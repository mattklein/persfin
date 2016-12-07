from datetime import datetime
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib

from jinja2 import Environment, PackageLoader
from sqlalchemy import select, and_

from credentials import ses_smtp
from persfin import EMAIL_FROM, SES_SMTP_SERVER, SES_SMTP_PORT, VERIFICATION_POST_URL
from persfin.core import get_user_by_id
from persfin.db import engine, transaction_tbl, user_tbl, verification_attempt_tbl, account_tbl


def get_possible_attributed_to_users(db_conn):
    # The list of users to which a transaction can be "attributed to" (that's any user in the system)
    s = select([user_tbl.c.id, user_tbl.c.name]).select_from(user_tbl)
    return db_conn.execute(s).fetchall()


def get_possible_forward_to_users(db_conn, excluded_user_ids):
    # The list of users to which this transaction can be "forwarded to"
    # This is any user who's got the is_verifier flag set, EXCEPT FOR the "initial verifier"
    s = select([user_tbl.c.id, user_tbl.c.name]).select_from(user_tbl) \
            .where(and_(user_tbl.c.is_verifier, user_tbl.c.id.notin_(excluded_user_ids)))
    return db_conn.execute(s).fetchall()


def get_verification_history_first_entry(dt, predicted_user_name, predicted_scores):
    # A single history entry -- the system's prediction for this transaction
    comment = ', '.join(['%s: %.0f%%' % (k, v * 100)
        for k, v in sorted(predicted_scores.items(), key=lambda x: x[1], reverse=True)])
    return {'date': dt,
            'who': 'System',
            'action': 'Prediction: %s' % predicted_user_name,
            'comment': comment}


def get_verification_history(db_conn, transaction_id):
    """
    The verification history is comprised of all of the verifications of this transaction,
    PLUS (at the beginning) the system's initial prediction as to the verifier.
    """
    history = []

    # Get the first entry (the predicted verifier)
    s = select([transaction_tbl.c.verifier_predicted_result,
                transaction_tbl.c.verifier_predicted_date,
                user_tbl.c.name.label('verifier_predicted_user_name')]) \
            .select_from(transaction_tbl.join(user_tbl,
                onclause=transaction_tbl.c.verifier_predicted_user_id == user_tbl.c.id)) \
            .where(transaction_tbl.c.id == transaction_id)
    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    row = rs.fetchone()
    history.append(get_verification_history_first_entry(row.verifier_predicted_date,
                                                        row.verifier_predicted_user_name,
                                                        row.verifier_predicted_result))

    # Get the rest of the entries (the verifications that have come so far)
    s = select([verification_attempt_tbl.c.attempt_replied_to,
                verification_attempt_tbl.c.did_verify,
                verification_attempt_tbl.c.comment,
                user_tbl.c.name.label('user_name')]) \
            .select_from(verification_attempt_tbl.join(user_tbl)) \
            .where(verification_attempt_tbl.c.transaction_id == transaction_id) \
            .order_by(verification_attempt_tbl.c.attempt_replied_to)
    existing_verifications = db_conn.execute(s).fetchall()
    for i, r in enumerate(existing_verifications[:-1]):  # We don't want the last verification attempt -- that's the one we're creating now
        next_verifier = existing_verifications[i + 1].user_name
        history.append({'date': r.attempt_replied_to,
                        'who': r.user_name,
                        'action': 'Forward to %s' % next_verifier if not r.did_verify else '???',
                        'comment': r.comment})
    return history


def derive_and_store_verification_attempt(db_conn, transaction_id, verifier_id):

    logging.info('Deriving and storing verification attempt')

    possible_attributed_tos = get_possible_attributed_to_users(db_conn)
    possible_other_verifiers = get_possible_forward_to_users(db_conn, [verifier_id, ])

    # Create the verification attempt in the DB
    i = verification_attempt_tbl.insert().values({
        'transaction_id': transaction_id,
        'asked_of': verifier_id,
        'did_verify': None,
        'attempt_sent': datetime.utcnow(),
    })
    r = db_conn.execute(i)
    verif_attempt_id = r.inserted_primary_key[0]

    return {'verif_attempt_id': verif_attempt_id,
            'possible_attributed_tos': possible_attributed_tos,
            'possible_other_verifiers': possible_other_verifiers}


def send_verification_email(verif_attempt_id, verifier, account_name, date, amount, merchant,
    possible_attributed_tos, possible_other_verifiers, verification_history):

    logging.info('Sending verification email to %s (%s)', verifier.name, verifier.email)

    date_str = datetime.strftime(date, '%m/%d/%Y')
    amount_str = '$%.2f' % amount

    env = Environment(loader=PackageLoader('persfin', 'email_templates'))
    templ = env.get_template('transaction_verification.html')
    msg_html = templ.render({
        'verif_attempt_id': verif_attempt_id,
        'account': account_name,
        'date': date_str,
        'merchant': merchant,
        'amount': amount_str,
        'post_url': VERIFICATION_POST_URL,
        'verifier': verifier,
        'possible_attributed_tos': possible_attributed_tos,
        'possible_other_verifiers': possible_other_verifiers,
        'default_attributed_to': verifier,
        'superuser': verifier.is_superuser,
        'verification_history': verification_history,
    })

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "[Persfin] %s %s %s" % (date_str, merchant, amount_str)
    msg['From'] = EMAIL_FROM
    msg['To'] = verifier.email
    part = MIMEText(msg_html, 'html')
    msg.attach(part)

    server_ssl = smtplib.SMTP_SSL(SES_SMTP_SERVER, SES_SMTP_PORT)
    server_ssl.login(ses_smtp.SMTP_USERNAME, ses_smtp.SMTP_PASSWORD)
    server_ssl.sendmail(EMAIL_FROM, [verifier.email, ], msg.as_string())
    server_ssl.quit()


def verify_transaction(verif_attempt_id, did_verify, forward_to_id, attributed_to_id,
    correcting_amount, corrected_amount, correcting_verifier, corrected_verifier_id):

    # TODO edge cases:
    #   - what if it's already verified, and this is a non-verification?  disallow it, or take off the verification attributes?
    #   - what if it's already verified, and this is a verification?
    #   - what if it's been forwarded to somebody else?  and a verification/non-verification comes through?

    assert isinstance(verif_attempt_id, int)
    assert isinstance(did_verify, bool)
    assert isinstance(forward_to_id, int)
    assert isinstance(attributed_to_id, int) or attributed_to_id is None
    assert isinstance(correcting_amount, bool)
    assert isinstance(corrected_amount, Decimal) or corrected_amount is None
    if not correcting_amount:
        corrected_amount = None
    if corrected_amount is not None:
        corrected_amount = round(corrected_amount, 2)
    assert isinstance(correcting_verifier, bool)
    assert isinstance(corrected_verifier_id, int) or corrected_verifier_id is None

    logging.info('Processing verification %s: did_verify %s, forward_to_id %s, attributed_to_id %s, '
        'correcting_amount %s, corrected_amount %s, correcting_verifier %s, corrected_verifier_id %s',
        verif_attempt_id, did_verify, forward_to_id, attributed_to_id, correcting_amount,
        corrected_amount, correcting_verifier, corrected_verifier_id)

    db_conn = engine.connect()
    db_trans = db_conn.begin()

    s = select([verification_attempt_tbl.c.transaction_id,
                verification_attempt_tbl.c.asked_of.label('verifier_id'),
                user_tbl.c.name.label('verifier_name'),
                verification_attempt_tbl.c.did_verify,
                transaction_tbl.c.date.label('transaction_date'),
                transaction_tbl.c.amount,
                transaction_tbl.c.merchant,
                account_tbl.c.name.label('account_name')]) \
            .select_from(verification_attempt_tbl
                .join(transaction_tbl)
                .join(account_tbl)
                .join(user_tbl, onclause=verification_attempt_tbl.c.asked_of == user_tbl.c.id)) \
            .where(verification_attempt_tbl.c.id == verif_attempt_id)
    rs = db_conn.execute(s)
    assert rs.rowcount == 1, '%s row(s) found for verif_attempt_id %s' % (rs.rowcount, verif_attempt_id)
    existing_db_rec = rs.fetchone()

    logging.info('Transaction %s, verifier "%s", amount %s, date %s, merchant "%s"',
        existing_db_rec['transaction_id'],
        existing_db_rec['verifier_name'],
        existing_db_rec['amount'],
        existing_db_rec['transaction_date'],
        existing_db_rec['merchant'])

    now = datetime.utcnow()
    u = verification_attempt_tbl.update() \
            .where(verification_attempt_tbl.c.id == verif_attempt_id) \
            .values({'did_verify': did_verify,
                     'attempt_replied_to': now})
    db_conn.execute(u)

    if did_verify:
        if correcting_verifier:
            verifier_id = corrected_verifier_id
        else:
            verifier_id = existing_db_rec['verifier_id']

        if corrected_amount == existing_db_rec['amount']:
            # They didn't actually make a correction
            corrected_amount = None

        u = transaction_tbl.update() \
                .where(transaction_tbl.c.id == existing_db_rec['transaction_id']) \
                .values({'is_verified': did_verify,
                         'verified_date': now,
                         'verified_by': verifier_id,
                         'attributed_to': attributed_to_id,
                         'amount_corrected': corrected_amount})

        db_conn.execute(u)

    else:
        verification_dict = derive_and_store_verification_attempt(db_conn, existing_db_rec['transaction_id'], forward_to_id)
        verification_history = get_verification_history(db_conn, existing_db_rec['transaction_id'])
        send_verification_email(
            verification_dict['verif_attempt_id'],
            get_user_by_id(db_conn, forward_to_id),
            existing_db_rec['account_name'],
            existing_db_rec['transaction_date'],
            existing_db_rec['amount'],
            existing_db_rec['merchant'],
            verification_dict['possible_attributed_tos'],
            verification_dict['possible_other_verifiers'],
            verification_history)

    db_trans.commit()

    logging.info('Done processing verification %d', verif_attempt_id)
    return 'OK'

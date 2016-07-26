from datetime import datetime
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.parser import Parser
import logging
import re
import smtplib

import boto
from jinja2 import Environment, PackageLoader
from sqlalchemy import select, and_

from credentials import s3_full, ses_smtp
from persfin import S3_BUCKET_NAME, EMAIL_FROM, SES_SMTP_SERVER, SES_SMTP_PORT
from persfin.db import engine, account_tbl, transaction_tbl, user_tbl, verification_attempt_tbl


def _fetch_email_from_s3_and_parse(s3_obj):

    logging.info('Parsing email message for %s', s3_obj.key)

    email_msg_str = s3_obj.get_contents_as_string()
    msg = Parser().parsestr(email_msg_str)
    subparts = [p for p in msg.walk()]
    for i, subpart in enumerate(subparts):
        logging.info('Subpart %d - %s', i, subpart.get_content_type())
        if subpart.get_content_type() == 'text/plain':
            text_payload = subpart.get_payload()

    assert text_payload is not None

    try:
        merchant_raw = re.search(r'^Merchant: (.*)\r\n', text_payload, flags=re.MULTILINE).groups()[0]
        amount_raw = re.search(r'^Amount: (.*)\r\n', text_payload, flags=re.MULTILINE).groups()[0]
        date_raw = re.search(r'^Date: (.*)\r\n', text_payload, flags=re.MULTILINE).groups()[0]
    except AttributeError:
        logging.info("Couldn't parse merchant/amount/date for email with text payload:\n%s", text_payload)
        raise

    merchant_parsed = merchant_raw.upper().strip()
    amount_parsed = Decimal(amount_raw[1:]) if amount_raw[0] == '$' else Decimal(amount_raw)
    date_parsed = datetime.strptime(date_raw, '%B %d, %Y').date()

    logging.info('Raw value -> Parsed value')
    logging.info('"%s" -> "%s"', merchant_raw, merchant_parsed)
    logging.info('"%s" -> "%s"', amount_raw, amount_parsed)
    logging.info('"%s" -> "%s"', date_raw, date_parsed)

    return {'merchant_parsed': merchant_parsed,
            'amount_parsed': amount_parsed,
            'date_parsed': date_parsed}


def _store_transaction_into_db(db_conn, merchant, date, amount, message_id, account):

    logging.info('Storing transaction into DB')

    i = transaction_tbl.insert().values({
        'account_id': account.id,
        'merchant': merchant,
        'date': date,
        'amount': amount,
        'email_message_id': message_id,
        'source': 'bank_email_through_persfin',
        'created_date': datetime.utcnow(),
        'is_verified': False,
        'is_cleared': False
    })
    r = db_conn.execute(i)
    return r.inserted_primary_key[0]


def _derive_and_store_verification_attempt(db_conn, new_transaction_id):

    logging.info('Deriving and storing verification attempt')

    # The user who will be the initial verifier for this transaction -- for now, always me
    s = select(['id', 'name', 'email']).select_from(user_tbl).where(user_tbl.c.name == 'Matt')
    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    initial_verifier = rs.fetchone()

    # The list of users to which this transaction can be "attributed to" (that's any user in the system)
    s = select([user_tbl.c.id, user_tbl.c.name]).select_from(user_tbl)
    possible_attributed_tos = db_conn.execute(s).fetchall()

    # The list of users to which this transaction can be "forwarded to"
    # This is any user who's got the is_verifier flag set, EXCEPT FOR the "initial verifier"
    s = select([user_tbl.c.id, user_tbl.c.name]).select_from(user_tbl) \
            .where(and_(user_tbl.c.is_verifier, user_tbl.c.id != initial_verifier.id))
    possible_other_verifiers = db_conn.execute(s).fetchall()

    # Create the verification attempt in the DB
    db_conn.execute(verification_attempt_tbl.insert().values({
        'transaction_id': new_transaction_id,
        'asked_of': initial_verifier.id,
        'did_verify': None,
        'attempt_sent': datetime.utcnow(),
    }))

    return {'initial_verifier': initial_verifier,
            'possible_attributed_tos': possible_attributed_tos,
            'possible_other_verifiers': possible_other_verifiers}


def _send_verification_email(verifier, account_name, date, amount, merchant,
    possible_attributed_tos, possible_other_verifiers):

    logging.info('Sending verification email to %s (%s)', verifier.name, verifier.email)

    date_str = datetime.strftime(date, '%m/%d/%Y')
    amount_str = '$%.2f' % amount

    env = Environment(loader=PackageLoader('persfin', 'email_templates'))
    templ = env.get_template('transaction_verification.html')
    msg_html = templ.render({
        'account': account_name,
        'date': date_str,
        'merchant': merchant,
        'amount': amount_str,
        'post_url': 'http://mantilklein.us/thething',
        'verifier': verifier,
        'possible_attributed_tos': possible_attributed_tos,
        'possible_other_verifiers': possible_other_verifiers,
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


def process_email_msg_in_s3(source_folder, message_id):

    assert source_folder in ('unprocessed', 'failed')
    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    bucket = s3_conn.get_bucket(S3_BUCKET_NAME)
    s3_key = '%s/%s' % (source_folder, message_id)
    s3_obj = bucket.get_key(s3_key)
    if not s3_obj:
        raise Exception('Expected S3 key not found (%s)' % s3_key)

    try:
        parsed_email_dict = _fetch_email_from_s3_and_parse(s3_obj)

        db_conn = engine.connect()
        db_trans = db_conn.begin()

        # For now, always use Discover as the account
        s = select(['id', 'name']).select_from(account_tbl).where(account_tbl.c.name == 'Discover')
        rs = db_conn.execute(s)
        assert rs.rowcount == 1
        account = rs.fetchone()

        new_trans_id = _store_transaction_into_db(db_conn,
                                                  parsed_email_dict['merchant_parsed'],
                                                  parsed_email_dict['date_parsed'],
                                                  parsed_email_dict['amount_parsed'],
                                                  message_id,
                                                  account)

        verification_dict = _derive_and_store_verification_attempt(db_conn, new_trans_id)

        _send_verification_email(
            verification_dict['initial_verifier'],
            account.name,
            parsed_email_dict['date_parsed'],
            parsed_email_dict['amount_parsed'],
            parsed_email_dict['merchant_parsed'],
            verification_dict['possible_attributed_tos'],
            verification_dict['possible_other_verifiers'])

        logging.info('Moving S3 file into "processed" folder')
        s3_obj.copy(S3_BUCKET_NAME, 'processed/%s' % message_id)
        s3_obj.delete()

        db_trans.commit()

    except Exception:
        if s3_obj:
            if source_folder != 'failed':  # If it's already in failed, just leave it there!  Don't delete it!
                logging.info('Moving S3 file into "failed" folder')
                s3_obj.copy(S3_BUCKET_NAME, 'failed/%s' % message_id)
                s3_obj.delete()
        raise

from datetime import datetime
from decimal import Decimal
from email.parser import Parser
import logging
import re

import boto
from sqlalchemy import select

from credentials import s3_full
from persfin import S3_BUCKET_NAME
from persfin.core.transaction_verification import derive_and_store_verification_attempt, send_verification_email
from persfin.db import engine, account_tbl, transaction_tbl


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

        verification_dict = derive_and_store_verification_attempt(db_conn, new_trans_id)

        send_verification_email(
            verification_dict['verif_attempt_id'],
            verification_dict['initial_verifier'],
            account.name,
            parsed_email_dict['date_parsed'],
            parsed_email_dict['amount_parsed'],
            parsed_email_dict['merchant_parsed'],
            verification_dict['possible_attributed_tos'],
            verification_dict['possible_other_verifiers'])

        logging.info('Moving S3 file into "processed" folder')
        s3_obj.copy(S3_BUCKET_NAME, 'processed/%s' % message_id)
        # TODO set content type to "text/plain"
        s3_obj.delete()

        db_trans.commit()

    except Exception:
        if s3_obj:
            if source_folder != 'failed':  # If it's already in failed, just leave it there!  Don't delete it!
                logging.info('Moving S3 file into "failed" folder')
                s3_obj.copy(S3_BUCKET_NAME, 'failed/%s' % message_id)
                # TODO set content type to "text/plain"
                s3_obj.delete()
        raise

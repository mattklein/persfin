from datetime import datetime
from decimal import Decimal
from email.parser import Parser
import logging
import re

import boto
import psycopg2

from credentials import s3_full, DBPASSWORD
from persfin import S3_BUCKET_NAME, DBHOST, DBPORT, DBUSER, DBNAME


def process_email_msg_in_s3(source_folder, message_id):

    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    bucket = s3_conn.get_bucket(S3_BUCKET_NAME)
    assert source_folder in ('unprocessed', 'failed')

    try:
        s3_key = '%s/%s' % (source_folder, message_id)
        s3_obj = bucket.get_key(s3_key)
        if not s3_obj:
            raise Exception('Expected S3 key not found (%s)' % s3_key)

        logging.info('Parsing email message')
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

        logging.info('Storing transaction into DB')
        conn = psycopg2.connect(host=DBHOST, port=DBPORT, user=DBUSER, database=DBNAME, password=DBPASSWORD)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transaction (
                merchant, date, amount,
                email_message_id, source, created_date,
                is_verified, is_cleared)
            VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s );''',
            (merchant_parsed, date_parsed, amount_parsed,
             message_id, 'bank_email_through_persfin', datetime.utcnow(),
             False, False)
        )
        conn.commit()

        logging.info('Moving S3 file into "processed" folder')
        s3_obj.copy(S3_BUCKET_NAME, 'processed/%s' % message_id)
        s3_obj.delete()

    except Exception:
        if s3_obj:
            if source_folder != 'failed':  # If it's already in failed, just leave it there!  Don't delete it!
                logging.info('Moving S3 file into "failed" folder')
                s3_obj.copy(S3_BUCKET_NAME, 'failed/%s' % message_id)
                s3_obj.delete()
        raise

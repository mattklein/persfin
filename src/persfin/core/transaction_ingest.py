from datetime import datetime
from decimal import Decimal
from email.parser import Parser
import logging
import re

import boto

from credentials import s3_full, ml_full
from persfin import EMAIL_BUCKET_NAME, ML_BUCKET_NAME, ML_MOST_RECENT_TRANSACTIONS_FILENAME
from persfin.core import get_account_for_transaction, get_user_by_username
from persfin.core.transaction_verification import derive_and_store_verification_attempt, send_verification_email
from persfin.db import engine, transaction_tbl
from persfin import ml


def _parse_for_merchant(text):
    try:
        merchant_raw = re.search(r'^Merchant: (.*)\r\n', text, flags=re.MULTILINE).groups()[0]
    except AttributeError:
        logging.info("Couldn't parse merchant from text:\n%s", text)
        raise
    merchant_parsed = merchant_raw.upper().strip()
    return merchant_raw, merchant_parsed


def _parse_for_amount(text):
    try:
        amount_raw = re.search(r'^Amount: (.*)\r\n', text, flags=re.MULTILINE).groups()[0]
        is_credit = False
    except AttributeError:
        try:
            amount_raw = re.search(r'^Amount Credited: (.*)\r\n', text, flags=re.MULTILINE).groups()[0]
        except AttributeError:
            logging.info("Couldn't parse amount from text:\n%s", text)
            raise
        is_credit = True
    amount_parsed = Decimal(amount_raw[1:]) if amount_raw[0] == '$' else Decimal(amount_raw)
    if is_credit:
        amount_parsed *= -1
    return amount_raw, amount_parsed


def _parse_for_date(text):
    try:
        date_raw = re.search(r'^(?:Date|Posting Date): (.*)\r\n', text, flags=re.MULTILINE).groups()[0]
    except AttributeError:
        logging.info("Couldn't parse date from text:\n%s", text)
        raise
    date_parsed = datetime.strptime(date_raw, '%B %d, %Y').date()
    return date_raw, date_parsed


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

    merchant_raw, merchant_parsed = _parse_for_merchant(text_payload)
    amount_raw, amount_parsed = _parse_for_amount(text_payload)
    date_raw, date_parsed = _parse_for_date(text_payload)

    logging.info('Raw value -> Parsed value')
    logging.info('"%s" -> "%s"', merchant_raw, merchant_parsed)
    logging.info('"%s" -> "%s"', amount_raw, amount_parsed)
    logging.info('"%s" -> "%s"', date_raw, date_parsed)

    return {'merchant_parsed': merchant_parsed,
            'amount_parsed': amount_parsed,
            'date_parsed': date_parsed}


def _perform_ml_prediction(ml_conn, ml_model_id, merchant, date_, amount, account_name, now):
    ml_model = ml_conn.get_ml_model(ml_model_id)
    python_weekday, weekend = ml.weekday_fields(date_)
    record = {
        'id': -1,  # Fine I think
        'merchant': merchant,
        'date': date_,
        'day_of_week': python_weekday,
        'weekend': weekend,
        'amount': amount,
        'created_date': now,
        'account': account_name,
    }
    # "Standardize" each of the values in the dict
    record = dict([(k, ml.standardize(v)) for k, v in record.items()])
    return ml_conn.predict(
        ml_model_id=ml_model_id,
        predict_endpoint=ml_model['EndpointInfo']['EndpointUrl'],
        record=record)


def _store_transaction_into_db(db_conn, merchant, date, amount, message_id, account, now, ml_model_id,
    verifier_predicted_result, verifier_predicted_user_id):

    logging.info('Storing transaction into DB')

    i = transaction_tbl.insert().values({
        'account_id': account.id,
        'merchant': merchant,
        'date': date,
        'amount': amount,
        'email_message_id': message_id,
        'source': 'bank_email_through_persfin',
        'created_date': now,
        'is_verified': False,
        'is_cleared': False,
        'verifier_predicted_date': now,
        'verifier_predicted_model_id': ml_model_id,
        'verifier_predicted_result': verifier_predicted_result,
        'verifier_predicted_user_id': verifier_predicted_user_id,
    })
    r = db_conn.execute(i)
    return r.inserted_primary_key[0]


def process_email_msg_in_s3(source_folder, message_id):

    assert source_folder in ('unprocessed', 'failed')
    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    email_bucket = s3_conn.get_bucket(EMAIL_BUCKET_NAME)
    s3_key = '%s/%s' % (source_folder, message_id)
    s3_obj = email_bucket.get_key(s3_key)
    if not s3_obj:
        raise Exception('Expected S3 key not found (%s)' % s3_key)

    try:
        parsed_email_dict = _fetch_email_from_s3_and_parse(s3_obj)

        db_conn = engine.connect()
        db_trans = db_conn.begin()

        account = get_account_for_transaction(db_conn)
        now = datetime.utcnow()

        logging.info('Calling ML to predict verifier')
        ml_bucket = s3_conn.get_bucket(ML_BUCKET_NAME)
        transactions_filename = ml_bucket.get_key(ML_MOST_RECENT_TRANSACTIONS_FILENAME).get_contents_as_string()
        ml_conn = boto.connect_machinelearning(ml_full.ACCESS_KEY_ID, ml_full.SECRET_ACCESS_KEY)
        prediction_dict = _perform_ml_prediction(
            ml_conn,
            transactions_filename,
            parsed_email_dict['merchant_parsed'],
            parsed_email_dict['date_parsed'],
            parsed_email_dict['amount_parsed'],
            account.name,
            now)

        verifier_predicted_user = get_user_by_username(db_conn, prediction_dict['Prediction']['predictedLabel'])
        verifier_predicted_scores = prediction_dict['Prediction']['predictedScores']

        logging.info('Predicted verifier is "%s" (%s)', verifier_predicted_user.name, verifier_predicted_scores)

        new_trans_id = _store_transaction_into_db(
            db_conn,
            parsed_email_dict['merchant_parsed'],
            parsed_email_dict['date_parsed'],
            parsed_email_dict['amount_parsed'],
            message_id,
            account,
            now,
            transactions_filename,
            verifier_predicted_scores,
            verifier_predicted_user.id)

        verification_dict = derive_and_store_verification_attempt(db_conn, new_trans_id, verifier_predicted_user.id)

        send_verification_email(
            verification_dict['verif_attempt_id'],
            verifier_predicted_user,
            account.name,
            parsed_email_dict['date_parsed'],
            parsed_email_dict['amount_parsed'],
            parsed_email_dict['merchant_parsed'],
            verification_dict['possible_attributed_tos'],
            verification_dict['possible_other_verifiers'])

        db_trans.commit()

        logging.info('Moving S3 file into "processed" folder')
        s3_obj.copy(EMAIL_BUCKET_NAME, 'processed/%s' % message_id, metadata={'Content-Type': 'text/plain'})
        s3_obj.delete()

    except Exception:
        if s3_obj:
            if source_folder != 'failed':  # If it's already in failed, just leave it there!  Don't delete it!
                logging.info('Moving S3 file into "failed" folder')
                s3_obj.copy(EMAIL_BUCKET_NAME, 'failed/%s' % message_id, metadata={'Content-Type': 'text/plain'})
                s3_obj.delete()
        raise

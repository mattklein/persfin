import logging

from persfin.core import process_email_msg_in_s3


def lambda_handler(event, context):

    logging.getLogger().setLevel(logging.INFO)
    logging.debug('Received event:\n%s', event)
    try:
        message_id = event['Records'][0]['ses']['mail']['messageId']
    except Exception as e:
        raise Exception("Couldn't get message ID from event:\n%s\n%s" % (event, e))

    process_email_msg_in_s3('unprocessed', message_id)

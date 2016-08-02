import logging

from persfin.core.transaction_verification import verify_transaction


def lambda_handler(event, context):

    logging.getLogger().setLevel(logging.INFO)
    logging.debug('Received event:\n%s', event)

    verify_transaction(int(event['verif-attempt-id']),
                       event['verified'] == 'Yes',
                       int(event['forward-to']),
                       int(event['attributed-to']))

    return "OK"

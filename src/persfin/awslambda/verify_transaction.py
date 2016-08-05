import logging

from persfin.core.transaction_verification import verify_transaction


def lambda_handler(event, context):

    logging.getLogger().setLevel(logging.INFO)
    logging.debug('Received event:\n%s', event)

    try:
        # This handles the case where we're receiving an event via a POST request (which I'm not currently
        # using -- see background/explanation in transaction_verification.html)
        verif_attempt_id = int(event['verif-attempt-id'])
        verified = event['verified'] == 'Yes'
        forward_to = int(event['forward-to'])
        attributed_to = int(event['attributed-to'])
    except KeyError:
        try:
            # This handles the case where we're receiving an event via a GET request
            verif_attempt_id = int(event['params']['querystring']['verif-attempt-id'])
            verified = event['params']['querystring']['verified'] == 'Yes'
            forward_to = int(event['params']['querystring']['forward-to'])
            attributed_to = int(event['params']['querystring']['attributed-to'])
        except KeyError:
            logging.error("Couldn't get parameters from event:\n%s", event)
            raise

    verify_transaction(verif_attempt_id, verified, forward_to, attributed_to)

    return "OK"

from decimal import Decimal
import logging

from persfin.core.transaction_verification import verify_transaction


def lambda_handler(event, context):

    logging.getLogger().setLevel(logging.INFO)
    logging.debug('Received event:\n%s', event)

    try:
        # Handles the case where we're receiving an event via a GET request
        parm_container = event['params']['querystring']
    except IndexError:
        # Handles the case where we're receiving an event via a POST request (which I'm not currently
        # using -- see background/explanation in transaction_verification.html)
        parm_container = event

    verif_attempt_id = int(parm_container['verif-attempt-id'])
    verified = parm_container['verified'] in ('Yes', 'Yes amount correction', 'Yes verifier correction')

    forward_to = int(parm_container['forward-to'])
    attributed_to = parm_container.get('attributed-to')
    if attributed_to is not None:
        attributed_to = int(attributed_to)

    correcting_amount = parm_container['verified'] == 'Yes amount correction'
    corrected_amount = parm_container.get('corrected-amount')
    if corrected_amount is not None:
        if corrected_amount.startswith('$'):
            corrected_amount = corrected_amount[1:]
        corrected_amount = Decimal(corrected_amount)

    correcting_verifier = parm_container['verified'] == 'Yes verifier correction'
    corrected_verifier = parm_container.get('corrected-verifier')
    if corrected_verifier is not None:
        corrected_verifier = int(corrected_verifier)

    verify_transaction(verif_attempt_id, verified, forward_to, attributed_to, correcting_amount,
        corrected_amount, correcting_verifier, corrected_verifier)

    return "OK"

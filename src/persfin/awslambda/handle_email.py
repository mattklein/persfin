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

    # TODO problem: if the function fails, Lambda will automatically retry it (twice, apparently)
    # I'll want to avoid this behavior if I've moved the file to the "failed" folder (the retry will fail; won't find the file in "unprocessed")
    # should I make the function smarter -- look for it in failed if it isn't found in unprocessed?
    # or it might be possible to have Lambda treat an error I'm handling as a NON-failure -- e.g., by calling context.done()
    # https://forums.aws.amazon.com/thread.jspa?messageID=643046

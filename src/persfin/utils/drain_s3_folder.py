import logging
import sys
import traceback

import boto

from credentials import s3_full
from persfin import S3_BUCKET_NAME
from persfin.core.transaction_ingest import process_email_msg_in_s3


def drain_s3_folder(folder_name):
    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    bucket = s3_conn.get_bucket(S3_BUCKET_NAME)
    s3_keys = [k for k in bucket.list(prefix='%s/' % folder_name)
              if k.key != '%s/' % folder_name]  # The folder itself shows up as a "file", with nothing after the slash
    logging.info('Found %d files in the %s folder', len(s3_keys), folder_name)
    successes, failures = 0, 0
    for s3_key in sorted(s3_keys, key=lambda x: x.last_modified):
        try:
            logging.info('Processing %s (%s)', s3_key.key, s3_key.last_modified)
            message_id = s3_key.key.split('/')[-1]
            process_email_msg_in_s3(folder_name, message_id)
            successes += 1
        except Exception as e:
            logging.info('Failed (%s)\n%s' % (e, traceback.format_exc()))
            failures += 1
    logging.info('Num files: %d   Successes: %d   Failures: %d', len(s3_keys), successes, failures)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stream_handler)
    try:
        folder_name = sys.argv[1]
    except IndexError:
        folder_name = None
    if len(sys.argv) != 2 or folder_name not in ('unprocessed', 'failed'):
        print 'Usage: %s <unprocessed|failed>' % sys.argv[0]
        sys.exit(1)
    drain_s3_folder(folder_name)

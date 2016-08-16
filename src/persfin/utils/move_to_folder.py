import logging
import sys

import boto

from credentials import s3_full
from persfin import S3_BUCKET_NAME


def move_to_folder(message_id, old_folder_name, new_folder_name):
    logging.info('Moving %s from %s to %s', message_id, old_folder_name, new_folder_name)
    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    bucket = s3_conn.get_bucket(S3_BUCKET_NAME)
    k = bucket.get_key('%s/%s' % (old_folder_name, message_id))
    k.copy(S3_BUCKET_NAME, '%s/%s' % (new_folder_name, message_id), metadata={'Content-Type': 'text/plain'})
    k.delete()


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stream_handler)
    if len(sys.argv) != 4:
        print 'Usage: %s message_id from_folder to_folder' % sys.argv[0]
        print 'E.g.:  %s bms9ienlmp6q9p2952o6up34kd12g9su34oa5701 failed should-not-process' % sys.argv[0]
        sys.exit(1)
    move_to_folder(sys.argv[1], sys.argv[2], sys.argv[3])

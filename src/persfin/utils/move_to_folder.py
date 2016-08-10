import boto

from credentials import s3_full
from persfin import S3_BUCKET_NAME


def move_to_folder(message_id, old_folder_name, new_folder_name):
    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    bucket = s3_conn.get_bucket(S3_BUCKET_NAME)
    k = bucket.get_key('%s/%s' % (old_folder_name, message_id))
    k.copy(S3_BUCKET_NAME, '%s/%s' % (new_folder_name, message_id), metadata={'Content-Type': 'text/plain'})
    k.delete()


if __name__ == '__main__':
    move_to_folder('2nufdqqtptvbmi5uf9vj84p6ss36pmql0f054r01', 'failed', 'should-not-process')

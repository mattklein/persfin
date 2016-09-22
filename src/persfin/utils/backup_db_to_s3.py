from datetime import datetime
import logging
import os
import subprocess

import boto3

from credentials import s3_full
from persfin import DB_BACKUP_BUCKET_NAME, configure_logging_file


def main():
    logging.info('Beginning backup_db_to_s3.py')
    now = datetime.utcnow()
    output_dir = '/tmp'
    output_filename = 'pg_dumpall_%s.gz' % now.strftime('%Y%m%d')
    output_fullpath = os.path.join(output_dir, output_filename)
    cmd = 'pg_dumpall -U postgres -h localhost -p 5432 | gzip -c > %s' % output_fullpath
    logging.info('Running dump with command "%s"', cmd)
    subprocess.check_call(cmd, shell=True)
    logging.info('Uploading output file to S3')
    s3 = boto3.client('s3',
                      aws_access_key_id=s3_full.ACCESS_KEY_ID,
                      aws_secret_access_key=s3_full.SECRET_ACCESS_KEY)
    s3.put_object(Bucket=DB_BACKUP_BUCKET_NAME,
                  Key=output_filename,
                  Body=open(output_fullpath, 'rb'),
                  ContentType='application/gzip')
    logging.info('Removing %s', output_fullpath)
    os.remove(output_fullpath)
    logging.info('Done')


if __name__ == '__main__':
    configure_logging_file('/var/log/backup_db_to_s3.log')
    main()

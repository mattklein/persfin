from datetime import datetime
import os
import subprocess

import boto3

from credentials import s3full
from persfin import DB_BACKUP_BUCKET_NAME


def main():
    now = datetime.utcnow()
    output_dir = '/tmp'
    output_filename = 'pg_dumpall_%s.gz' % now.strftime('%Y%m%d')
    output_fullpath = os.path.join(output_dir, output_filename)
    subprocess.check_call(
        'pg_dumpall -U postgres -h localhost -p 5432 | gzip -c > %s' % output_fullpath,
        shell=True)
    s3 = boto3.client('s3',
                      aws_access_key_id=s3full.ACCESS_KEY_ID,
                      aws_secret_access_key=s3full.SECRET_ACCESS_KEY)
    s3.put_object(Bucket=DB_BACKUP_BUCKET_NAME,
                  Key=output_filename,
                  Body=open(output_fullpath, 'rb'),
                  ContentType='application/gzip')
    os.remove(output_fullpath)


if __name__ == '__main__':
    main()

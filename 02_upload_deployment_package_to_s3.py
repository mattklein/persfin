#!/usr/bin/env python
import sys
import boto

from credentials import s3_full

if len(sys.argv) != 1:
    print 'Usage: %s' % sys.argv[0]
    sys.exit(1)

print 'Starting upload'
s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
bucket = s3_conn.get_bucket('us-mantilklein-pf-lambdabuild')
filename = 'lambda_deployment.zip'
k = bucket.new_key(filename)
k.set_contents_from_filename('/Users/mattklein/code/misc/pers_finance_2016/build/%s' % filename)
print 'Done with upload'

print 'Now you can paste this URL into the "S3 link URL" in the Lambda console:'
print 'https://s3.amazonaws.com/us-mantilklein-pf-lambdabuild/%s' % filename

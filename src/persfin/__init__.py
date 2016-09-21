import logging
import sys

EMAIL_BUCKET_NAME = 'us-mantilklein-pf-emails'
ML_BUCKET_NAME = 'us-mantilklein-ml-transactions'
ML_MOST_RECENT_TRANSACTIONS_FILENAME = '00_most_recent_filename.txt'
DBHOST = 'persfin-db.mantilklein.us'
DBPORT = '5432'
DBNAME = 'persfin'
DBUSER = 'postgres'
EMAIL_FROM = 'persfin@mantilklein.us'
SES_SMTP_SERVER = 'email-smtp.us-east-1.amazonaws.com'
SES_SMTP_PORT = 465
VERIFICATION_POST_URL = 'https://6q4ab38ci9.execute-api.us-east-1.amazonaws.com/prod/transaction-verification'
OPS_EMAIL = 'mpklein+persfinops@gmail.com'


def configure_logging():
    logging.getLogger().setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stream_handler)

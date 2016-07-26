from sqlalchemy import create_engine, MetaData
from sqlalchemy.pool import NullPool

from credentials import DBPASSWORD
from persfin import DBHOST, DBPORT, DBNAME, DBUSER

engine = create_engine('postgresql+psycopg2://%s:%s@%s:%s/%s' % (
    DBUSER, DBPASSWORD, DBHOST, DBPORT, DBNAME), echo=False, poolclass=NullPool)
metadata = MetaData(bind=engine)
metadata.reflect(bind=engine, views=True)

account_tbl = metadata.tables['account']
transaction_tbl = metadata.tables['transaction']
user_tbl = metadata.tables['persfin_user']
verification_attempt_tbl = metadata.tables['verification_attempt']

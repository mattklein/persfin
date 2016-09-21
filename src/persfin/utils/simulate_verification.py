from datetime import datetime
import logging
import sys

from persfin import configure_logging
from persfin.core import get_user_by_username
from persfin.db import engine, transaction_tbl, verification_attempt_tbl


def simulate_verification(db_conn, transaction_id, verifier_id):

    logging.info('Simulating verification of transaction ID %d by user ID %d' % (transaction_id, verifier_id))
    now = datetime.utcnow()
    db_trans = db_conn.begin()

    i = verification_attempt_tbl.insert().values({
        'transaction_id': transaction_id,
        'asked_of': verifier_id,
        'did_verify': True,
        'attempt_sent': now,
        'attempt_replied_to': now,
    })
    db_conn.execute(i)

    u = transaction_tbl.update() \
        .where(transaction_tbl.c.id == transaction_id) \
        .values({'is_verified': True,
                 'verified_date': now,
                 'verified_by': verifier_id})
    db_conn.execute(u)

    db_trans.commit()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print 'Usage: %s <verifier_username> <transaction_ids>' % sys.argv[0]
        sys.exit(1)
    configure_logging()
    verifier_name = sys.argv[1]
    transaction_ids = [int(tid) for tid in sys.argv[2:]]
    db_conn = engine.connect()
    verifier = get_user_by_username(db_conn, verifier_name)
    for transaction_id in transaction_ids:
        simulate_verification(db_conn, transaction_id, verifier.id)

import logging
import sys

from sqlalchemy import select

from persfin.core.transaction_verification import send_verification_email, get_initial_verifier, get_possible_attributed_to_users, get_possible_forward_to_users
from persfin.db import engine, verification_attempt_tbl, transaction_tbl, account_tbl


def resend_verification_email(verif_attempt_id):

    db_conn = engine.connect()
    s = select([verification_attempt_tbl.c.id,
                verification_attempt_tbl.c.asked_of,
                transaction_tbl.c.date,
                transaction_tbl.c.amount,
                transaction_tbl.c.merchant,
                account_tbl.c.name.label('account_name'),
                ]) \
            .select_from(verification_attempt_tbl
                .join(transaction_tbl)
                .join(account_tbl)) \
            .where(verification_attempt_tbl.c.id == verif_attempt_id)

    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    dbrow = rs.fetchone()

    initial_verifier = get_initial_verifier(db_conn)
    possible_attributed_tos = get_possible_attributed_to_users(db_conn)
    possible_other_verifiers = get_possible_forward_to_users(db_conn, [initial_verifier.id, ])

    send_verification_email(
        dbrow['id'],
        initial_verifier,
        dbrow['account_name'],
        dbrow['date'],
        dbrow['amount'],
        dbrow['merchant'],
        possible_attributed_tos,
        possible_other_verifiers)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: %s <verif_attempt_id>' % sys.argv[0]
        sys.exit(1)
    logging.getLogger().setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stream_handler)
    verif_attempt_id = int(sys.argv[1])
    resend_verification_email(verif_attempt_id)

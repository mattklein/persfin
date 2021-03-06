import sys

from sqlalchemy import select

from persfin import configure_logging
from persfin.core import get_user_by_id
from persfin.core.transaction_verification import send_verification_email, get_possible_attributed_to_users, get_possible_forward_to_users, get_verification_history
from persfin.db import engine, verification_attempt_tbl, transaction_tbl, account_tbl


def resend_verification_email(verif_attempt_ids):

    db_conn = engine.connect()
    for verif_attempt_id in verif_attempt_ids:
        s = select([verification_attempt_tbl.c.id,
                    verification_attempt_tbl.c.asked_of,
                    transaction_tbl.c.id.label('transaction_id'),
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

        verifier = get_user_by_id(db_conn, dbrow['asked_of'])
        possible_attributed_tos = get_possible_attributed_to_users(db_conn)
        possible_other_verifiers = get_possible_forward_to_users(db_conn, [verifier.id, ])
        verification_history = get_verification_history(db_conn, dbrow['transaction_id'])

        send_verification_email(
            dbrow['id'],
            verifier,
            dbrow['account_name'],
            dbrow['date'],
            dbrow['amount'],
            dbrow['merchant'],
            possible_attributed_tos,
            possible_other_verifiers,
            verification_history)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'Usage: %s <verif_attempt_ids>' % sys.argv[0]
        sys.exit(1)
    configure_logging()
    verif_attempt_ids = [int(id_) for id_ in sys.argv[1:]]
    resend_verification_email(verif_attempt_ids)

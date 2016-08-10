from sqlalchemy import select

from persfin.db import user_tbl, account_tbl


def get_user_by_username(db_conn, username):
    s = select(['id', 'name', 'email']).select_from(user_tbl).where(user_tbl.c.name == username)
    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    return rs.fetchone()


def get_user_by_id(db_conn, user_id):
    s = select(['id', 'name', 'email']).select_from(user_tbl).where(user_tbl.c.id == user_id)
    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    return rs.fetchone()


def get_account_for_transaction(db_conn):
    # For now, always use Discover as the account
    s = select(['id', 'name']).select_from(account_tbl).where(account_tbl.c.name == 'Discover')
    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    account = rs.fetchone()
    return account

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

from sqlalchemy import select

from credentials import ses_smtp
from persfin import EMAIL_FROM, SES_SMTP_SERVER, SES_SMTP_PORT, OPS_EMAIL
from persfin.db import user_tbl, account_tbl


def get_user_by_username(db_conn, username):
    s = select(['id', 'name', 'email', 'is_superuser']) \
            .select_from(user_tbl) \
            .where(user_tbl.c.name.lower() == username.lower())
    rs = db_conn.execute(s)
    assert rs.rowcount == 1
    return rs.fetchone()


def get_user_by_id(db_conn, user_id):
    s = select(['id', 'name', 'email', 'is_superuser']) \
            .select_from(user_tbl) \
            .where(user_tbl.c.id == user_id)
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


def send_error_email(subject, body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "[Persfin Ops] %s" % subject
    msg['From'] = EMAIL_FROM
    msg['To'] = OPS_EMAIL
    msg_html = body
    part = MIMEText(msg_html, 'html')
    msg.attach(part)

    server_ssl = smtplib.SMTP_SSL(SES_SMTP_SERVER, SES_SMTP_PORT)
    server_ssl.login(ses_smtp.SMTP_USERNAME, ses_smtp.SMTP_PASSWORD)
    server_ssl.sendmail(EMAIL_FROM, [OPS_EMAIL, ], msg.as_string())
    server_ssl.quit()

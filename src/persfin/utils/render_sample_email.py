import os

from jinja2 import Environment, PackageLoader

from persfin.core import get_user_by_username
from persfin.core.transaction_verification import get_possible_attributed_to_users, get_possible_forward_to_users, \
                                                  get_verification_history
from persfin.db import engine

db_conn = engine.connect()
verifier = get_user_by_username(db_conn, 'Matt')
possible_attributed_tos = get_possible_attributed_to_users(db_conn)
possible_other_verifiers = get_possible_forward_to_users(db_conn, [verifier.id, ])
verification_history = get_verification_history(db_conn, 693)

env = Environment(loader=PackageLoader('persfin', 'email_templates'))
templ = env.get_template('transaction_verification.html')
msg_html = templ.render({
    'verif_attempt_id': -1,
    'account': 'Discover',
    'date': '12/05/2016',
    'merchant': 'AMAZON.COM',
    'amount': '$158.31',
    'post_url': 'https://none.com/prod/transaction-verification',
    'verifier': verifier,
    'possible_attributed_tos': possible_attributed_tos,
    'possible_other_verifiers': possible_other_verifiers,
    'default_attributed_to': verifier,
    'superuser': verifier.is_superuser,
    'verification_history': verification_history,
})

this_scripts_directory = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(this_scripts_directory, 'sample_email_rendered.html'), 'wb') as f:
    f.write(msg_html)

# from collections import namedtuple
from datetime import datetime, date
from decimal import Decimal
from email.parser import Parser
import os
import re

# TODO make a unit test out of this -- add additional cases that seem trickier or that break this parsing

sample_email_filenames = [
    'ftebuck5p874lpgsq90qjd42h5k02617dt1d1rg1',
    'lib0vu9si6fbi1u3tecqeamee28vhp6d2suqv481',
    'ol0od60v9hr4qplk79d6eo0qe28vhp6e3i5hi9o1',
    'qed28gjvb55k8vk5jnui19r3da5u5vkidlou7n81',
    'vims25f2k62nn2somkk6h4pd6rbrt8kfi1qufm81',
]
# ParsingResult = namedtuple('ParsingResult', ['merchant', 'amount', 'date'])
# expected_results = {
#     '3al9hsal8ei25cdjlbj6bg10g9hgk5vqh6l3g1g1': ParsingResult('MAMAS MOVE - NORWELL', Decimal(56.25), date(2016, 6, 27)),
#     'qed28gjvb55k8vk5jnui19r3da5u5vkidlou7n81': ParsingResult('STARBUCKS CARD RELOAD', Decimal(25), date(2016, 6, 27)),
# }

data_dir = './sample_data/us-mantilklein-pf-emails'
for email_filename in sample_email_filenames:
    print '\n%s' % email_filename
    f = open(os.path.join(data_dir, email_filename), 'rb')
    msg = Parser().parse(f)
    subparts = [p for p in msg.walk()]
    for i, subpart in enumerate(subparts):
        print 'Subpart %d - %s' % (i, subpart.get_content_type())
        if subpart.get_content_type() == 'text/plain':
            text_payload = subpart.get_payload()

    assert text_payload is not None
    print 'Have a text_payload'
    merchant_raw = re.search(r'^Merchant: (.*)\r\n', text_payload, flags=re.MULTILINE).groups()[0]
    amount_raw = re.search(r'^Amount: (.*)\r\n', text_payload, flags=re.MULTILINE).groups()[0]
    date_raw = re.search(r'^Date: (.*)\r\n', text_payload, flags=re.MULTILINE).groups()[0]
    merchant_parsed = merchant_raw.upper().strip()
    amount_parsed = Decimal(amount_raw[1:]) if amount_raw[0] == '$' else Decimal(amount_raw)
    date_parsed = datetime.strptime(date_raw, '%B %d, %Y').date()
    print 'Raw value -> Parsed value'
    print '"%s" -> "%s"' % (merchant_raw, merchant_parsed)
    print '"%s" -> "%s"' % (amount_raw, amount_parsed)
    print '"%s" -> "%s"' % (date_raw, date_parsed)

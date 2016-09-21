import csv
from datetime import datetime
import logging
import os
import tempfile

import boto
from sqlalchemy import select

from credentials import s3_full, ml_full
from persfin import ml
from persfin import ML_BUCKET_NAME, ML_MOST_RECENT_TRANSACTIONS_FILENAME, configure_logging
from persfin.db import engine, transaction_tbl, user_tbl, account_tbl


# TODO will want to make this a scheduled job (say every week)

def create_ml_model():

    #
    # 0. Derive datasource/model/evaluation name and IDs -- the same value for all
    #
    now = datetime.utcnow()
    model_name = model_id = 'transactions-%s' % now.strftime('%Y%m%d')
    datasource_name = datasource_id = model_name
    evaluation_name = evaluation_id = model_name

    logging.info('Model/datasource/evaluation name/ID will be %s' % model_name)

    #
    # 1. Query the DB for transactions; write them to a CSV
    #

    logging.info('Querying DB for transactions, writing them to CSV')

    _, temp_fname = tempfile.mkstemp()
    outfile = open(temp_fname, 'wb')
    writer = csv.writer(outfile, quoting=csv.QUOTE_NONNUMERIC)

    writer.writerow([
        'id',
        'merchant',
        'date',
        'day_of_week',
        'weekend',
        'amount',
        'created_date',
        'account',
        'verified_by',
    ])

    s = select([transaction_tbl.c.id,
                transaction_tbl.c.merchant,
                transaction_tbl.c.date,
                transaction_tbl.c.amount,
                transaction_tbl.c.created_date,
                account_tbl.c.name.label('account_name'),
                user_tbl.c.name.label('verifier_name')
               ]) \
            .select_from(transaction_tbl
            .join(user_tbl, onclause=transaction_tbl.c.verified_by == user_tbl.c.id)
            .join(account_tbl)) \
            .where(transaction_tbl.c.is_verified)

    conn = engine.connect()
    rs = conn.execute(s)
    for row in rs:
        python_weekday, weekend = ml.weekday_fields(row.date)
        row = [row.id,
               row.merchant,
               row.date,
               python_weekday,
               weekend,
               row.amount,
               row.created_date,
               row.account_name,
               row.verifier_name]
        row = [ml.standardize(f) for f in row]
        writer.writerow(row)

    outfile.close()

    #
    # 2. Upload the CSV into S3
    #

    logging.info('Uploading CSV into S3 bucket')

    infile = open(temp_fname, 'rb')
    s3_conn = boto.connect_s3(s3_full.ACCESS_KEY_ID, s3_full.SECRET_ACCESS_KEY)
    bucket = s3_conn.get_bucket(ML_BUCKET_NAME)
    s3_key = bucket.new_key('%s.csv' % model_name)
    s3_key.metadata = {'Content-Type': 'text/csv'}
    s3_key.set_contents_from_file(infile)

    infile.close()
    os.remove(temp_fname)

    #
    # 3. Create an ML datasource from the CSV
    #

    logging.info('Creating ML datasource from the CSV')

    ml_conn = boto.connect_machinelearning(ml_full.ACCESS_KEY_ID, ml_full.SECRET_ACCESS_KEY)
    try:
        ml_conn.delete_data_source(data_source_id=model_name)
    except boto.machinelearning.exceptions.ResourceNotFoundException:
        pass

    # Obtained by using the AWS console UI
    transactions_schema = '''
    {
      "version" : "1.0",
      "rowId" : "id",
      "rowWeight" : null,
      "targetAttributeName" : "verified_by",
      "dataFormat" : "CSV",
      "dataFileContainsHeader" : true,
      "attributes" : [ {
        "attributeName" : "id",
        "attributeType" : "CATEGORICAL"
      }, {
        "attributeName" : "merchant",
        "attributeType" : "TEXT"
      }, {
        "attributeName" : "date",
        "attributeType" : "CATEGORICAL"
      }, {
        "attributeName" : "day_of_week",
        "attributeType" : "CATEGORICAL"
      }, {
        "attributeName" : "weekend",
        "attributeType" : "BINARY"
      }, {
        "attributeName" : "amount",
        "attributeType" : "NUMERIC"
      }, {
        "attributeName" : "created_date",
        "attributeType" : "TEXT"
      }, {
        "attributeName" : "account",
        "attributeType" : "CATEGORICAL"
      }, {
        "attributeName" : "verified_by",
        "attributeType" : "CATEGORICAL"
      } ],
      "excludedAttributeNames" : [ ]
    }
    '''

    ml_conn.create_data_source_from_s3(
        data_source_id=datasource_id,
        data_source_name=datasource_name,
        data_spec={
            'DataLocationS3': 's3://%s/%s.csv' % (ML_BUCKET_NAME, datasource_name),
            'DataSchema': transactions_schema,
        },
        compute_statistics=True)

    #
    # 4. Create an ML model from the datasource
    #

    logging.info('Creating ML model from the datasource')

    ml_conn.create_ml_model(
        ml_model_id=model_id,
        ml_model_name=model_name,
        ml_model_type='MULTICLASS',
        training_data_source_id=datasource_id)

    ml_conn.create_realtime_endpoint(ml_model_id=model_id)

    ml_conn.create_evaluation(
        evaluation_id=evaluation_id,
        ml_model_id=model_id,
        evaluation_data_source_id=datasource_id,
        evaluation_name=evaluation_name)

    #
    # 5. Write the name of the just-created model/datasource/evaluation to the ML_MOST_RECENT_TRANSACTIONS_FILENAME key in S3
    #

    logging.info('Writing model name to ML_MOST_RECENT_TRANSACTIONS_FILENAME in S3')

    bucket = s3_conn.get_bucket(ML_BUCKET_NAME)
    k = bucket.get_key(ML_MOST_RECENT_TRANSACTIONS_FILENAME)
    if not k:
        k = bucket.new_key(ML_MOST_RECENT_TRANSACTIONS_FILENAME)
    k.metadata = {'Content-Type': 'text/plain'}
    k.set_contents_from_string(model_name)


if __name__ == '__main__':
    configure_logging()
    create_ml_model()

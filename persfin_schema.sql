CREATE TABLE account (
    id SERIAL NOT NULL PRIMARY KEY,
    name TEXT
);

INSERT INTO account
    (name)
VALUES
    ('Discover'),
    ('USAA Checking')
;

CREATE TABLE transaction (
    id SERIAL NOT NULL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES account(id),
    merchant VARCHAR(200),
    date DATE,
    amount NUMERIC,
    email_message_id TEXT,
    source TEXT,
    created_date TIMESTAMP WITH TIME ZONE,
    is_verified BOOLEAN,
    verified_by INTEGER REFERENCES persfin_user(id),
    verified_date TIMESTAMP WITH TIME ZONE,
    is_cleared BOOLEAN
);

CREATE TABLE persfin_user (
    id SERIAL NOT NULL PRIMARY KEY,
    name TEXT UNIQUE,
    email TEXT,
    is_verifier BOOLEAN NOT NULL
);

INSERT INTO persfin_user
    (name, email, is_verifier)
VALUES
    ('Matt', 'mpklein+persfin@gmail.com', true),
    ('Ann', 'mpklein+persfin-ann@gmail.com', true)
    ('Neither/both/family', null, false)
;

CREATE TABLE verification_attempt (
    id SERIAL NOT NULL PRIMARY KEY,
    transaction_id INTEGER REFERENCES transaction(id),
    asked_of INTEGER REFERENCES persfin_user(id),
    did_verify BOOLEAN,
    attempt_sent TIMESTAMP WITH TIME ZONE,
    attempt_replied_to TIMESTAMP WITH TIME ZONE
);

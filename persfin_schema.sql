CREATE TABLE transaction (
    id SERIAL NOT NULL PRIMARY KEY,
    merchant VARCHAR(200),
    date DATE,
    amount NUMERIC,
    email_message_id TEXT,
    source TEXT,
    created_date TIMESTAMP WITH TIME ZONE,
    is_verified BOOLEAN,
    verified_by TEXT,
    verified_date TIMESTAMP WITH TIME ZONE,
    is_cleared BOOLEAN
);

CREATE TABLE users (
    email INTEGER PRIMARY KEY
);

CREATE TABLE logins (
    id SERIAL PRIMARY KEY,
    email TEXT REFERENCES users(email)
);

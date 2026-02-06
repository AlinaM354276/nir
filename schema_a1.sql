CREATE TABLE users (
    email TEXT PRIMARY KEY
);

CREATE TABLE logins (
    id SERIAL PRIMARY KEY,
    email TEXT REFERENCES users(email)
);

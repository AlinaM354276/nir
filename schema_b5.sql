CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT
);

CREATE TABLE logins (
    id INTEGER PRIMARY KEY,
    email TEXT REFERENCES users(email)
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE
);

CREATE TABLE logins (
    id INTEGER PRIMARY KEY,
    email TEXT REFERENCES users(email)
);

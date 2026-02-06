CREATE TABLE users (
    id INTEGER PRIMARY KEY
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES customers(id)
);

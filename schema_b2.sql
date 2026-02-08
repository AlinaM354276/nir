CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id)
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id)
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    CONSTRAINT fk_orders_users
        FOREIGN KEY (user_id)
        REFERENCES users(id)
);

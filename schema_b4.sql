CREATE TABLE users (
    id BIGINT PRIMARY KEY
);

CREATE TABLE orders (
    user_id INTEGER REFERENCES users(id)
);

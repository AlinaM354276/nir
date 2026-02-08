CREATE TABLE users (
    id TEXT PRIMARY KEY
);

CREATE TABLE orders (
    user_id INTEGER REFERENCES users(id)
);

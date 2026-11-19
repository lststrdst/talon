"""Disposable SQLite adapter for the order retry example."""

import sqlite3
from contextlib import closing


def create_store(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE orders ("
            "id INTEGER PRIMARY KEY, operation_key TEXT NOT NULL UNIQUE, item TEXT NOT NULL)"
        )


def _place_order(path, operation_key, item):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "INSERT INTO orders (operation_key, item) VALUES (?, ?) "
            "ON CONFLICT(operation_key) DO NOTHING",
            (operation_key, item),
        )
        order_id, = connection.execute(
            "SELECT id FROM orders WHERE operation_key = ?", (operation_key,)
        ).fetchone()
    return order_id


def submit_order(path, operation_key, item, *, acknowledge=None):
    order_id = _place_order(path, operation_key, item)
    if acknowledge is not None:
        acknowledge(order_id)
    return order_id


def read_orders(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as reader:
        return reader.execute(
            "SELECT id, operation_key, item FROM orders ORDER BY id"
        ).fetchall()

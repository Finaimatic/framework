import os
import pathlib
import sqlite3
from contextlib import contextmanager

_DB_PATH = os.environ.get(
    "DATABASE_PATH",
    str(pathlib.Path(__file__).parent / "gtmbackend.db"),
)


@contextmanager
def get_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

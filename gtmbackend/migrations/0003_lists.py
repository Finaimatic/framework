"""Migration: create lists and list_entries tables.

Run:
    python migrations/0003_lists.py
    python migrations/0003_lists.py --rollback
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db


def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def upgrade(conn) -> None:
    if not _table_exists(conn, "lists"):
        print("  creating lists ...", end=" ", flush=True)
        conn.execute("""
            CREATE TABLE lists (
                id         INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        print("done", flush=True)
    else:
        print("  skip   lists (already exists)", flush=True)

    if not _table_exists(conn, "list_entries"):
        print("  creating list_entries ...", end=" ", flush=True)
        conn.execute("""
            CREATE TABLE list_entries (
                id       INTEGER PRIMARY KEY,
                list_id  INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
                lead_id  INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                added_at TEXT DEFAULT (datetime('now')),
                UNIQUE(list_id, lead_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_list_entries_list ON list_entries (list_id)")
        print("done", flush=True)
    else:
        print("  skip   list_entries (already exists)", flush=True)

    conn.commit()


def downgrade(conn) -> None:
    for table in ("list_entries", "lists"):
        if _table_exists(conn, table):
            print(f"  dropping {table} ...", end=" ", flush=True)
            conn.execute(f"DROP TABLE {table}")
            print("done", flush=True)
        else:
            print(f"  skip   {table} (not present)", flush=True)
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    with get_db() as conn:
        label = "Downgrade" if args.rollback else "Upgrade"
        print(f"{label}: lists tables", flush=True)
        try:
            if args.rollback:
                downgrade(conn)
            else:
                upgrade(conn)
        except Exception as exc:
            conn.rollback()
            print(f"FAILED: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

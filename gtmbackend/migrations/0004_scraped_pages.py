"""Migration: create scraped_pages table."""

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
    if _table_exists(conn, "scraped_pages"):
        print("  skip   scraped_pages (already exists)", flush=True)
        return
    print("  creating scraped_pages ...", end=" ", flush=True)
    conn.execute("""
        CREATE TABLE scraped_pages (
            domain        TEXT PRIMARY KEY,
            final_url     TEXT,
            text          TEXT,
            pages_scraped INTEGER,
            scraped_at    TEXT,
            scrape_error  TEXT,
            failed_at     TEXT
        )
    """)
    conn.commit()
    print("done", flush=True)


def downgrade(conn) -> None:
    if not _table_exists(conn, "scraped_pages"):
        print("  skip   scraped_pages (not present)", flush=True)
        return
    print("  dropping scraped_pages ...", end=" ", flush=True)
    conn.execute("DROP TABLE scraped_pages")
    conn.commit()
    print("done", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    with get_db() as conn:
        print(f"{'Downgrade' if args.rollback else 'Upgrade'}: scraped_pages table")
        try:
            downgrade(conn) if args.rollback else upgrade(conn)
        except Exception as exc:
            conn.rollback()
            print(f"FAILED: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

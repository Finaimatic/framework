"""Migration: add Surveyor scoring columns to leads.

Run:
    uv run migrations/0002_scoring.py
    uv run migrations/0002_scoring.py --rollback
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db

_COLUMNS = [
    ("fit_score",       "INTEGER"),
    ("confidence",      "TEXT"),
    ("disqualified",    "INTEGER"),
    ("disqualifier",    "TEXT"),
    ("primary_signals", "TEXT"),
    ("value_blockers",  "TEXT"),
    ("score_reason",    "TEXT"),
    ("tier",            "TEXT"),
    ("scored_at",       "TEXT"),
]


def _column_exists(conn, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def upgrade(conn) -> None:
    for col, coltype in _COLUMNS:
        if _column_exists(conn, "leads", col):
            print(f"  skip   {col} (exists)")
            continue
        print(f"  adding {col} ...", end=" ", flush=True)
        conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {coltype}")
        print("done")

    print("  adding index on tier ...", end=" ", flush=True)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_tier ON leads (tier)")
    print("done")
    conn.commit()


def downgrade(conn) -> None:
    for col, _ in reversed(_COLUMNS):
        if not _column_exists(conn, "leads", col):
            print(f"  skip   {col} (not present)")
            continue
        print(f"  dropping {col} ...", end=" ", flush=True)
        conn.execute(f"ALTER TABLE leads DROP COLUMN {col}")
        print("done")
    conn.execute("DROP INDEX IF EXISTS idx_leads_tier")
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    with get_db() as conn:
        label = "Downgrade" if args.rollback else "Upgrade"
        print(f"{label}: scoring columns", flush=True)
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

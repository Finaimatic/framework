"""Print a summary of the current database contents.

Usage:
    uv run scripts/show_db.py
    uv run scripts/show_db.py --sample 5
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db


def _section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def show(sample: int) -> None:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        print(f"Total leads: {total}")

        _section("By import batch")
        for r in conn.execute(
            "SELECT import_name, COUNT(*) n FROM leads GROUP BY import_name ORDER BY n DESC"
        ).fetchall():
            print(f"  {r['n']:>5}  {r['import_name']}")

        _section("By country (top 10)")
        for r in conn.execute(
            "SELECT lead_country, COUNT(*) n FROM leads GROUP BY lead_country ORDER BY n DESC LIMIT 10"
        ).fetchall():
            print(f"  {r['n']:>5}  {r['lead_country'] or '(blank)'}")

        _section("By seniority")
        for r in conn.execute(
            "SELECT seniority, COUNT(*) n FROM leads GROUP BY seniority ORDER BY n DESC"
        ).fetchall():
            print(f"  {r['n']:>5}  {r['seniority'] or '(blank)'}")

        _section("By industry (top 10)")
        for r in conn.execute(
            "SELECT industry, COUNT(*) n FROM leads GROUP BY industry ORDER BY n DESC LIMIT 10"
        ).fetchall():
            print(f"  {r['n']:>5}  {r['industry'] or '(blank)'}")

        has_email = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''"
        ).fetchone()[0]
        has_linkedin = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE linkedin_link IS NOT NULL AND linkedin_link != ''"
        ).fetchone()[0]
        _section("Coverage")
        print(f"  email:    {has_email:>5} / {total}  ({100*has_email//total if total else 0}%)")
        print(f"  linkedin: {has_linkedin:>5} / {total}  ({100*has_linkedin//total if total else 0}%)")

        if sample:
            _section(f"Sample ({sample} rows)")
            for r in conn.execute(
                "SELECT full_name, title, company_name, lead_country, email FROM leads LIMIT ?",
                (sample,),
            ).fetchall():
                print(f"  {r['full_name'] or '?':<30} {r['title'] or '':<25} {r['company_name'] or '':<25} {r['lead_country'] or ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show database summary")
    parser.add_argument("--sample", type=int, default=0, metavar="N", help="Print N sample rows")
    args = parser.parse_args()
    show(args.sample)


if __name__ == "__main__":
    main()

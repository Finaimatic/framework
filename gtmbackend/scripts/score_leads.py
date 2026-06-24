"""Score scraped company pages against an ICP spec using Surveyor.agent.

Usage:
    uv run scripts/score_leads.py --spec specs/icp_spec.yaml
    uv run scripts/score_leads.py --spec specs/icp_spec.yaml --list 3
    uv run scripts/score_leads.py --spec specs/icp_spec.yaml --limit 20
    uv run scripts/score_leads.py --spec specs/icp_spec.yaml --all

Requires OPENROUTER_API_KEY env var or [openrouter] api_key in config.toml.
Scraped content must already be in scraped_pages table (run scrape_leads.py first).
Run migrations/0002_scoring.py and 0004_scraped_pages.py before the first run.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import tomllib
from datetime import datetime

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db

_CFG_PATH = pathlib.Path(__file__).parent.parent / "config.toml"
_OR_URL   = "https://openrouter.ai/api/v1/chat/completions"


def _load_api_key() -> str:
    val = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if val:
        return val
    try:
        return tomllib.loads(_CFG_PATH.read_text())["openrouter"]["api_key"]
    except (KeyError, FileNotFoundError):
        return ""

_AGENT_FILE  = pathlib.Path(__file__).parent.parent / "agents" / "surveyor.agent"
_OUTPUT_FILE = pathlib.Path(__file__).parent.parent / "scoring.txt"
_MODEL       = "anthropic/claude-haiku-4-5"


def _normalize_domain(url: str) -> str:
    s = url.strip()
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    return s.rstrip("/").split("?")[0].split("#")[0].split("/")[0].lower()


def _extract_system_prompt(agent_text: str) -> str:
    lines = agent_text.splitlines()
    in_block = False
    result: list[str] = []
    for line in lines:
        if line.rstrip() == "```":
            if not in_block:
                in_block = True
                continue
            else:
                break
        if in_block:
            result.append(line)
    if not result:
        raise ValueError(f"No ``` block found in {_AGENT_FILE}")
    return "\n".join(result)


def _get_list_lead_ids(list_id: int) -> list[int]:
    with get_db() as conn:
        list_row = conn.execute("SELECT name FROM lists WHERE id = ?", (list_id,)).fetchone()
        if list_row is None:
            print(f"List {list_id} not found.", file=sys.stderr)
            sys.exit(1)
        rows = conn.execute(
            "SELECT lead_id FROM list_entries WHERE list_id = ?", (list_id,)
        ).fetchall()
    print(f"List: {list_row['name']} ({len(rows)} leads)", flush=True)
    return [row["lead_id"] for row in rows]


def _build_domain_index(lead_ids: list[int] | None = None) -> dict[str, list[int]]:
    """Map normalized domain → [lead_ids] for leads with a website."""
    with get_db() as conn:
        if lead_ids is not None:
            placeholders = ",".join("?" * len(lead_ids))
            rows = conn.execute(
                f"SELECT id, company_website_short FROM leads "
                f"WHERE id IN ({placeholders}) "
                f"AND company_website_short IS NOT NULL AND company_website_short != ''",
                lead_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, company_website_short FROM leads "
                "WHERE company_website_short IS NOT NULL AND company_website_short != ''"
            ).fetchall()
    index: dict[str, list[int]] = {}
    for row in rows:
        domain = _normalize_domain(row["company_website_short"])
        if domain:
            index.setdefault(domain, []).append(row["id"])
    return index


def _load_scraped(domains: list[str] | None = None) -> list[tuple[str, str]]:
    """Return (domain, text) pairs from scraped_pages. Filters to domains if provided."""
    with get_db() as conn:
        if domains:
            placeholders = ",".join("?" * len(domains))
            rows = conn.execute(
                f"SELECT domain, text FROM scraped_pages "
                f"WHERE text IS NOT NULL AND domain IN ({placeholders})",
                domains,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT domain, text FROM scraped_pages WHERE text IS NOT NULL"
            ).fetchall()
    return [(row["domain"], row["text"]) for row in rows]


def _load_scored_domains() -> set[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT company_website_short FROM leads "
            "WHERE scored_at IS NOT NULL AND company_website_short IS NOT NULL AND company_website_short != ''"
        ).fetchall()
    return {_normalize_domain(row["company_website_short"]) for row in rows}


def _score_one(api_key: str, system_prompt: str, retries: int = 3) -> dict:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Score this company for ICP fit."},
    ]
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.post(
                _OR_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": _MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 1024},
                timeout=90,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            return json.loads(raw)
        except Exception as exc:
            if attempt == retries:
                raise
            time.sleep(3 * attempt)


def _write_scores(results: list[dict], domain_index: dict[str, list[int]]) -> None:
    with get_db() as conn:
        updated = 0
        for r in results:
            domain = r["_domain"]
            for lead_id in domain_index.get(domain, []):
                conn.execute(
                    """UPDATE leads SET
                        fit_score       = ?,
                        confidence      = ?,
                        disqualified    = ?,
                        disqualifier    = ?,
                        primary_signals = ?,
                        value_blockers  = ?,
                        score_reason    = ?,
                        tier            = ?,
                        scored_at       = datetime('now')
                    WHERE id = ?""",
                    (
                        r.get("fit_score"),
                        r.get("confidence"),
                        1 if r.get("disqualified") else 0,
                        r.get("disqualifier"),
                        json.dumps(r.get("primary_signals", [])),
                        json.dumps(r.get("value_blockers", [])),
                        r.get("reason"),
                        r.get("tier"),
                        lead_id,
                    ),
                )
                updated += conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    print(f"DB — updated {updated:,} lead rows", flush=True)


def _write_report(results: list[dict]) -> None:
    sorted_results = sorted(results, key=lambda r: -(r.get("fit_score") or 0))
    lines = [
        "SCORING REPORT — Surveyor ICP Fit",
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Model     : {_MODEL}",
        f"Evaluated : {len(sorted_results)} companies",
        "=" * 60,
        "",
    ]
    for r in sorted_results:
        lines += [
            f"Domain    : {r.get('_domain', '?')}",
            f"Score     : {r.get('fit_score', '?')}/10  tier={r.get('tier', '?')}  confidence={r.get('confidence', '?')}",
            f"Disqual.  : {r.get('disqualified')}  ({r.get('disqualifier') or 'none'})",
            f"Signals   : {', '.join(r.get('primary_signals', [])) or 'none'}",
            f"Blockers  : {', '.join(r.get('value_blockers', [])) or 'none'}",
            f"Reason    : {r.get('reason', '')}",
            "",
            "-" * 60,
            "",
        ]
    _OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report → {_OUTPUT_FILE}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score leads with Surveyor.agent")
    parser.add_argument("--spec", required=True, metavar="FILE")
    parser.add_argument("--list", dest="list_id", type=int, metavar="LIST_ID",
                        help="Only score leads in this list")
    parser.add_argument("--limit", type=int, metavar="N")
    parser.add_argument("--all", dest="all_mode", action="store_true",
                        help="Re-score already-scored companies")
    args = parser.parse_args()

    spec_path = pathlib.Path(args.spec)
    if not spec_path.exists():
        print(f"Spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    agent_text    = _AGENT_FILE.read_text(encoding="utf-8")
    system_prompt = _extract_system_prompt(agent_text)
    icp_spec      = spec_path.read_text(encoding="utf-8")

    # Resolve lead IDs and domain index
    if args.list_id:
        lead_ids     = _get_list_lead_ids(args.list_id)
        domain_index = _build_domain_index(lead_ids)
    else:
        domain_index = _build_domain_index()

    if not domain_index:
        print("No leads with websites found.", file=sys.stderr)
        sys.exit(1)

    # Load scraped content for the relevant domains
    target_domains = list(domain_index.keys())
    scraped = _load_scraped(target_domains)

    if not scraped:
        print("No scraped content found for these leads. Run scrape_leads.py first.", file=sys.stderr)
        sys.exit(1)

    # Filter already scored unless --all
    if not args.all_mode:
        scored = _load_scored_domains()
        todo = [(d, t) for d, t in scraped if d not in scored]
    else:
        todo = scraped

    if args.limit:
        todo = todo[: args.limit]

    skipped = len(scraped) - len(todo)
    print(f"To score: {len(todo)}  |  already scored/skipped: {skipped}", flush=True)
    print(f"Model: {_MODEL}  |  Spec: {spec_path.name}\n", flush=True)

    if not todo:
        print("Nothing to score.")
        return

    api_key = _load_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set and no [openrouter] api_key in config.toml", file=sys.stderr)
        sys.exit(1)

    results: list[dict] = []

    for i, (domain, text) in enumerate(todo, 1):
        pct    = i / len(todo) * 100
        filled = int(20 * i / len(todo))
        bar    = "█" * filled + "░" * (20 - filled)
        content = text[:6000]

        print(f"[{bar}] {pct:5.1f}%  ({i}/{len(todo)})  {domain}", flush=True)

        filled_prompt = (
            system_prompt
            .replace("{icp_spec}", icp_spec)
            .replace("{company}", domain)
            .replace("{content}", content)
        )

        try:
            result = _score_one(api_key, filled_prompt)
            result["_domain"] = domain
            score = result.get("fit_score", "?")
            tier  = result.get("tier", "?")
            print(f"  score={score}/10 tier={tier}  {result.get('reason', '')[:80]}", flush=True)
            results.append(result)
        except Exception as exc:
            print(f"  [error] {exc}", file=sys.stderr)
            results.append({
                "_domain": domain,
                "fit_score": None,
                "tier": "skip",
                "reason": f"scoring error: {exc}",
                "confidence": "low",
                "disqualified": False,
                "primary_signals": [],
                "value_blockers": [],
            })

    if results:
        _write_scores(results, domain_index)
    _write_report(results)


if __name__ == "__main__":
    main()

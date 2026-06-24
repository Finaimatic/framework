"""Score scraped company pages against an ICP spec using Surveyor.agent.

Usage:
    uv run scripts/score_leads.py --spec specs/icp_spec.example.yaml
    uv run scripts/score_leads.py --spec specs/icp_spec.example.yaml --limit 20
    uv run scripts/score_leads.py --spec specs/icp_spec.example.yaml --all

Requires ANTHROPIC_API_KEY.
Scraped content must already exist in scraped/*.txt (run scrape_leads.py first).
Run migrations/0002_scoring.py before the first score run.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime

import anthropic

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db

_SCRAPED_DIR  = pathlib.Path(__file__).parent.parent / "scraped"
_AGENT_FILE   = pathlib.Path(__file__).parent.parent / "agents" / "surveyor.agent"
_OUTPUT_FILE  = pathlib.Path(__file__).parent.parent / "scoring.txt"
_MODEL        = "claude-haiku-4-5"


def _extract_system_prompt(agent_text: str) -> str:
    """Pull the content between the first ```...``` block in a .agent file."""
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


def url_to_slug(url: str) -> str:
    s = url.strip()
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    s = s.rstrip("/").split("?")[0].split("#")[0]
    return s.replace("/", "_").replace(".", "_")


def _build_slug_index() -> dict[str, list[int]]:
    """Map url_to_slug(company_website_short) → list of lead IDs."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, company_website_short FROM leads "
            "WHERE company_website_short IS NOT NULL AND company_website_short != ''"
        ).fetchall()
    index: dict[str, list[int]] = {}
    for row in rows:
        slug = url_to_slug(row["company_website_short"])
        index.setdefault(slug, []).append(row["id"])
    return index


def _load_scored_slugs() -> set[str]:
    """Return slugs for companies that already have a score in the DB."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT company_website_short FROM leads WHERE scored_at IS NOT NULL"
        ).fetchall()
    slugs: set[str] = set()
    for row in rows:
        if row["company_website_short"]:
            slugs.add(url_to_slug(row["company_website_short"]))
    return slugs


def _score_one(client: anthropic.Anthropic, system_prompt: str, company: str, content: str) -> dict:
    """Call Surveyor and return parsed JSON."""
    response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Score this company for ICP fit."}],
    )
    raw = response.content[0].text.strip()
    # strip any accidental markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def _write_scores(results: list[dict], slug_index: dict[str, list[int]]) -> None:
    with get_db() as conn:
        updated = 0
        for r in results:
            slug = r["_slug"]
            lead_ids = slug_index.get(slug, [])
            for lead_id in lead_ids:
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
    print(f"DB    — updated {updated:,} lead rows")


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
            f"Company   : {r.get('company', r.get('_slug', '?'))}",
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
    print(f"Report → {_OUTPUT_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score leads with Surveyor.agent")
    parser.add_argument("--spec", required=True, metavar="FILE", help="Path to ICP spec YAML file")
    parser.add_argument("--limit", type=int, metavar="N")
    parser.add_argument("--all", dest="all_mode", action="store_true", help="Re-score already-scored companies")
    args = parser.parse_args()

    spec_path = pathlib.Path(args.spec)
    if not spec_path.exists():
        print(f"Spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    agent_text    = _AGENT_FILE.read_text(encoding="utf-8")
    system_prompt = _extract_system_prompt(agent_text)
    icp_spec      = spec_path.read_text(encoding="utf-8")

    files = sorted(_SCRAPED_DIR.glob("*.txt"))
    if not files:
        print(f"No scraped files in {_SCRAPED_DIR}. Run scrape_leads.py first.", file=sys.stderr)
        sys.exit(1)

    slug_index = _build_slug_index()

    if not args.all_mode:
        scored = _load_scored_slugs()
        todo = [f for f in files if f.stem not in scored]
    else:
        todo = files

    # Deduplicate: if two URL forms map to the same leads, only score once
    seen_sets: set[frozenset] = set()
    deduped: list[pathlib.Path] = []
    for f in todo:
        lead_set = frozenset(slug_index.get(f.stem, []))
        if lead_set and lead_set in seen_sets:
            print(f"  [skip dup] {f.name}")
            continue
        if lead_set:
            seen_sets.add(lead_set)
        deduped.append(f)
    todo = deduped

    if args.limit:
        todo = todo[: args.limit]

    skipped = len(files) - len(todo)
    print(f"To score: {len(todo)}  |  already scored/skipped: {skipped}")
    print(f"Model: {_MODEL}  |  Spec: {spec_path.name}\n")

    client = anthropic.Anthropic()
    results: list[dict] = []

    for i, f in enumerate(todo, 1):
        pct    = i / len(todo) * 100
        filled = int(20 * i / len(todo))
        bar    = "█" * filled + "░" * (20 - filled)
        company_name = f.stem.replace("_", ".")
        content = f.read_text(encoding="utf-8")[:6000]

        print(f"[{bar}] {pct:5.1f}%  ({i}/{len(todo)})  {f.stem}", flush=True)

        # Substitute template vars — use explicit replace to avoid issues
        # with JSON brace literals in the system prompt
        filled_prompt = (
            system_prompt
            .replace("{icp_spec}", icp_spec)
            .replace("{company}", company_name)
            .replace("{content}", content)
        )

        try:
            result = _score_one(client, filled_prompt, company_name, content)
            result["_slug"] = f.stem
            score = result.get("fit_score", "?")
            tier  = result.get("tier", "?")
            print(f"  score={score}/10 tier={tier}  {result.get('reason', '')[:80]}", flush=True)
            results.append(result)
        except Exception as exc:
            print(f"  [error] {exc}", file=sys.stderr)
            results.append({
                "_slug": f.stem,
                "company": company_name,
                "fit_score": None,
                "tier": "skip",
                "reason": f"scoring error: {exc}",
                "confidence": "low",
                "disqualified": False,
                "primary_signals": [],
                "value_blockers": [],
            })

    if results:
        _write_scores(results, slug_index)
    _write_report(results)


if __name__ == "__main__":
    main()

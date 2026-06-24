"""Build an Apollo.io People search URL from ICP filters.

Usage:
    # From a JSON filters dict
    uv run scripts/generate_apollo_link.py --filters '{"industries": ["Computer Software"], "seniorities": ["founder", "c_suite"], "locations": ["United States"]}'

    # From a natural-language description (calls claude-haiku-4-5 via icp_filter.agent)
    uv run scripts/generate_apollo_link.py --description "B2B SaaS founders in the US with 10-200 employees"
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from urllib.parse import quote_plus

_APOLLO_INDUSTRY_IDS: dict[str, str] = {
    "Information Technology and Services": "5567cd4773696439b10b0000",
    "Construction":                         "5567cd4773696439dd350000",
    "Marketing and Advertising":            "5567cd467369644d39040000",
    "Real Estate":                          "5567cd477369645401010000",
    "Health, Wellness and Fitness":         "5567cddb7369644d250c0000",
    "Management Consulting":                "5567cdd47369643dbf260000",
    "Computer Software":                    "5567cd4e7369643b70010000",
    "Internet":                             "5567cd4d736964397e020000",
    "Retail":                               "5567ced173696450cb580000",
    "Financial Services":                   "5567cdd67369643e64020000",
    "Consumer Services":                    "5567d1127261697f2b1d0000",
    "Hospital and Health Care":             "5567cdde73696439812c0000",
    "Automotive":                           "5567cdf27369644cfd800000",
    "Restaurants":                          "5567e0e0736964198de70700",
    "Education Management":                 "5567ce9e736964540d540000",
    "Food and Beverages":                   "5567ce1e7369643b806a0000",
    "Design":                               "5567cdbc73696439d90b0000",
    "Hospitality":                          "5567ce9d7369643bc19c0000",
    "Accounting":                           "5567ce1f7369643b78570000",
    "Events Services":                      "5567cd8e7369645409450000",
}


def build_url(filters: dict) -> tuple[str, list[str]]:
    """Build Apollo People search URL from filter dict.

    Returns (url, unknown_industries) where unknown_industries lists any
    industry names that had no known Apollo tag ID.
    """
    params: list[str] = []
    unknown_industries: list[str] = []
    for title in filters.get("titles", []):
        params.append(f"personTitles[]={quote_plus(title)}")
    for seniority in filters.get("seniorities", []):
        params.append(f"personSeniorities[]={quote_plus(seniority)}")
    for loc in filters.get("locations", []):
        params.append(f"personLocations[]={quote_plus(loc)}")
    for rng in filters.get("employeeRanges", []):
        params.append(f"organizationNumEmployeesRanges[]={quote_plus(rng)}")
    for industry in filters.get("industries", []):
        tag_id = _APOLLO_INDUSTRY_IDS.get(industry)
        if tag_id:
            params.append(f"organizationIndustryTagIds[]={tag_id}")
        else:
            unknown_industries.append(industry)
    params += ["sortAscending=false", "sortByField=%5Bnone%5D", "recommendationConfigId=score"]
    return "https://app.apollo.io/#/people?" + "&".join(params), unknown_industries


def _filters_from_description(description: str) -> dict:
    """Call claude-haiku-4-5 with the icp_filter agent prompt to extract filters."""
    import anthropic

    agent_path = pathlib.Path(__file__).parent.parent / "agents" / "icp_filter.agent"
    system_prompt = agent_path.read_text()

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": description}],
    )
    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: LLM returned invalid JSON:\n{raw}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Apollo.io People search URL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--filters",
        metavar="JSON",
        help='JSON filter object, e.g. \'{"industries": [...], "seniorities": [...]}\'',
    )
    group.add_argument(
        "--description",
        metavar="TEXT",
        help="Natural-language ICP description; calls claude-haiku-4-5 to extract filters",
    )
    args = parser.parse_args()

    if args.filters:
        try:
            filters = json.loads(args.filters)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid JSON in --filters: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
    else:
        print("Calling LLM to extract filters...", file=sys.stderr)
        filters = _filters_from_description(args.description)
        print("Extracted filters:", file=sys.stderr)
        print(json.dumps(filters, indent=2), file=sys.stderr)
        if filters.get("notes"):
            print(f"\nNotes: {filters['notes']}", file=sys.stderr)
        print(file=sys.stderr)

    url, unknown = build_url(filters)

    if unknown:
        print(f"Warning: no Apollo tag ID for: {', '.join(unknown)}", file=sys.stderr)

    print(url)


if __name__ == "__main__":
    main()

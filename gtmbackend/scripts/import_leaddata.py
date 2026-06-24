"""Import all CSVs from the leaddata/ folder.

Usage:
    uv run scripts/import_leaddata.py
    uv run scripts/import_leaddata.py --dir path/to/other/folder
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from import_leads import import_csv

_DEFAULT_DIR = pathlib.Path(__file__).parent.parent / "leaddata"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import all CSVs from leaddata/")
    parser.add_argument(
        "--dir",
        type=pathlib.Path,
        default=_DEFAULT_DIR,
        help=f"Folder to scan (default: {_DEFAULT_DIR})",
    )
    args = parser.parse_args()

    csvs = sorted(args.dir.glob("*.csv"))
    if not csvs:
        print(f"No CSV files found in {args.dir}")
        sys.exit(1)

    print(f"Found {len(csvs)} file(s) in {args.dir}\n")
    for path in csvs:
        import_name = path.stem
        print(f"[{path.name}]  import_name='{import_name}'")
        import_csv(path, import_name)
        print()


if __name__ == "__main__":
    main()

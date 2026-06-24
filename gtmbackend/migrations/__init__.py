"""Run all migrations in order. Each upgrade() is idempotent."""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))

from db import get_db  # noqa: E402


def run_all() -> None:
    migration_files = sorted(_HERE.glob("[0-9]*.py"))
    with get_db() as conn:
        for path in migration_files:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if hasattr(mod, "upgrade"):
                mod.upgrade(conn)

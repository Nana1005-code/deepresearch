"""Backfill personal-graph start times without changing import timestamps."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from research_square.store import ResearchSquareStore  # noqa: E402


def main() -> None:
    store = ResearchSquareStore()
    history_path = Path(os.getenv("RESEARCH_DB_PATH") or ROOT / "backend" / "data" / "research.sqlite3")
    run_times: dict[str, str] = {}
    if history_path.exists():
        with sqlite3.connect(history_path) as history:
            for run_id, payload in history.execute("SELECT id,data FROM runs"):
                try:
                    created_at = json.loads(payload).get("created_at")
                except (TypeError, json.JSONDecodeError):
                    created_at = None
                if created_at:
                    run_times[run_id] = created_at

    user_updated = sample_updated = 0
    now = datetime.now(timezone.utc)
    with store.connect() as db:
        rows = db.execute("""SELECT id,source_run_id,data_origin,published_at
            FROM public_researches ORDER BY id""").fetchall()
        for row in rows:
            started_at = None
            if row["data_origin"] == "user":
                started_at = run_times.get(row["source_run_id"])
                if started_at:
                    user_updated += 1
            elif row["data_origin"] == "sample":
                # A fixed permutation spreads sample starts across 330 days,
                # avoiding identical colours while remaining reproducible.
                started_at = (now - timedelta(days=(row["id"] * 97) % 330)).isoformat()
                sample_updated += 1
            db.execute("UPDATE public_researches SET research_started_at=? WHERE id=?",
                       (started_at or row["published_at"], row["id"]))
    store.rebuild_analytics()
    print(json.dumps({"ok": True, "user_records": user_updated,
                      "sample_records": sample_updated, "database": str(store.path)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

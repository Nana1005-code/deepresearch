"""Remove generated Research Square records while preserving real publications.

Targets are identified by explicit generator markers (`seed-*`, `[模拟]`,
`sim-user-*`, `load-user-*`, and source=`seed`). OpenAlex tables and ordinary
user publications are never selected. A consistent SQLite backup is created
before deletion unless --no-backup is supplied.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from research_square.store import ResearchSquareStore  # noqa: E402


def snapshot(store: ResearchSquareStore) -> dict[str, int]:
    with store.connect() as db:
        return {
            "synthetic_researches": db.execute("""SELECT COUNT(*) FROM public_researches
                WHERE source_run_id LIKE 'seed-%' OR title LIKE '[模拟] %'""").fetchone()[0],
            "real_public_researches": db.execute("""SELECT COUNT(*) FROM public_researches
                WHERE source_run_id NOT LIKE 'seed-%' AND title NOT LIKE '[模拟] %'""").fetchone()[0],
            "synthetic_events": db.execute("""SELECT COUNT(*) FROM research_events e
                LEFT JOIN public_researches r ON r.id=e.research_id
                WHERE r.source_run_id LIKE 'seed-%' OR e.event_id LIKE 'seed-event-%'
                   OR e.metadata_json LIKE '%\"synthetic\":true%'""").fetchone()[0],
            "synthetic_users": db.execute("""SELECT COUNT(*) FROM users
                WHERE public_id LIKE 'sim-user-%' OR public_id LIKE 'load-user-%'""").fetchone()[0],
            "community_topics": db.execute("SELECT COUNT(*) FROM topics").fetchone()[0],
            "openalex_works": db.execute("SELECT COUNT(*) FROM openalex_works").fetchone()[0],
        }


def backup_database(store: ResearchSquareStore) -> Path:
    directory = store.path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"research_square-before-clear-synthetic-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    source_db = sqlite3.connect(store.path, timeout=30)
    target_db = sqlite3.connect(target)
    try:
        source_db.backup(target_db)
    finally:
        target_db.close()
        source_db.close()
    return target


def clear(store: ResearchSquareStore) -> dict[str, int]:
    with store.connect() as db:
        # Foreign-key cascades remove research_topics, events, likes and
        # favorites attached to generated publications.
        deleted_researches = db.execute("""DELETE FROM public_researches
            WHERE source_run_id LIKE 'seed-%' OR title LIKE '[模拟] %'""").rowcount
        db.execute("""DELETE FROM research_events WHERE event_id LIKE 'seed-event-%'
            OR metadata_json LIKE '%\"synthetic\":true%'""")
        db.execute("DELETE FROM topic_aliases WHERE source='seed'")
        db.execute("DELETE FROM topic_domains WHERE source='seed'")
        db.execute("DELETE FROM topics WHERE NOT EXISTS(SELECT 1 FROM research_topics rt WHERE rt.topic_id=topics.id)")
        deleted_users = db.execute("""DELETE FROM users
            WHERE (public_id LIKE 'sim-user-%' OR public_id LIKE 'load-user-%')
              AND NOT EXISTS(SELECT 1 FROM public_researches r WHERE r.owner_id=users.id)
              AND NOT EXISTS(SELECT 1 FROM research_events e WHERE e.user_id=users.id)
              AND NOT EXISTS(SELECT 1 FROM research_likes l WHERE l.user_id=users.id)
              AND NOT EXISTS(SELECT 1 FROM research_favorites f WHERE f.user_id=users.id)""").rowcount
    store.rebuild_analytics()
    return {"deleted_researches": deleted_researches, "deleted_users": deleted_users}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Required confirmation for deletion")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()
    store = ResearchSquareStore()
    before = snapshot(store)
    print({"before": before, "database": str(store.path)}, flush=True)
    if not args.yes:
        raise SystemExit("未执行删除。确认范围后请增加 --yes。")
    backup = None if args.no_backup else backup_database(store)
    deleted = clear(store)
    after = snapshot(store)
    print({"ok": True, **deleted, "after": after,
           "backup": str(backup) if backup else None}, flush=True)


if __name__ == "__main__":
    main()

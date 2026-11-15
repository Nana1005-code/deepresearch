"""Import OpenAlex metadata into isolated real-data tables.

The importer never writes to public_researches, topics, or synthetic seed data.
A free OpenAlex API key is required when --limit is greater than 100 because
cursor pagination past the first page requires authentication.

Example:
  $env:OPENALEX_API_KEY="your-free-key"
  python scripts/research_square/import_openalex.py --limit 5000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
load_dotenv(ROOT / "backend" / ".env")

from research_square.store import ResearchSquareStore, utcnow  # noqa: E402

API_URL = "https://api.openalex.org/works"
DEFAULT_FILTER = (
    f"from_publication_date:2024-01-01,to_publication_date:{date.today().isoformat()},"
    "has_abstract:true,type:article|review|preprint"
)
SELECT_FIELDS = ",".join([
    "id", "doi", "title", "abstract_inverted_index", "publication_date", "publication_year",
    "type", "language", "primary_location", "cited_by_count", "open_access", "authorships",
    "topics", "primary_topic", "updated_date",
])


def short_id(value: str | None) -> str | None:
    return value.rstrip("/").rsplit("/", 1)[-1] if value else None


def reconstruct_abstract(inverted: dict | None) -> str | None:
    if not inverted:
        return None
    positions = [(position, word) for word, indexes in inverted.items() for position in indexes]
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def nested_name(value: dict | None) -> tuple[str | None, str | None]:
    value = value or {}
    return short_id(value.get("id")), value.get("display_name")


def upsert_page(store: ResearchSquareStore, works: list[dict]) -> int:
    stamp = utcnow()
    with store.connect() as db:
        for work in works:
            openalex_id = short_id(work.get("id"))
            if not openalex_id or not work.get("title"):
                continue
            location = work.get("primary_location") or {}
            source = location.get("source") or {}
            open_access = work.get("open_access") or {}
            authors = [
                {"id": short_id((entry.get("author") or {}).get("id")),
                 "name": (entry.get("author") or {}).get("display_name")}
                for entry in work.get("authorships") or [] if (entry.get("author") or {}).get("display_name")
            ]
            db.execute("""INSERT INTO openalex_works(
                openalex_id,doi,title,abstract,publication_date,publication_year,work_type,language,
                source_name,landing_page_url,cited_by_count,is_oa,oa_url,authors_json,
                openalex_updated_at,imported_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(openalex_id) DO UPDATE SET
                doi=excluded.doi,title=excluded.title,abstract=excluded.abstract,
                publication_date=excluded.publication_date,publication_year=excluded.publication_year,
                work_type=excluded.work_type,language=excluded.language,source_name=excluded.source_name,
                landing_page_url=excluded.landing_page_url,cited_by_count=excluded.cited_by_count,
                is_oa=excluded.is_oa,oa_url=excluded.oa_url,authors_json=excluded.authors_json,
                openalex_updated_at=excluded.openalex_updated_at,updated_at=excluded.updated_at""", (
                openalex_id, work.get("doi"), work["title"], reconstruct_abstract(work.get("abstract_inverted_index")),
                work.get("publication_date"), work.get("publication_year"), work.get("type"), work.get("language"),
                source.get("display_name"), location.get("landing_page_url"), int(work.get("cited_by_count") or 0),
                int(bool(open_access.get("is_oa"))), open_access.get("oa_url"),
                json.dumps(authors, ensure_ascii=False), work.get("updated_date"), stamp, stamp,
            ))
            work_id = db.execute("SELECT id FROM openalex_works WHERE openalex_id=?", (openalex_id,)).fetchone()[0]
            db.execute("DELETE FROM openalex_work_topics WHERE work_id=?", (work_id,))
            primary_id = short_id((work.get("primary_topic") or {}).get("id"))
            for rank, topic in enumerate((work.get("topics") or [])[:3], 1):
                topic_openalex_id = short_id(topic.get("id"))
                if not topic_openalex_id or not topic.get("display_name"):
                    continue
                subfield_id, subfield_name = nested_name(topic.get("subfield"))
                field_id, field_name = nested_name(topic.get("field"))
                domain_id, domain_name = nested_name(topic.get("domain"))
                db.execute("""INSERT INTO openalex_topics(
                    openalex_id,display_name,subfield_id,subfield_name,field_id,field_name,
                    domain_id,domain_name,imported_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(openalex_id) DO UPDATE SET display_name=excluded.display_name,
                    subfield_id=excluded.subfield_id,subfield_name=excluded.subfield_name,
                    field_id=excluded.field_id,field_name=excluded.field_name,
                    domain_id=excluded.domain_id,domain_name=excluded.domain_name,updated_at=excluded.updated_at""",
                    (topic_openalex_id, topic["display_name"], subfield_id, subfield_name, field_id, field_name,
                     domain_id, domain_name, stamp, stamp))
                topic_id = db.execute("SELECT id FROM openalex_topics WHERE openalex_id=?", (topic_openalex_id,)).fetchone()[0]
                is_primary = int(topic_openalex_id == primary_id or rank == 1)
                db.execute("""INSERT INTO openalex_work_topics(work_id,topic_id,score,topic_rank,is_primary)
                    VALUES(?,?,?,?,?)""", (work_id, topic_id, float(topic.get("score") or 0), rank, is_primary))
                if domain_id and domain_name:
                    db.execute("""INSERT OR REPLACE INTO openalex_topic_domains(
                        topic_id,domain_slug,domain_name,relevance_score,is_primary,source,confidence,review_status)
                        VALUES(?,?,?,?,?,'openalex',1,'approved')""",
                        (topic_id, domain_id.casefold(), domain_name, 1.0, is_primary))
    return len(works)


def fetch_page(client: httpx.Client, params: dict, attempts: int = 5) -> dict:
    for attempt in range(attempts):
        response = client.get(API_URL, params=params)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429 or response.status_code >= 500:
            wait = min(30, int(response.headers.get("Retry-After", 2 ** attempt)))
            time.sleep(max(1, wait))
            continue
        raise RuntimeError(f"OpenAlex 返回 HTTP {response.status_code}：{response.text[:300]}")
    raise RuntimeError("OpenAlex 连续重试后仍不可用")


def run_import(limit: int, filter_value: str, search: str | None, api_key: str | None):
    if limit > 100 and not api_key:
        raise SystemExit("导入超过 100 条需要免费的 OPENALEX_API_KEY；无需充值。请先在 OpenAlex 注册并设置环境变量。")
    store = ResearchSquareStore()
    run_id = uuid4().hex
    started = utcnow()
    settings = {"filter": filter_value, "search": search, "requested_at": date.today().isoformat()}
    with store.connect() as db:
        db.execute("""INSERT INTO openalex_import_runs(
            public_id,requested_limit,status,filter_json,cursor,started_at)
            VALUES(?,?,'running',?,'*',?)""", (run_id, limit, json.dumps(settings, ensure_ascii=False), started))
    imported = 0
    cursor = "*"
    total_cost = 0.0
    try:
        with httpx.Client(timeout=60, headers={"User-Agent": "deepresearch-local/0.1"}) as client:
            while imported < limit and cursor:
                per_page = min(100, limit - imported)
                params = {"filter": filter_value, "per_page": per_page, "cursor": cursor,
                          "select": SELECT_FIELDS, "sort": "publication_date:desc"}
                if search: params["search"] = search
                if api_key: params["api_key"] = api_key
                payload = fetch_page(client, params)
                results = payload.get("results") or []
                if not results:
                    break
                imported += upsert_page(store, results)
                meta = payload.get("meta") or {}
                cursor = meta.get("next_cursor")
                total_cost += float(meta.get("cost_usd") or meta.get("cost") or 0)
                with store.connect() as db:
                    db.execute("""UPDATE openalex_import_runs SET imported_count=?,cursor=?,cost_usd=?
                        WHERE public_id=?""", (imported, cursor, total_cost, run_id))
                print({"imported": imported, "requested": limit, "reported_cost_usd": round(total_cost, 6)})
        with store.connect() as db:
            db.execute("""UPDATE openalex_import_runs SET status='completed',imported_count=?,cursor=?,
                cost_usd=?,completed_at=? WHERE public_id=?""",
                (imported, cursor, total_cost, utcnow(), run_id))
    except Exception as exc:
        with store.connect() as db:
            db.execute("""UPDATE openalex_import_runs SET status='failed',imported_count=?,
                completed_at=?,error_message=? WHERE public_id=?""",
                (imported, utcnow(), str(exc)[:1000], run_id))
        raise
    print({"ok": True, "run_id": run_id, "imported": imported,
           "reported_cost_usd": round(total_cost, 6), "database": str(store.path)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--filter", default=DEFAULT_FILTER)
    parser.add_argument("--search", default=None, help="Optional full-text search; costs more than list filtering")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100_000:
        parser.error("--limit 必须在 1 到 100000 之间")
    run_import(args.limit, args.filter, args.search, os.getenv("OPENALEX_API_KEY"))


if __name__ == "__main__":
    main()

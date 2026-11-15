from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_name(value: str) -> str:
    return re.sub(r"[\s_\-/]+", "", value).casefold()


def _database_path(value: str | None = None) -> Path:
    backend = Path(__file__).resolve().parents[2]
    raw = value or os.getenv("RESEARCH_SQUARE_DB_URL") or "sqlite:///./data/research_square.sqlite3"
    if raw.startswith("sqlite:///"):
        raw = raw[len("sqlite:///"):]
    path = Path(raw)
    if not path.is_absolute():
        path = backend / path
    return path.resolve()


class ResearchSquareStore:
    """SQLite repository for the optional research-square feature only."""

    def __init__(self, database_url: str | None = None):
        self.path = _database_path(database_url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _initialize(self):
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;
                CREATE TABLE IF NOT EXISTS academic_concepts(id TEXT PRIMARY KEY,name TEXT,description TEXT);
                CREATE TABLE IF NOT EXISTS academic_concept_works(concept_id TEXT REFERENCES academic_concepts(id),work_id INTEGER REFERENCES openalex_works(id) ON DELETE CASCADE,evidence TEXT,PRIMARY KEY(concept_id,work_id));
                CREATE TABLE IF NOT EXISTS academic_concept_aliases(concept_id TEXT REFERENCES academic_concepts(id),alias TEXT,PRIMARY KEY(concept_id,alias));
                CREATE INDEX IF NOT EXISTS idx_concept_work ON academic_concept_works(work_id,concept_id);
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    avatar_url TEXT,
                    bio TEXT,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','disabled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS domains (
                    id INTEGER PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    parent_id INTEGER REFERENCES domains(id),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS public_researches (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    owner_id INTEGER NOT NULL REFERENCES users(id),
                    source_run_id TEXT NOT NULL,
                    domain_id INTEGER NOT NULL REFERENCES domains(id),
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    report_content TEXT,
                    report_visibility TEXT NOT NULL DEFAULT 'summary' CHECK(report_visibility IN ('summary','full')),
                    is_anonymous INTEGER NOT NULL DEFAULT 0 CHECK(is_anonymous IN (0,1)),
                    allow_like INTEGER NOT NULL DEFAULT 1 CHECK(allow_like IN (0,1)),
                    allow_favorite INTEGER NOT NULL DEFAULT 1 CHECK(allow_favorite IN (0,1)),
                    status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('draft','published','hidden','deleted')),
                    published_at TEXT NOT NULL,
                    research_started_at TEXT,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    view_count INTEGER NOT NULL DEFAULT 0 CHECK(view_count >= 0),
                    like_count INTEGER NOT NULL DEFAULT 0 CHECK(like_count >= 0),
                    favorite_count INTEGER NOT NULL DEFAULT 0 CHECK(favorite_count >= 0),
                    comment_count INTEGER NOT NULL DEFAULT 0 CHECK(comment_count >= 0),
                    heat_score REAL NOT NULL DEFAULT 0,
                    research_input TEXT NOT NULL DEFAULT '',
                    data_origin TEXT NOT NULL DEFAULT 'user',
                    extraction_status TEXT NOT NULL DEFAULT 'pending',
                    extraction_error TEXT,
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    pinned_at TEXT,
                    UNIQUE(owner_id, source_run_id)
                );
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    canonical_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','merged','disabled')),
                    merged_into_id INTEGER REFERENCES topics(id),
                    research_count INTEGER NOT NULL DEFAULT 0,
                    heat_score REAL NOT NULL DEFAULT 0,
                    concept_type TEXT NOT NULL DEFAULT 'topic',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS topic_aliases (
                    id INTEGER PRIMARY KEY,
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL DEFAULT 'user',
                    confidence REAL NOT NULL DEFAULT 1,
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS topic_domains (
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
                    relevance_score REAL NOT NULL DEFAULT 1,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'user',
                    confidence REAL NOT NULL DEFAULT 1,
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    PRIMARY KEY(topic_id, domain_id)
                );
                CREATE TABLE IF NOT EXISTS research_topics (
                    research_id INTEGER NOT NULL REFERENCES public_researches(id) ON DELETE CASCADE,
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    weight REAL NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'user' CHECK(source IN ('user','ai','rule','seed')),
                    confidence REAL NOT NULL DEFAULT 1,
                    evidence_text TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(research_id, topic_id)
                );
                CREATE TABLE IF NOT EXISTS research_events (
                    id INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    research_id INTEGER NOT NULL REFERENCES public_researches(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id),
                    event_type TEXT NOT NULL CHECK(event_type IN ('view','like','favorite','share')),
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                );
                CREATE TABLE IF NOT EXISTS research_likes (
                    research_id INTEGER NOT NULL REFERENCES public_researches(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(research_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS research_favorites (
                    research_id INTEGER NOT NULL REFERENCES public_researches(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(research_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS topic_daily_stats (
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    stat_date TEXT NOT NULL,
                    new_research_count INTEGER NOT NULL DEFAULT 0,
                    view_count INTEGER NOT NULL DEFAULT 0,
                    like_count INTEGER NOT NULL DEFAULT 0,
                    favorite_count INTEGER NOT NULL DEFAULT 0,
                    unique_user_count INTEGER NOT NULL DEFAULT 0,
                    heat_score REAL NOT NULL DEFAULT 0,
                    calculated_at TEXT NOT NULL,
                    PRIMARY KEY(topic_id, stat_date)
                );
                CREATE TABLE IF NOT EXISTS topic_edges (
                    source_topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    target_topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    cooccurrence_count INTEGER NOT NULL DEFAULT 0,
                    relation_score REAL NOT NULL DEFAULT 0,
                    last_seen_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(source_topic_id, target_topic_id),
                    CHECK(source_topic_id < target_topic_id)
                );
                CREATE TABLE IF NOT EXISTS topic_openalex_mappings (
                    topic_id INTEGER PRIMARY KEY REFERENCES topics(id) ON DELETE CASCADE,
                    canonical_topic_id INTEGER NOT NULL REFERENCES openalex_canonical_topics(id),
                    confidence REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'ai',
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_import_jobs (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    source_run_id TEXT NOT NULL UNIQUE,
                    model_profile_id TEXT,
                    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','processing','completed','failed','cancelled')),
                    research_public_id TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hotspot_chat_sessions (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    user_id INTEGER REFERENCES users(id),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hotspot_chat_messages (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES hotspot_chat_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    query_plan_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_import_runs (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    requested_limit INTEGER NOT NULL,
                    imported_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
                    filter_json TEXT,
                    cursor TEXT,
                    cost_usd REAL NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                );
                CREATE TABLE IF NOT EXISTS openalex_works (
                    id INTEGER PRIMARY KEY,
                    openalex_id TEXT NOT NULL UNIQUE,
                    doi TEXT,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    publication_date TEXT,
                    publication_year INTEGER,
                    work_type TEXT,
                    language TEXT,
                    source_name TEXT,
                    landing_page_url TEXT,
                    cited_by_count INTEGER NOT NULL DEFAULT 0,
                    is_oa INTEGER NOT NULL DEFAULT 0 CHECK(is_oa IN (0,1)),
                    oa_url TEXT,
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    openalex_updated_at TEXT,
                    imported_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_topics (
                    id INTEGER PRIMARY KEY,
                    openalex_id TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    subfield_id TEXT,
                    subfield_name TEXT,
                    field_id TEXT,
                    field_name TEXT,
                    domain_id TEXT,
                    domain_name TEXT,
                    imported_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_work_topics (
                    work_id INTEGER NOT NULL REFERENCES openalex_works(id) ON DELETE CASCADE,
                    topic_id INTEGER NOT NULL REFERENCES openalex_topics(id) ON DELETE CASCADE,
                    score REAL NOT NULL DEFAULT 0,
                    topic_rank INTEGER NOT NULL,
                    is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
                    PRIMARY KEY(work_id,topic_id)
                );
                CREATE TABLE IF NOT EXISTS openalex_topic_aliases (
                    id INTEGER PRIMARY KEY,
                    topic_id INTEGER NOT NULL REFERENCES openalex_topics(id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL UNIQUE,
                    language TEXT,
                    source TEXT NOT NULL DEFAULT 'ai',
                    confidence REAL NOT NULL DEFAULT 0,
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_topic_domains (
                    topic_id INTEGER NOT NULL REFERENCES openalex_topics(id) ON DELETE CASCADE,
                    domain_slug TEXT NOT NULL,
                    domain_name TEXT NOT NULL,
                    relevance_score REAL NOT NULL DEFAULT 1,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'openalex',
                    confidence REAL NOT NULL DEFAULT 1,
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    PRIMARY KEY(topic_id,domain_slug,source)
                );
                CREATE TABLE IF NOT EXISTS openalex_topic_enrichments (
                    topic_id INTEGER PRIMARY KEY REFERENCES openalex_topics(id) ON DELETE CASCADE,
                    chinese_name TEXT NOT NULL,
                    summary_zh TEXT,
                    confidence REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed','needs_review','rejected')),
                    model_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_work_topic_reviews (
                    work_id INTEGER PRIMARY KEY REFERENCES openalex_works(id) ON DELETE CASCADE,
                    original_topic_id INTEGER REFERENCES openalex_topics(id),
                    selected_topic_id INTEGER REFERENCES openalex_topics(id),
                    original_score REAL NOT NULL DEFAULT 0,
                    ai_confidence REAL NOT NULL DEFAULT 0,
                    needs_human_review INTEGER NOT NULL DEFAULT 1 CHECK(needs_human_review IN (0,1)),
                    reason TEXT,
                    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed','needs_review','failed')),
                    model_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_ai_runs (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    model_profile_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
                    requested_topics INTEGER NOT NULL DEFAULT 0,
                    enriched_topics INTEGER NOT NULL DEFAULT 0,
                    requested_reviews INTEGER NOT NULL DEFAULT 0,
                    reviewed_works INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                );
                CREATE TABLE IF NOT EXISTS openalex_canonical_topics (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    canonical_name_zh TEXT NOT NULL,
                    canonical_name_en TEXT,
                    normalized_name TEXT NOT NULL,
                    summary_zh TEXT,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','merged','disabled')),
                    resolution_status TEXT NOT NULL DEFAULT 'pending' CHECK(resolution_status IN ('pending','resolved','needs_review')),
                    merged_into_id INTEGER REFERENCES openalex_canonical_topics(id),
                    confidence REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'bootstrap',
                    model_id TEXT,
                    prompt_version TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_canonical_aliases (
                    id INTEGER PRIMARY KEY,
                    canonical_topic_id INTEGER NOT NULL REFERENCES openalex_canonical_topics(id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    language TEXT,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    created_at TEXT NOT NULL,
                    UNIQUE(canonical_topic_id,normalized_alias)
                );
                CREATE TABLE IF NOT EXISTS openalex_topic_canonical_mappings (
                    openalex_topic_id INTEGER PRIMARY KEY REFERENCES openalex_topics(id) ON DELETE CASCADE,
                    canonical_topic_id INTEGER NOT NULL REFERENCES openalex_canonical_topics(id),
                    relation_type TEXT NOT NULL DEFAULT 'equivalent' CHECK(relation_type IN ('equivalent','broader','narrower','related')),
                    confidence REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL,
                    review_status TEXT NOT NULL DEFAULT 'approved',
                    reason TEXT,
                    model_id TEXT,
                    prompt_version TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_canonical_decisions (
                    id INTEGER PRIMARY KEY,
                    run_public_id TEXT,
                    source_canonical_id INTEGER NOT NULL REFERENCES openalex_canonical_topics(id),
                    target_canonical_id INTEGER REFERENCES openalex_canonical_topics(id),
                    action TEXT NOT NULL CHECK(action IN ('merged','kept','proposed_merge','needs_review','created','reused')),
                    confidence REAL NOT NULL DEFAULT 0,
                    reason TEXT,
                    model_id TEXT,
                    prompt_version TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openalex_canonical_runs (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    model_profile_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
                    requested_count INTEGER NOT NULL DEFAULT 0,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    merged_count INTEGER NOT NULL DEFAULT 0,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_public_research_status_published ON public_researches(status, published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_public_research_domain_status ON public_researches(domain_id, status, published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_public_research_heat ON public_researches(status, heat_score DESC);
                CREATE INDEX IF NOT EXISTS idx_public_research_owner ON public_researches(owner_id, status);
                CREATE INDEX IF NOT EXISTS idx_topic_status_heat ON topics(status, heat_score DESC);
                CREATE INDEX IF NOT EXISTS idx_topic_domain_lookup ON topic_domains(domain_id, relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_research_topic_reverse ON research_topics(topic_id, research_id);
                CREATE INDEX IF NOT EXISTS idx_event_research_type_time ON research_events(research_id, event_type, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_user_type_time ON research_events(user_id, event_type, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_time ON research_events(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_daily_date_heat ON topic_daily_stats(stat_date, heat_score DESC);
                CREATE INDEX IF NOT EXISTS idx_edge_source_score ON topic_edges(source_topic_id, relation_score DESC);
                CREATE INDEX IF NOT EXISTS idx_edge_target_score ON topic_edges(target_topic_id, relation_score DESC);
                CREATE INDEX IF NOT EXISTS idx_edge_score ON topic_edges(relation_score DESC);
                CREATE INDEX IF NOT EXISTS idx_openalex_work_publication ON openalex_works(publication_date DESC);
                CREATE INDEX IF NOT EXISTS idx_openalex_work_citations ON openalex_works(cited_by_count DESC);
                CREATE INDEX IF NOT EXISTS idx_openalex_work_doi ON openalex_works(doi);
                CREATE INDEX IF NOT EXISTS idx_openalex_work_topic_topic ON openalex_work_topics(topic_id,work_id);
                CREATE INDEX IF NOT EXISTS idx_openalex_topic_domain ON openalex_topic_domains(domain_slug,relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_openalex_enrichment_status ON openalex_topic_enrichments(status,confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_openalex_review_status ON openalex_work_topic_reviews(status,needs_human_review);
                CREATE INDEX IF NOT EXISTS idx_openalex_canonical_name ON openalex_canonical_topics(normalized_name,status);
                CREATE INDEX IF NOT EXISTS idx_openalex_canonical_resolution ON openalex_canonical_topics(status,resolution_status);
                CREATE INDEX IF NOT EXISTS idx_openalex_canonical_alias ON openalex_canonical_aliases(normalized_alias);
                CREATE INDEX IF NOT EXISTS idx_openalex_mapping_canonical ON openalex_topic_canonical_mappings(canonical_topic_id,openalex_topic_id);
            """)
            # Forward-only additive migration for databases created by the
            # first Research Square version.  The provenance fields are needed
            # later by AI classification and human review, while remaining
            # harmless to the existing application.
            migrations = {
                "public_researches": {
                    "research_input": "TEXT NOT NULL DEFAULT ''",
                    "data_origin": "TEXT NOT NULL DEFAULT 'user'",
                    "extraction_status": "TEXT NOT NULL DEFAULT 'pending'",
                    "extraction_error": "TEXT",
                    "is_pinned": "INTEGER NOT NULL DEFAULT 0",
                    "pinned_at": "TEXT",
                    "research_started_at": "TEXT",
                },
                "topics": {
                    "concept_type": "TEXT NOT NULL DEFAULT 'topic'",
                },
                "research_topics": {
                    "confidence": "REAL NOT NULL DEFAULT 1",
                    "evidence_text": "TEXT",
                },
                "topic_aliases": {
                    "source": "TEXT NOT NULL DEFAULT 'user'",
                    "confidence": "REAL NOT NULL DEFAULT 1",
                    "review_status": "TEXT NOT NULL DEFAULT 'approved'",
                },
                "topic_domains": {
                    "source": "TEXT NOT NULL DEFAULT 'user'",
                    "confidence": "REAL NOT NULL DEFAULT 1",
                    "review_status": "TEXT NOT NULL DEFAULT 'approved'",
                },
            }
            for table, columns in migrations.items():
                existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                for column, definition in columns.items():
                    if column not in existing:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            db.execute("CREATE INDEX IF NOT EXISTS idx_public_research_origin ON public_researches(data_origin,status,published_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_public_research_pinned ON public_researches(status,is_pinned DESC,pinned_at DESC,published_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_public_research_started ON public_researches(status,research_started_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_import_job_status ON research_import_jobs(status,created_at)")
            db.execute("UPDATE public_researches SET research_input=title WHERE research_input='' OR research_input IS NULL")
            db.execute("UPDATE public_researches SET research_started_at=published_at WHERE research_started_at IS NULL OR research_started_at=''")
            db.execute("""UPDATE public_researches SET extraction_status='completed'
                WHERE extraction_status='pending' AND EXISTS(
                    SELECT 1 FROM research_topics rt WHERE rt.research_id=public_researches.id)""")
        self.ensure_defaults()

    def ensure_defaults(self):
        stamp = utcnow()
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO users(public_id,username,display_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                ("local-user", "local_user", "本地用户", "active", stamp, stamp),
            )
            defaults = [
                ("general", "综合", "跨领域研究"), ("ai", "人工智能", "人工智能与机器学习"),
                ("database", "数据库", "数据库系统与数据工程"), ("medicine", "医学", "医学与生命科学"),
                ("education", "教育", "教育技术与学习科学"), ("finance", "金融", "金融科技与经济"),
                ("security", "网络安全", "安全、隐私与可信计算"), ("robotics", "机器人", "机器人与具身智能"),
            ]
            db.executemany(
                "INSERT OR IGNORE INTO domains(slug,name,description,created_at) VALUES(?,?,?,?)",
                [(slug, name, desc, stamp) for slug, name, desc in defaults],
            )

    def ensure_user(self, public_id: str, display_name: str | None = None, db=None) -> int:
        owns = db is None
        if owns:
            ctx = self.connect(); db = ctx.__enter__()
        try:
            row = db.execute("SELECT id FROM users WHERE public_id=?", (public_id,)).fetchone()
            if row:
                return row["id"]
            stamp = utcnow()
            username = re.sub(r"[^a-zA-Z0-9_]", "_", public_id)[:50] or f"user_{uuid4().hex[:8]}"
            db.execute(
                "INSERT INTO users(public_id,username,display_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (public_id, username, display_name or public_id, "active", stamp, stamp),
            )
            return db.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            if owns:
                ctx.__exit__(None, None, None)

    def _domain_id(self, slug: str, db) -> int:
        row = db.execute("SELECT id FROM domains WHERE slug=?", (slug,)).fetchone()
        if not row:
            row = db.execute("SELECT id FROM domains WHERE slug='general'").fetchone()
        return row["id"]

    def _topic_id(self, name: str, domain_id: int, db, source="user") -> int:
        normalized = normalize_name(name)
        row = db.execute("""SELECT t.id FROM topics t
            LEFT JOIN topic_aliases a ON a.topic_id=t.id
            WHERE t.normalized_name=? OR a.normalized_alias=? LIMIT 1""",
            (normalized, normalized)).fetchone()
        if row:
            topic_id = row["id"]
        else:
            stamp = utcnow()
            db.execute(
                "INSERT INTO topics(public_id,canonical_name,normalized_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (uuid4().hex, name[:80], normalized, "active", stamp, stamp),
            )
            topic_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        has_domain = db.execute("SELECT 1 FROM topic_domains WHERE topic_id=? LIMIT 1", (topic_id,)).fetchone()
        db.execute(
            """INSERT OR IGNORE INTO topic_domains(
                topic_id,domain_id,relevance_score,is_primary,source,confidence,review_status)
                VALUES(?,?,?,?,?,?,?)""",
            (topic_id, domain_id, 1.0, int(has_domain is None), source, 1.0, "approved"),
        )
        return topic_id

    def publish(self, *, source_run_id: str, owner_public_id: str, domain_slug: str,
                title: str, summary: str, report: str | None, topics: list[str],
                anonymous: bool = False, research_input: str | None = None,
                data_origin: str = "user", extraction_status: str = "completed",
                create_initial_topics: bool = True, research_started_at: str | None = None):
        stamp = utcnow()
        research_input = " ".join((research_input or title).split()).strip()
        if data_origin not in {"user", "sample"}:
            raise ValueError("data_origin 只能是 user 或 sample")
        with self.connect() as db:
            owner_id = self.ensure_user(owner_public_id, db=db)
            domain_id = self._domain_id(domain_slug, db)
            row = db.execute(
                "SELECT id,public_id,version FROM public_researches WHERE owner_id=? AND source_run_id=?",
                (owner_id, source_run_id),
            ).fetchone()
            if row:
                research_id, public_id, version = row["id"], row["public_id"], row["version"] + 1
                db.execute("""UPDATE public_researches SET domain_id=?,title=?,summary=?,report_content=?,
                    report_visibility=?,is_anonymous=?,status='published',updated_at=?,version=?,research_input=?,
                    data_origin=?,extraction_status=?,extraction_error=NULL,
                    research_started_at=COALESCE(?,research_started_at) WHERE id=?""",
                    (domain_id, title, summary, report, "full" if report else "summary",
                     int(anonymous), stamp, version, research_input, data_origin, extraction_status,
                     research_started_at, research_id))
                db.execute("DELETE FROM research_topics WHERE research_id=?", (research_id,))
            else:
                public_id, version = uuid4().hex, 1
                db.execute("""INSERT INTO public_researches(
                    public_id,owner_id,source_run_id,domain_id,title,summary,report_content,
                    report_visibility,is_anonymous,status,published_at,research_started_at,updated_at,version,research_input,
                    data_origin,extraction_status)
                    VALUES(?,?,?,?,?,?,?,?,?,'published',?,?,?,?,?,?,?)""",
                    (public_id, owner_id, source_run_id, domain_id, title, summary, report,
                     "full" if report else "summary", int(anonymous), stamp, research_started_at or stamp, stamp, version,
                     research_input, data_origin, extraction_status))
                research_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            topic_values = topics or ([title] if create_initial_topics else [])
            for rank, topic in enumerate(topic_values):
                topic_id = self._topic_id(topic, domain_id, db)
                db.execute("""INSERT OR REPLACE INTO research_topics(
                    research_id,topic_id,weight,source,confidence,evidence_text,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (research_id, topic_id, max(.4, 1 - rank * .08), "user", 1.0, topic, stamp))
        self.rebuild_analytics()
        return self.get_research(public_id)

    def enqueue_import(self, source_run_id: str, model_profile_id: str | None,
                       max_queued: int = 10) -> dict:
        """Persist one local import request and return immediately."""
        stamp = utcnow()
        with self.connect() as db:
            imported = db.execute("""SELECT r.public_id,r.extraction_status,
                EXISTS(SELECT 1 FROM research_topics rt WHERE rt.research_id=r.id) has_topics
                FROM public_researches r
                JOIN users u ON u.id=r.owner_id WHERE r.source_run_id=? AND r.status='published'
                AND r.data_origin='user' AND u.public_id='local-user' LIMIT 1""", (source_run_id,)).fetchone()
            if imported and imported["extraction_status"] == "completed" and imported["has_topics"]:
                return {"public_id": "", "source_run_id": source_run_id, "status": "completed",
                        "research_public_id": imported["public_id"], "already_exists": True}
            existing = db.execute("SELECT * FROM research_import_jobs WHERE source_run_id=?", (source_run_id,)).fetchone()
            if existing and existing["status"] in {"queued", "processing"}:
                return {**dict(existing), "already_exists": True}
            if existing and existing["status"] == "completed":
                published = db.execute("""SELECT r.status,r.extraction_status,
                    EXISTS(SELECT 1 FROM research_topics rt WHERE rt.research_id=r.id) has_topics
                    FROM public_researches r WHERE r.public_id=?""", (existing["research_public_id"],)).fetchone()
                if (published and published["status"] == "published"
                        and published["extraction_status"] == "completed" and published["has_topics"]):
                    return {**dict(existing), "already_exists": True}
            queued = db.execute("SELECT COUNT(*) FROM research_import_jobs WHERE status='queued'").fetchone()[0]
            if queued >= max_queued:
                raise OverflowError(f"等待队列已满，最多允许 {max_queued} 条")
            if existing:
                db.execute("""UPDATE research_import_jobs SET model_profile_id=?,status='queued',
                    research_public_id=NULL,error_message=NULL,started_at=NULL,completed_at=NULL,updated_at=?
                    WHERE id=?""", (model_profile_id, stamp, existing["id"]))
                job_id = existing["public_id"]
            else:
                job_id = uuid4().hex
                db.execute("""INSERT INTO research_import_jobs(public_id,source_run_id,model_profile_id,
                    status,created_at,updated_at) VALUES(?,?,?,'queued',?,?)""",
                    (job_id, source_run_id, model_profile_id, stamp, stamp))
            row = db.execute("SELECT * FROM research_import_jobs WHERE public_id=?", (job_id,)).fetchone()
        return {**dict(row), "already_exists": False, "retried": bool(existing or imported)}

    def import_status(self, source_run_id: str) -> dict:
        """Return the real keyword-extraction state for one local research run."""
        with self.connect() as db:
            research = db.execute("""SELECT r.public_id,r.status,r.extraction_status,r.extraction_error,
                EXISTS(SELECT 1 FROM research_topics rt WHERE rt.research_id=r.id) has_topics
                FROM public_researches r JOIN users u ON u.id=r.owner_id
                WHERE r.source_run_id=? AND r.data_origin='user' AND u.public_id='local-user'
                LIMIT 1""", (source_run_id,)).fetchone()
            job = db.execute("""SELECT status,error_message,created_at,started_at,completed_at
                FROM research_import_jobs WHERE source_run_id=?""", (source_run_id,)).fetchone()
        if research and research["status"] == "published":
            if research["extraction_status"] == "completed" and research["has_topics"]:
                state, message = "completed", "已导入到我的研究图谱"
            elif job and job["status"] in {"queued", "processing"}:
                state = job["status"]
                message = "等待提取关键词" if state == "queued" else "正在提取关键词"
            elif research["extraction_status"] == "failed" or (job and job["status"] == "failed"):
                state, message = "failed", "导入失败，请检查模型 API 后重试"
            else:
                state, message = "processing", "正在准备关键词提取"
            return {"state": state, "message": message, "research_public_id": research["public_id"],
                    "error": research["extraction_error"] or (job["error_message"] if job else None)}
        if job and job["status"] in {"queued", "processing", "failed"}:
            messages = {"queued": "等待提取关键词", "processing": "正在提取关键词",
                        "failed": "导入失败，请检查模型 API 后重试"}
            return {"state": job["status"], "message": messages[job["status"]],
                    "research_public_id": None, "error": job["error_message"]}
        return {"state": "not_imported", "message": "尚未导入", "research_public_id": None, "error": None}

    def restore_hidden_import(self, source_run_id: str) -> dict | None:
        """Restore a cancelled local import without spending another AI call.

        Cancelling an import intentionally preserves its keyword links.  If
        those links still exist, re-importing is a visibility change rather
        than a new extraction job.
        """
        stamp = utcnow()
        with self.connect() as db:
            row = db.execute("""SELECT r.id,r.public_id FROM public_researches r
                JOIN users u ON u.id=r.owner_id WHERE r.source_run_id=? AND r.status='hidden'
                AND r.data_origin='user' AND u.public_id='local-user' LIMIT 1""", (source_run_id,)).fetchone()
            if not row:
                return None
            has_topics = db.execute("SELECT EXISTS(SELECT 1 FROM research_topics WHERE research_id=?)",
                                    (row["id"],)).fetchone()[0]
            if not has_topics:
                return None
            db.execute("""UPDATE public_researches SET status='published',extraction_status='completed',
                extraction_error=NULL,updated_at=? WHERE id=?""", (stamp, row["id"]))
            db.execute("""UPDATE research_import_jobs SET status='completed',research_public_id=?,
                error_message=NULL,completed_at=?,updated_at=? WHERE source_run_id=?""",
                (row["public_id"], stamp, stamp, source_run_id))
        self.rebuild_analytics()
        return self.get_research(row["public_id"])

    def recover_import_jobs(self):
        with self.connect() as db:
            db.execute("""UPDATE research_import_jobs SET status='queued',started_at=NULL,
                error_message='程序上次退出，已自动恢复排队',updated_at=? WHERE status='processing'""", (utcnow(),))

    def claim_next_import_job(self) -> dict | None:
        stamp = utcnow()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM research_import_jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE research_import_jobs SET status='processing',started_at=?,updated_at=? WHERE id=?",
                       (stamp, stamp, row["id"]))
            return dict(db.execute("SELECT * FROM research_import_jobs WHERE id=?", (row["id"],)).fetchone())

    def finish_import_job(self, public_id: str, *, status: str,
                          research_public_id: str | None = None, error: str | None = None):
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("导入任务终态无效")
        stamp = utcnow()
        with self.connect() as db:
            db.execute("""UPDATE research_import_jobs SET status=?,research_public_id=?,error_message=?,
                completed_at=?,updated_at=? WHERE public_id=?""",
                (status, research_public_id, error, stamp, stamp, public_id))

    def import_queue_status(self) -> dict:
        with self.connect() as db:
            counts = {row["status"]: row["n"] for row in db.execute(
                "SELECT status,COUNT(*) n FROM research_import_jobs GROUP BY status")}
            recent = [dict(row) for row in db.execute("""SELECT public_id,source_run_id,status,
                research_public_id,error_message,created_at,started_at,completed_at
                FROM research_import_jobs ORDER BY updated_at DESC LIMIT 20""")]
        return {"counts": {key: counts.get(key, 0) for key in
                ("queued", "processing", "completed", "failed", "cancelled")},
                "max_queued": 10, "recent": recent}

    def replace_research_concepts(self, public_id: str, concepts: list[dict], *,
                                  extraction_status: str = "completed",
                                  extraction_error: str | None = None):
        """Replace one publication's keyword set after validated AI extraction.

        Every concept in the same user input is linked to the same research row;
        ``rebuild_analytics`` therefore creates a co-occurrence edge for every
        pair, while aggregate edge weights grow only when the pair recurs.
        """
        stamp = utcnow()
        with self.connect() as db:
            research = db.execute("SELECT id,domain_id FROM public_researches WHERE public_id=?", (public_id,)).fetchone()
            if not research:
                raise KeyError("公开研究不存在")
            db.execute("DELETE FROM research_topics WHERE research_id=?", (research["id"],))
            for index, concept in enumerate(concepts[:8]):
                name = " ".join(str(concept.get("canonical_name_zh") or concept.get("name") or "").split()).strip()[:80]
                if not name:
                    continue
                topic_id = self._topic_id(name, research["domain_id"], db, source="ai")
                concept_type = str(concept.get("concept_type") or "topic")[:40]
                db.execute("UPDATE topics SET concept_type=?,updated_at=? WHERE id=?", (concept_type, stamp, topic_id))
                openalex_canonical_id = concept.get("openalex_canonical_id")
                if openalex_canonical_id:
                    db.execute("""INSERT INTO topic_openalex_mappings(
                        topic_id,canonical_topic_id,confidence,source,review_status,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?) ON CONFLICT(topic_id) DO UPDATE SET
                        canonical_topic_id=excluded.canonical_topic_id,confidence=excluded.confidence,
                        source=excluded.source,review_status=excluded.review_status,updated_at=excluded.updated_at""",
                        (topic_id, int(openalex_canonical_id), float(concept.get("confidence") or 0.8),
                         "ai", "approved", stamp, stamp))
                aliases = [concept.get("surface_text"), *(concept.get("aliases") or [])]
                for alias in aliases:
                    alias = " ".join(str(alias or "").split()).strip()[:80]
                    normalized = normalize_name(alias)
                    if not alias or not normalized or normalized == normalize_name(name):
                        continue
                    db.execute("""INSERT OR IGNORE INTO topic_aliases(
                        topic_id,alias,normalized_alias,source,confidence,review_status,created_at)
                        VALUES(?,?,?,?,?,?,?)""", (topic_id, alias, normalized, "ai",
                        float(concept.get("confidence") or 0.8), "approved", stamp))
                db.execute("""INSERT OR REPLACE INTO research_topics(
                    research_id,topic_id,weight,source,confidence,evidence_text,created_at)
                    VALUES(?,?,?,?,?,?,?)""", (research["id"], topic_id,
                    max(0.05, min(1.0, float(concept.get("weight") or (1-index*.08)))), "ai",
                    max(0.0, min(1.0, float(concept.get("confidence") or 0.8))),
                    str(concept.get("evidence") or concept.get("surface_text") or "")[:500], stamp))
            db.execute("""UPDATE public_researches SET extraction_status=?,extraction_error=?,updated_at=?
                WHERE id=?""", (extraction_status, extraction_error, stamp, research["id"]))
        self.rebuild_analytics()
        return self.get_research(public_id)

    def unpublish(self, public_id: str, owner_public_id: str):
        with self.connect() as db:
            row = db.execute("""SELECT r.id,u.public_id owner FROM public_researches r
                JOIN users u ON u.id=r.owner_id WHERE r.public_id=?""", (public_id,)).fetchone()
            if not row:
                raise KeyError("公开研究不存在")
            if row["owner"] != owner_public_id:
                raise PermissionError("只能取消公开自己的研究")
            db.execute("UPDATE public_researches SET status='hidden',updated_at=? WHERE id=?", (utcnow(), row["id"]))
        self.rebuild_analytics()

    def remove_import(self, public_id: str):
        """Remove one locally imported item from the personal graph."""
        stamp = utcnow()
        with self.connect() as db:
            row = db.execute("SELECT id,source_run_id FROM public_researches WHERE public_id=?", (public_id,)).fetchone()
            if not row:
                raise KeyError("导入记录不存在")
            db.execute("UPDATE public_researches SET status='hidden',is_pinned=0,pinned_at=NULL,updated_at=? WHERE id=?",
                       (stamp, row["id"]))
            db.execute("""UPDATE research_import_jobs SET status='cancelled',completed_at=?,updated_at=?
                WHERE source_run_id=?""", (stamp, stamp, row["source_run_id"]))
        self.rebuild_analytics()

    def set_pinned(self, public_id: str, pinned: bool) -> dict:
        stamp = utcnow()
        with self.connect() as db:
            result = db.execute("""UPDATE public_researches SET is_pinned=?,pinned_at=?,updated_at=?
                WHERE public_id=? AND status='published'""",
                (int(pinned), stamp if pinned else None, stamp, public_id))
            if not result.rowcount:
                raise KeyError("导入记录不存在")
        return self.get_research(public_id)

    def domains(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT id,slug,name,description FROM domains ORDER BY id")]

    def resolve_topic_mentions(self, text: str, limit: int = 5) -> list[str]:
        """Resolve canonical topic names and aliases mentioned in free text.

        Longest matches win, so ``医学影像性能优化`` suppresses the nested
        generic topic ``医学影像``. Short Latin aliases such as RAG and KG use
        word boundaries to avoid accidental substring matches.
        """
        normalized_text = normalize_name(text)
        folded_text = text.casefold()
        with self.connect() as db:
            rows = db.execute("""SELECT * FROM (
                SELECT t.canonical_name,t.normalized_name candidate,t.canonical_name display
                FROM topics t WHERE t.status='active'
                UNION ALL
                SELECT t.canonical_name,a.normalized_alias candidate,a.alias display
                FROM topic_aliases a JOIN topics t ON t.id=a.topic_id WHERE t.status='active'
                ) ORDER BY LENGTH(candidate) DESC""").fetchall()
        matches: list[tuple[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            candidate = row["candidate"]
            display = row["display"]
            if not candidate or row["canonical_name"] in seen:
                continue
            if re.fullmatch(r"[a-z0-9.+#]{2,8}", candidate):
                found = re.search(rf"(?<![a-z0-9]){re.escape(display.casefold())}(?![a-z0-9])", folded_text) is not None
            else:
                found = candidate in normalized_text
            if not found:
                continue
            # Do not return a shorter generic topic already contained in a
            # more specific selected topic.
            if any(candidate in selected_norm for _, selected_norm in matches):
                continue
            matches.append((row["canonical_name"], normalize_name(row["canonical_name"])))
            seen.add(row["canonical_name"])
            if len(matches) >= limit:
                break
        return [name for name, _ in matches]

    def list_researches(self, *, query="", domain_slug=None, sort="latest", limit=20, offset=0, viewer_public_id=None):
        order = "r.is_pinned DESC,r.pinned_at DESC,r.published_at DESC,r.id DESC"
        clauses = ["r.status='published'", "u.public_id IN ('local-user','sample-library')"]
        params: list[object] = []
        if query:
            clauses.append("(r.title LIKE ? OR r.summary LIKE ? OR EXISTS(SELECT 1 FROM research_topics rt JOIN topics t ON t.id=rt.topic_id WHERE rt.research_id=r.id AND t.canonical_name LIKE ?))")
            token = f"%{query}%"; params.extend([token, token, token])
        if domain_slug:
            clauses.append("d.slug=?"); params.append(domain_slug)
        params.extend([limit, offset])
        sql = f"""SELECT r.public_id,r.source_run_id,r.title,r.summary,r.research_input,r.data_origin,r.is_pinned,r.pinned_at,
            r.extraction_status,r.extraction_error,r.report_visibility,r.is_anonymous,
            r.published_at,r.research_started_at,r.updated_at,r.view_count,r.like_count,r.favorite_count,r.heat_score,
            d.slug domain_slug,d.name domain_name,u.public_id owner_public_id,
            CASE WHEN r.is_anonymous=1 THEN '匿名研究者' ELSE u.display_name END author
            FROM public_researches r JOIN domains d ON d.id=r.domain_id JOIN users u ON u.id=r.owner_id
            WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT ? OFFSET ?"""
        with self.connect() as db:
            rows = [dict(row) for row in db.execute(sql, params)]
            for row in rows:
                row["can_manage"] = True
                row.pop("owner_public_id", None)
                row["topics"] = [x[0] for x in db.execute("""SELECT t.canonical_name FROM research_topics rt
                    JOIN topics t ON t.id=rt.topic_id JOIN public_researches r ON r.id=rt.research_id
                    WHERE r.public_id=? ORDER BY rt.weight DESC""", (row["public_id"],))]
            total_params = params[:-2]
            total = db.execute(f"""SELECT COUNT(*) FROM public_researches r JOIN domains d ON d.id=r.domain_id
                JOIN users u ON u.id=r.owner_id
                WHERE {' AND '.join(clauses)}""", total_params).fetchone()[0]
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    def get_research(self, public_id: str):
        with self.connect() as db:
            row = db.execute("""SELECT r.id,r.public_id,r.source_run_id,r.title,r.summary,r.research_input,r.data_origin,
                r.is_pinned,r.pinned_at,
                r.extraction_status,r.extraction_error,r.report_content,r.report_visibility,
                r.is_anonymous,r.published_at,r.research_started_at,r.updated_at,r.view_count,r.like_count,r.favorite_count,r.heat_score,
                r.status,d.slug domain_slug,d.name domain_name,
                CASE WHEN r.is_anonymous=1 THEN '匿名研究者' ELSE u.display_name END author
                FROM public_researches r JOIN domains d ON d.id=r.domain_id JOIN users u ON u.id=r.owner_id
                WHERE r.public_id=?""", (public_id,)).fetchone()
            if not row: raise KeyError("公开研究不存在")
            if row["status"] != "published": raise PermissionError("研究未公开")
            item = dict(row); item.pop("id"); item.pop("status")
            item["topics"] = [x[0] for x in db.execute("""SELECT t.canonical_name FROM research_topics rt
                JOIN topics t ON t.id=rt.topic_id WHERE rt.research_id=? ORDER BY rt.weight DESC""", (row["id"],))]
        item["report_content"] = item["report_content"] if item["report_visibility"] == "full" else None
        return item

    def community_topic_detail(self, public_id: str, limit: int = 100):
        """Return one user-keyword node and its latest complete research inputs."""
        with self.connect() as db:
            topic = db.execute("""SELECT id,public_id,canonical_name name,description,concept_type,
                research_count,heat_score FROM topics WHERE public_id=? AND status='active'""",
                (public_id,)).fetchone()
            if not topic:
                raise KeyError("用户研究关键词不存在")
            topic_id = topic["id"]
            result = dict(topic); result.pop("id")
            result["aliases"] = [row[0] for row in db.execute("""SELECT alias FROM topic_aliases
                WHERE topic_id=? ORDER BY confidence DESC,alias LIMIT 30""", (topic_id,))]
            result["domains"] = [dict(row) for row in db.execute("""SELECT d.slug,d.name,
                td.relevance_score relevance FROM topic_domains td JOIN domains d ON d.id=td.domain_id
                WHERE td.topic_id=? ORDER BY td.relevance_score DESC,d.id""", (topic_id,))]
            result["researches"] = [dict(row) for row in db.execute("""SELECT r.public_id,r.source_run_id,r.title,
                CASE WHEN r.research_input<>'' THEN r.research_input ELSE r.title END research_input,
                r.published_at,r.research_started_at,r.updated_at,r.data_origin,r.extraction_status,r.heat_score,
                '匿名研究者' author
                FROM research_topics rt JOIN public_researches r ON r.id=rt.research_id
                WHERE rt.topic_id=? AND r.status='published'
                ORDER BY r.research_started_at DESC,r.id DESC LIMIT ?""", (topic_id, limit))]
            result["stats"] = {
                "researches": len(result["researches"]),
                "user_researches": sum(x["data_origin"] == "user" for x in result["researches"]),
                "sample_researches": sum(x["data_origin"] == "sample" for x in result["researches"]),
                "heat": result["heat_score"],
            }
            result["limit"] = limit
        return result

    def record_action(self, public_id: str, user_public_id: str, action: str, event_id: str | None = None):
        if action not in {"view", "like", "favorite", "share"}:
            raise ValueError("不支持的行为")
        stamp = utcnow(); event_id = event_id or uuid4().hex
        with self.connect() as db:
            research = db.execute("SELECT id,allow_like,allow_favorite FROM public_researches WHERE public_id=? AND status='published'", (public_id,)).fetchone()
            if not research:
                raise KeyError("公开研究不存在")
            user_id = self.ensure_user(user_public_id, db=db)
            if action == "like":
                if not research["allow_like"]: raise PermissionError("该研究未开放点赞")
                changed = db.execute("INSERT OR IGNORE INTO research_likes VALUES(?,?,?)", (research["id"], user_id, stamp)).rowcount
                if not changed: return {"changed": False, "reason": "already_liked"}
            elif action == "favorite":
                if not research["allow_favorite"]: raise PermissionError("该研究未开放收藏")
                changed = db.execute("INSERT OR IGNORE INTO research_favorites VALUES(?,?,?)", (research["id"], user_id, stamp)).rowcount
                if not changed: return {"changed": False, "reason": "already_favorited"}
            try:
                db.execute("INSERT INTO research_events(event_id,research_id,user_id,event_type,created_at) VALUES(?,?,?,?,?)",
                           (event_id, research["id"], user_id, action, stamp))
            except sqlite3.IntegrityError:
                return {"changed": False, "reason": "duplicate_event"}
            column = {"view": "view_count", "like": "like_count", "favorite": "favorite_count"}.get(action)
            if column:
                db.execute(f"UPDATE public_researches SET {column}={column}+1 WHERE id=?", (research["id"],))
            db.execute("""UPDATE public_researches SET heat_score=
                10 + view_count*.2 + like_count*3 + favorite_count*5 WHERE id=?""", (research["id"],))
            # Interactive events update only the affected topics. Rebuilding the
            # complete graph here would serialize every concurrent click.
            delta = {"view": .2, "like": 3.0, "favorite": 5.0}.get(action, 0.0)
            day = stamp[:10]
            for topic in db.execute("SELECT topic_id FROM research_topics WHERE research_id=?", (research["id"],)).fetchall():
                views, likes, favorites = (1, 0, 0) if action == "view" else (0, 1, 0) if action == "like" else (0, 0, 1) if action == "favorite" else (0, 0, 0)
                db.execute("""INSERT INTO topic_daily_stats(topic_id,stat_date,new_research_count,view_count,like_count,
                    favorite_count,unique_user_count,heat_score,calculated_at) VALUES(?,?,0,?,?,?,?,?,?)
                    ON CONFLICT(topic_id,stat_date) DO UPDATE SET view_count=view_count+excluded.view_count,
                    like_count=like_count+excluded.like_count,favorite_count=favorite_count+excluded.favorite_count,
                    heat_score=heat_score+excluded.heat_score,calculated_at=excluded.calculated_at""",
                    (topic["topic_id"], day, views, likes, favorites, 0, delta, stamp))
                db.execute("UPDATE topics SET heat_score=heat_score+?,updated_at=? WHERE id=?", (delta, stamp, topic["topic_id"]))
        return {"changed": True, "research": self.get_research(public_id)}

    def rebuild_analytics(self):
        """Rebuild deterministic aggregates. Suitable for local development and audits."""
        stamp = utcnow()
        with self.connect() as db:
            db.execute("UPDATE public_researches SET like_count=(SELECT COUNT(*) FROM research_likes l WHERE l.research_id=public_researches.id), favorite_count=(SELECT COUNT(*) FROM research_favorites f WHERE f.research_id=public_researches.id)")
            db.execute("UPDATE public_researches SET heat_score=CASE WHEN status='published' THEN 10+view_count*.2+like_count*3+favorite_count*5 ELSE 0 END")
            db.execute("DELETE FROM topic_daily_stats")
            rows = db.execute("""SELECT rt.topic_id,substr(COALESCE(r.research_started_at,r.published_at),1,10) day,COUNT(DISTINCT r.id) researches,
                SUM(r.view_count) views,SUM(r.like_count) likes,SUM(r.favorite_count) favorites,
                COUNT(DISTINCT r.owner_id) users
                FROM research_topics rt JOIN public_researches r ON r.id=rt.research_id
                WHERE r.status='published' GROUP BY rt.topic_id,substr(COALESCE(r.research_started_at,r.published_at),1,10)""").fetchall()
            db.executemany("INSERT INTO topic_daily_stats VALUES(?,?,?,?,?,?,?,?,?)", [
                (r["topic_id"], r["day"], r["researches"], r["views"], r["likes"], r["favorites"], r["users"],
                 r["researches"]*10+r["views"]*.2+r["likes"]*3+r["favorites"]*5, stamp) for r in rows
            ])
            cutoff = (date.today() - timedelta(days=30)).isoformat()
            db.execute("""UPDATE topics SET research_count=(SELECT COUNT(DISTINCT rt.research_id) FROM research_topics rt
                JOIN public_researches r ON r.id=rt.research_id WHERE rt.topic_id=topics.id AND r.status='published'),
                heat_score=COALESCE((SELECT SUM(s.heat_score) FROM topic_daily_stats s WHERE s.topic_id=topics.id AND s.stat_date>=?),0),
                updated_at=?""", (cutoff, stamp))
            db.execute("DELETE FROM topic_edges")
            pairs = db.execute("""SELECT a.topic_id source,b.topic_id target,COUNT(*) n,MAX(COALESCE(r.research_started_at,r.published_at)) last_seen
                FROM research_topics a JOIN research_topics b ON a.research_id=b.research_id AND a.topic_id<b.topic_id
                JOIN public_researches r ON r.id=a.research_id WHERE r.status='published'
                GROUP BY a.topic_id,b.topic_id""").fetchall()
            payload = []
            for row in pairs:
                counts = db.execute("SELECT research_count FROM topics WHERE id IN (?,?) ORDER BY id", (row["source"], row["target"])).fetchall()
                union = sum(x[0] for x in counts) - row["n"]
                score = row["n"] / union if union else 0
                payload.append((row["source"], row["target"], row["n"], score, row["last_seen"], stamp))
            db.executemany("INSERT INTO topic_edges VALUES(?,?,?,?,?,?)", payload)

    def hot_topics(self, days=30, domain_slug=None, limit=15):
        cutoff = (date.today() - timedelta(days=days-1)).isoformat()
        params: list[object] = [cutoff]
        domain_join = ""
        if domain_slug:
            domain_join = "JOIN topic_domains td ON td.topic_id=t.id JOIN domains d ON d.id=td.domain_id AND d.slug=?"
            params.insert(0, domain_slug)
        params.append(limit)
        with self.connect() as db:
            rows = db.execute(f"""SELECT t.public_id,t.canonical_name name,t.research_count,
                COALESCE(SUM(s.view_count),0) views,COALESCE(SUM(s.like_count),0) likes,
                COALESCE(SUM(s.favorite_count),0) favorites,COALESCE(SUM(s.heat_score),0) heat
                FROM topics t {domain_join} LEFT JOIN topic_daily_stats s ON s.topic_id=t.id AND s.stat_date>=?
                WHERE t.status='active' GROUP BY t.id HAVING heat>0 ORDER BY heat DESC LIMIT ?""", params).fetchall()
        return [dict(row) for row in rows]

    def overview(self, days=30, domain_slug=None):
        topics = self.hot_topics(days, domain_slug, 15)
        with self.connect() as db:
            where = "WHERE r.status='published'"; params: list[object] = []
            if domain_slug:
                where += " AND d.slug=?"; params.append(domain_slug)
            stats = db.execute(f"""SELECT COUNT(*) researches,COUNT(DISTINCT r.owner_id) authors,
                COALESCE(SUM(r.view_count),0) views,COALESCE(SUM(r.like_count),0) likes
                FROM public_researches r JOIN domains d ON d.id=r.domain_id {where}""", params).fetchone()
        return {"stats": dict(stats), "hot_topics": topics, "days": days, "domain_slug": domain_slug}

    def openalex_enrichment_status(self):
        with self.connect() as db:
            row = db.execute("""SELECT
                (SELECT COUNT(*) FROM openalex_works) works,
                (SELECT COUNT(*) FROM openalex_topics) topics,
                (SELECT COUNT(*) FROM openalex_topic_enrichments) enriched_topics,
                (SELECT COUNT(*) FROM openalex_topic_enrichments WHERE status='needs_review') topic_needs_review,
                (SELECT COUNT(*) FROM openalex_work_topics WHERE is_primary=1 AND score<.5) low_confidence_works,
                (SELECT COUNT(*) FROM openalex_work_topic_reviews) reviewed_works,
                (SELECT COUNT(*) FROM openalex_work_topic_reviews WHERE needs_human_review=1) work_needs_review""").fetchone()
            latest = db.execute("""SELECT public_id,status,model_id,enriched_topics,reviewed_works,
                prompt_tokens,completion_tokens,started_at,completed_at,error_message
                FROM openalex_ai_runs ORDER BY id DESC LIMIT 1""").fetchone()
        result = dict(row)
        result["topic_progress"] = round(result["enriched_topics"] / result["topics"] * 100, 2) if result["topics"] else 0
        result["review_progress"] = round(result["reviewed_works"] / result["low_confidence_works"] * 100, 2) if result["low_confidence_works"] else 100
        result["latest_run"] = dict(latest) if latest else None
        return result

    def openalex_overview(self, days=365, domain_slug=None, limit=15):
        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
        stats_clause = "w.publication_date>=?"
        stats_params: list[object] = [cutoff]
        if domain_slug:
            stats_clause += """ AND EXISTS(SELECT 1 FROM openalex_work_topics wx
                JOIN openalex_topic_domains dx ON dx.topic_id=wx.topic_id
                WHERE wx.work_id=w.id AND dx.source='ai' AND dx.domain_slug=?)"""
            stats_params.append(domain_slug)
        with self.connect() as db:
            stats = dict(db.execute(f"""SELECT COUNT(*) works,COALESCE(SUM(w.cited_by_count),0) citations,
                COALESCE(SUM(w.is_oa),0) open_access FROM openalex_works w WHERE {stats_clause}""",
                stats_params).fetchone())
            canonical_ready = db.execute("SELECT EXISTS(SELECT 1 FROM openalex_topic_canonical_mappings)").fetchone()[0]
            if not canonical_ready:
                raw_join = ""
                raw_params: list[object] = [cutoff]
                if domain_slug:
                    raw_join = """JOIN openalex_topic_domains td ON td.topic_id=t.id
                        AND td.source='ai' AND td.domain_slug=?"""
                    raw_params.insert(0, domain_slug)
                raw_params.append(limit)
                stats["topics"] = db.execute(f"""SELECT COUNT(DISTINCT wt.topic_id)
                    FROM openalex_works w JOIN openalex_work_topics wt ON wt.work_id=w.id
                    WHERE {stats_clause}""", stats_params).fetchone()[0]
                rows = db.execute(f"""SELECT t.openalex_id public_id,
                    COALESCE(e.chinese_name,t.display_name) name,t.display_name original_name,
                    COUNT(DISTINCT wt.work_id) research_count,SUM(w.cited_by_count) citations,
                    AVG(wt.score) average_score,COUNT(DISTINCT wt.work_id) heat
                    FROM openalex_topics t JOIN openalex_work_topics wt ON wt.topic_id=t.id
                    JOIN openalex_works w ON w.id=wt.work_id
                    LEFT JOIN openalex_topic_enrichments e ON e.topic_id=t.id
                    {raw_join} WHERE w.publication_date>=?
                    GROUP BY t.id ORDER BY research_count DESC,citations DESC LIMIT ?""", raw_params).fetchall()
                return {"stats": stats, "hot_topics": [dict(row) for row in rows],
                        "days": days, "domain_slug": domain_slug, "source": "openalex"}
            domain_clause = ""
            params: list[object] = [cutoff]
            if domain_slug:
                domain_clause = """AND EXISTS(SELECT 1 FROM openalex_topic_canonical_mappings md
                    JOIN openalex_topic_domains dd ON dd.topic_id=md.openalex_topic_id
                    WHERE md.canonical_topic_id=c.id AND dd.source='ai' AND dd.domain_slug=?)"""
                params.append(domain_slug)
            stats["topics"] = db.execute(f"""SELECT COUNT(DISTINCT m.canonical_topic_id)
                FROM openalex_works w JOIN openalex_work_topics wt ON wt.work_id=w.id
                JOIN openalex_topic_canonical_mappings m ON m.openalex_topic_id=wt.topic_id
                JOIN openalex_canonical_topics c ON c.id=m.canonical_topic_id AND c.status='active'
                WHERE w.publication_date>=? {domain_clause}""", params).fetchone()[0]
            rows = db.execute(f"""WITH workset AS (
                SELECT c.id,c.public_id,c.canonical_name_zh name,c.canonical_name_en original_name,
                    wt.work_id,MAX(wt.score) score,w.cited_by_count
                FROM openalex_canonical_topics c
                JOIN openalex_topic_canonical_mappings m ON m.canonical_topic_id=c.id
                JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                JOIN openalex_works w ON w.id=wt.work_id
                WHERE c.status='active' AND w.publication_date>=? {domain_clause}
                GROUP BY c.id,wt.work_id)
                SELECT public_id,name,original_name,COUNT(*) research_count,SUM(cited_by_count) citations,
                    AVG(score) average_score,COUNT(*) heat FROM workset
                GROUP BY id ORDER BY research_count DESC,citations DESC LIMIT ?""", [*params, limit]).fetchall()
        return {"stats": stats, "hot_topics": [dict(row) for row in rows],
                "days": days, "domain_slug": domain_slug, "source": "openalex"}

    def resolve_openalex_topic_mentions(self, text: str, limit: int = 5) -> list[str]:
        """Resolve real OpenAlex topics without treating paper titles as topics."""
        normalized_text = normalize_name(text)
        folded_text = text.casefold()
        with self.connect() as db:
            rows = db.execute("""SELECT * FROM (
                SELECT c.id,c.canonical_name_zh canonical_name,c.canonical_name_zh display,
                    c.canonical_name_zh candidate FROM openalex_canonical_topics c WHERE c.status='active'
                UNION ALL
                SELECT c.id,c.canonical_name_zh,c.canonical_name_en,c.canonical_name_en
                    FROM openalex_canonical_topics c WHERE c.status='active'
                UNION ALL
                SELECT c.id,c.canonical_name_zh,a.alias,a.alias FROM openalex_canonical_aliases a
                    JOIN openalex_canonical_topics c ON c.id=a.canonical_topic_id WHERE c.status='active'
                ) WHERE candidate IS NOT NULL ORDER BY LENGTH(candidate) DESC""").fetchall()
        matches: list[tuple[str, str]] = []
        seen: set[int] = set()
        for row in rows:
            candidate = normalize_name(row["candidate"])
            if not candidate or row["id"] in seen:
                continue
            display = str(row["display"])
            if re.fullmatch(r"[a-z0-9.+#]{2,12}", candidate):
                found = re.search(rf"(?<![a-z0-9]){re.escape(display.casefold())}(?![a-z0-9])", folded_text) is not None
            else:
                found = candidate in normalized_text
            if not found or any(candidate in selected for _, selected in matches):
                continue
            matches.append((row["canonical_name"], normalize_name(row["canonical_name"])))
            seen.add(row["id"])
            if len(matches) >= limit:
                break
        return [name for name, _ in matches]

    def research_gap_candidates(self, question: str, limit: int = 10) -> dict:
        from .gaps import candidates
        return candidates(self, question, limit)

    def _openalex_topic_rows(self, names: list[str], db) -> list[sqlite3.Row]:
        if not names:
            return []
        normalized = [normalize_name(name) for name in names]
        rows = db.execute("""SELECT id,public_id openalex_id,canonical_name_en display_name,
            canonical_name_zh canonical_name FROM openalex_canonical_topics WHERE status='active'""").fetchall()
        aliases: dict[str, int] = {}
        for row in db.execute("SELECT canonical_topic_id,alias FROM openalex_canonical_aliases"):
            aliases[normalize_name(row["alias"])] = row["canonical_topic_id"]
        wanted = set(normalized)
        return [row for row in rows if normalize_name(row["canonical_name"]) in wanted
                or normalize_name(row["display_name"]) in wanted or row["id"] in {aliases.get(x) for x in wanted}]

    def openalex_graph(self, days=30, domain_slug=None, limit=40, max_edges_per_node=3):
        """Return the same nodes/edges contract as the simulated graph.

        Nodes are canonical OpenAlex topics, never paper titles.  Edges are
        period-accurate topic co-occurrences within the same imported work.
        """
        with self.connect() as db:
            canonical_count = db.execute("SELECT COUNT(*) FROM openalex_topic_canonical_mappings").fetchone()[0]
            enriched_count = db.execute("SELECT COUNT(*) FROM openalex_topic_enrichments").fetchone()[0]
        if not canonical_count and enriched_count:
            # One-time forward migration for databases enriched before the
            # canonical layer existed.
            from .canonical import bootstrap_canonical_topics
            bootstrap_canonical_topics(self)
        current_start = (date.today() - timedelta(days=days - 1)).isoformat()
        domain_clause = ""
        params: list[object] = [current_start]
        if domain_slug:
            domain_clause = """AND EXISTS(SELECT 1 FROM openalex_topic_canonical_mappings md
                JOIN openalex_topic_domains dd ON dd.topic_id=md.openalex_topic_id
                WHERE md.canonical_topic_id=c.id AND dd.source='ai' AND dd.domain_slug=?)"""
            params.append(domain_slug)
        with self.connect() as db:
            selected = db.execute(f"""WITH workset AS (
                SELECT c.id,c.public_id,c.canonical_name_zh name,c.canonical_name_en original_name,
                    wt.work_id,w.cited_by_count
                FROM openalex_canonical_topics c
                JOIN openalex_topic_canonical_mappings m ON m.canonical_topic_id=c.id
                JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                JOIN openalex_works w ON w.id=wt.work_id
                WHERE c.status='active' AND w.publication_date>=? {domain_clause}
                GROUP BY c.id,wt.work_id)
                SELECT workset.id,workset.public_id,workset.name,workset.original_name,COUNT(*) research_count,
                    COALESCE(SUM(workset.cited_by_count),0) citations,
                    date(AVG(julianday(w.publication_date))) average_started_at,
                    MAX(w.publication_date) latest_started_at FROM workset
                JOIN openalex_works w ON w.id=workset.work_id
                GROUP BY workset.id ORDER BY research_count DESC,citations DESC LIMIT ?""", [*params, limit]).fetchall()
            if not selected:
                return {"nodes": [], "edges": [], "days": days, "domain_slug": domain_slug, "source": "openalex"}
            topic_ids = [row["id"] for row in selected]
            marks = ",".join("?" for _ in topic_ids)
            pair_rows = db.execute(f"""WITH mapped_work AS (
                SELECT m.canonical_topic_id canonical_id,wt.work_id,MAX(wt.score) score
                FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                JOIN openalex_works w ON w.id=wt.work_id
                WHERE m.canonical_topic_id IN ({marks}) AND w.publication_date>=?
                GROUP BY m.canonical_topic_id,wt.work_id)
                SELECT a.canonical_id source_id,b.canonical_id target_id,COUNT(*) cooccurrence_count,
                    SUM(MIN(a.score,b.score)) weighted_cooccurrence FROM mapped_work a
                JOIN mapped_work b ON b.work_id=a.work_id AND a.canonical_id<b.canonical_id
                GROUP BY a.canonical_id,b.canonical_id ORDER BY cooccurrence_count DESC""", [*topic_ids, current_start]).fetchall()
        by_id = {row["id"]: row for row in selected}
        candidates = []
        for row in pair_rows:
            left, right = by_id[row["source_id"]], by_id[row["target_id"]]
            union = left["research_count"] + right["research_count"] - row["cooccurrence_count"]
            candidates.append({
                "source": left["public_id"], "target": right["public_id"],
                "cooccurrence_count": row["cooccurrence_count"],
                "relation_score": round(row["cooccurrence_count"] / union, 6) if union else 0,
                "weighted_cooccurrence": round(float(row["weighted_cooccurrence"] or 0), 3),
            })
        candidates.sort(key=lambda item: (item["relation_score"], item["cooccurrence_count"]), reverse=True)
        degrees = {row["public_id"]: 0 for row in selected}
        edges = []
        for edge in candidates:
            if degrees[edge["source"]] >= max_edges_per_node or degrees[edge["target"]] >= max_edges_per_node:
                continue
            edges.append(edge); degrees[edge["source"]] += 1; degrees[edge["target"]] += 1
            if len(edges) >= limit * 2:
                break
        nodes = []
        for row in selected:
            current = row["research_count"]
            average_day = date.fromisoformat(row["average_started_at"])
            average_age = max(0, (date.today() - average_day).days)
            recency = max(0.0, min(1.0, 1 - average_age / max(days - 1, 1)))
            activity = round(current * (0.25 + 0.75 * recency), 3)
            nodes.append({"id": row["public_id"], "name": row["name"], "heat": activity,
                          "recent_activity": activity, "research_count": current,
                          "average_started_at": row["average_started_at"],
                          "latest_started_at": row["latest_started_at"],
                          "original_name": row["original_name"]})
        return {"nodes": nodes, "edges": edges, "days": days, "domain_slug": domain_slug, "source": "openalex"}

    def query_openalex_plan_data(self, plan):
        """Execute the chat whitelist against real OpenAlex metadata only."""
        cutoff = (date.today() - timedelta(days=plan.days - 1)).isoformat()
        if plan.intent in {"rank_topics", "domain_summary"}:
            result = self.openalex_overview(plan.days, plan.domain_slug, plan.limit)
            return {"topics": result["hot_topics"], "source": "openalex"}
        if plan.intent == "list_researches":
            result = self.list_openalex_works(domain_slug=plan.domain_slug, limit=plan.limit)
            result["source"] = "openalex"
            return result
        if plan.intent in {"related_topics", "compare_topics", "topic_trend"}:
            if not plan.topics:
                return {"error": "missing_topic", "message": "没有识别到要查询的 OpenAlex 主题。", "source": "openalex"}
            with self.connect() as db:
                topic_rows = self._openalex_topic_rows(plan.topics, db)
                if not topic_rows:
                    return {"error": "unknown_topic", "message": f"真实主题库中没有找到：{'、'.join(plan.topics)}。", "source": "openalex"}
                if plan.intent in {"topic_trend", "compare_topics"}:
                    series, summaries = {}, {}
                    for row in topic_rows:
                        raw = db.execute("""SELECT w.publication_date stat_date,COUNT(DISTINCT w.id) n,
                            COALESCE(SUM(w.cited_by_count),0) citations FROM openalex_topic_canonical_mappings m
                            JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                            JOIN openalex_works w ON w.id=wt.work_id
                            WHERE m.canonical_topic_id=? AND w.publication_date>=?
                            GROUP BY w.publication_date ORDER BY w.publication_date""",
                            (row["id"], cutoff)).fetchall()
                        points = [{"stat_date": x["stat_date"], "heat_score": x["n"],
                                   "new_research_count": x["n"], "view_count": 0, "like_count": 0,
                                   "citations": x["citations"]} for x in raw]
                        series[row["canonical_name"]] = points
                        summaries[row["canonical_name"]] = self._trend_summary(points, plan.days)
                    return {"series": series, "trend_summaries": summaries, "source": "openalex"}
                related: dict[str, dict] = {}
                for topic in topic_rows:
                    topic_count = db.execute("""SELECT COUNT(DISTINCT wt.work_id)
                        FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                        JOIN openalex_works w ON w.id=wt.work_id
                        WHERE m.canonical_topic_id=? AND w.publication_date>=?""",
                        (topic["id"], cutoff)).fetchone()[0]
                    rows = db.execute("""WITH source_works AS (
                            SELECT DISTINCT wt.work_id FROM openalex_topic_canonical_mappings m
                            JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                            JOIN openalex_works w ON w.id=wt.work_id
                            WHERE m.canonical_topic_id=? AND w.publication_date>=?)
                        SELECT other.id,other.canonical_name_zh name,other.canonical_name_en original_name,
                            COUNT(DISTINCT sw.work_id) cooccurrence_count
                        FROM source_works sw JOIN openalex_work_topics b ON b.work_id=sw.work_id
                        JOIN openalex_topic_canonical_mappings mb ON mb.openalex_topic_id=b.topic_id
                        JOIN openalex_canonical_topics other ON other.id=mb.canonical_topic_id AND other.status='active'
                        WHERE other.id<>? GROUP BY other.id ORDER BY cooccurrence_count DESC LIMIT ?""",
                        (topic["id"], cutoff, topic["id"], plan.limit * 3)).fetchall()
                    for item in rows:
                        other_count = db.execute("""SELECT COUNT(DISTINCT wt.work_id)
                            FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                            JOIN openalex_works w ON w.id=wt.work_id
                            WHERE m.canonical_topic_id=? AND w.publication_date>=?""",
                            (item["id"], cutoff)).fetchone()[0]
                        union = topic_count + other_count - item["cooccurrence_count"]
                        value = {"name": item["name"], "original_name": item["original_name"],
                                 "cooccurrence_count": item["cooccurrence_count"],
                                 "relation_score": item["cooccurrence_count"] / union if union else 0}
                        if value["relation_score"] > related.get(value["name"], {}).get("relation_score", -1):
                            related[value["name"]] = value
                items = sorted(related.values(), key=lambda x: (x["relation_score"], x["cooccurrence_count"]), reverse=True)
                return {"related": items[:plan.limit], "matched_topics": [x["canonical_name"] for x in topic_rows], "source": "openalex"}
        return {"topics": [], "source": "openalex"}

    def list_openalex_works(self, *, query="", domain_slug=None, sort="latest", limit=20, offset=0):
        clauses = ["1=1"]
        params: list[object] = []
        query = query.strip()
        if query:
            from .paper_search import work_filter
            predicate, values = work_filter(query)
            clauses.append(predicate)
            params.extend(values)
        if domain_slug:
            clauses.append("""EXISTS(SELECT 1 FROM openalex_work_topics wx
                JOIN openalex_topic_domains dx ON dx.topic_id=wx.topic_id
                WHERE wx.work_id=w.id AND dx.source='ai' AND dx.domain_slug=?)""")
            params.append(domain_slug)
        where = " AND ".join(clauses)
        order = {"latest": "w.publication_date DESC,w.id DESC", "citations": "w.cited_by_count DESC,w.id DESC", "citations_asc": "w.cited_by_count ASC,w.id ASC", "oldest": "w.publication_date ASC,w.id ASC",
                 "confidence": "primary_score DESC"}.get(sort, "w.publication_date DESC,w.id DESC")
        with self.connect() as db:
            rows = [dict(row) for row in db.execute(f"""SELECT w.id,w.openalex_id,w.doi,w.title,w.abstract,
                w.publication_date,w.work_type,w.language,w.source_name,w.landing_page_url,w.cited_by_count,
                w.is_oa,w.oa_url,w.authors_json,t.display_name original_topic,
                COALESCE(ct.canonical_name_zh,te.chinese_name,t.display_name) primary_topic,wt.score primary_score,
                rt.display_name ai_selected_topic,rv.ai_confidence,rv.needs_human_review
                FROM openalex_works w
                LEFT JOIN openalex_work_topics wt ON wt.work_id=w.id AND wt.is_primary=1
                LEFT JOIN openalex_topics t ON t.id=wt.topic_id
                LEFT JOIN openalex_topic_enrichments te ON te.topic_id=t.id
                LEFT JOIN openalex_topic_canonical_mappings cm ON cm.openalex_topic_id=t.id
                LEFT JOIN openalex_canonical_topics ct ON ct.id=cm.canonical_topic_id AND ct.status='active'
                LEFT JOIN openalex_work_topic_reviews rv ON rv.work_id=w.id
                LEFT JOIN openalex_topics rt ON rt.id=rv.selected_topic_id
                WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?""", [*params, limit, offset])]
            total = db.execute(f"SELECT COUNT(*) FROM openalex_works w WHERE {where}", params).fetchone()[0]
        for row in rows:
            row["authors"] = json.loads(row.pop("authors_json") or "[]")
        return {"items": rows, "total": total, "limit": limit, "offset": offset, "source": "openalex"}

    def openalex_topic_detail(self, public_id: str, limit: int = 100, *, query="", sort="citations", offset=0):
        """Return one canonical topic and its most-cited distinct works."""
        with self.connect() as db:
            topic = db.execute("""SELECT id,public_id,canonical_name_zh name,
                canonical_name_en original_name,summary_zh,confidence,resolution_status
                FROM openalex_canonical_topics WHERE public_id=? AND status='active'""", (public_id,)).fetchone()
            if not topic:
                raise KeyError("真实研究主题不存在")
            topic_id = topic["id"]
            result = dict(topic); result.pop("id")
            result["aliases"] = [row[0] for row in db.execute("""SELECT alias
                FROM openalex_canonical_aliases WHERE canonical_topic_id=?
                ORDER BY language DESC,confidence DESC,alias LIMIT 30""", (topic_id,))]
            result["domains"] = [dict(row) for row in db.execute("""SELECT d.domain_slug slug,d.domain_name name,
                MAX(d.relevance_score) relevance FROM openalex_topic_canonical_mappings m
                JOIN openalex_topic_domains d ON d.topic_id=m.openalex_topic_id AND d.source='ai'
                WHERE m.canonical_topic_id=? GROUP BY d.domain_slug,d.domain_name ORDER BY relevance DESC""", (topic_id,))]
            result["source_topics"] = [dict(row) for row in db.execute("""SELECT t.openalex_id,t.display_name,
                t.subfield_name,t.field_name,t.domain_name,m.confidence,m.source
                FROM openalex_topic_canonical_mappings m JOIN openalex_topics t ON t.id=m.openalex_topic_id
                WHERE m.canonical_topic_id=? ORDER BY m.confidence DESC,t.display_name""", (topic_id,))]
            stats = db.execute("""SELECT COUNT(DISTINCT w.id) works
                FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                JOIN openalex_works w ON w.id=wt.work_id WHERE m.canonical_topic_id=?""", (topic_id,)).fetchone()
            # Citation totals must deduplicate works; SUM(DISTINCT citations)
            # would incorrectly collapse different papers with equal counts.
            citation_total = db.execute("""SELECT COALESCE(SUM(cited_by_count),0) FROM (
                SELECT DISTINCT w.id,w.cited_by_count FROM openalex_topic_canonical_mappings m
                JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                JOIN openalex_works w ON w.id=wt.work_id WHERE m.canonical_topic_id=?)""", (topic_id,)).fetchone()[0]
            result["stats"] = {"works": stats["works"], "citations": citation_total,
                               "source_topics": len(result["source_topics"])}
            pattern = "%" + query + "%"
            filters = " AND (w.title LIKE ? OR w.abstract LIKE ? OR w.authors_json LIKE ? OR w.source_name LIKE ?)" if query else ""
            params = [topic_id, *([pattern]*4 if query else [])]
            order = {"citations": "w.cited_by_count DESC,w.id DESC", "citations_asc": "w.cited_by_count ASC,w.id ASC", "latest": "w.publication_date DESC,w.id DESC", "oldest": "w.publication_date ASC,w.id ASC"}.get(sort, "w.cited_by_count DESC,w.id DESC")
            result["total"] = db.execute(f"""SELECT COUNT(DISTINCT w.id) FROM openalex_topic_canonical_mappings m
                JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id JOIN openalex_works w ON w.id=wt.work_id
                WHERE m.canonical_topic_id=? {filters}""", params).fetchone()[0]
            rows = [dict(row) for row in db.execute(f"""SELECT w.id,w.openalex_id,w.doi,w.title,w.abstract,
                w.publication_date,w.publication_year,w.work_type,w.language,w.source_name,w.landing_page_url,
                w.cited_by_count,w.is_oa,w.oa_url,w.authors_json,MAX(wt.score) topic_score
                FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
                JOIN openalex_works w ON w.id=wt.work_id WHERE m.canonical_topic_id=? {filters}
                GROUP BY w.id ORDER BY {order} LIMIT ? OFFSET ?""",
                [*params, limit, offset])]
        for row in rows:
            row["authors"] = json.loads(row.pop("authors_json") or "[]")
            row.pop("id", None)
        result["works"] = rows
        result["limit"] = limit
        return result

    def graph(self, days=30, domain_slug=None, limit=40, max_edges_per_node=3):
        """Return a sparse graph coloured by recent research activity.

        A topic's activity is based on research start time, never import time:
        ``count * (0.25 + 0.75 * average_recency)``.  Average recency is one
        for research started today and zero at the beginning of the requested
        window.  This makes both frequency and the average start date visible.
        """
        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
        domain_join = ""
        params: list[object] = [cutoff]
        if domain_slug:
            domain_join = "JOIN topic_domains td ON td.topic_id=t.id JOIN domains d ON d.id=td.domain_id AND d.slug=?"
            params.insert(0, domain_slug)
        with self.connect() as db:
            rows = [dict(row) for row in db.execute(f"""SELECT t.id,t.public_id,t.canonical_name name,
                COUNT(DISTINCT r.id) research_count,
                date(AVG(julianday(substr(r.research_started_at,1,10)))) average_started_at,
                MAX(substr(r.research_started_at,1,10)) latest_started_at
                FROM topics t {domain_join}
                JOIN research_topics rt ON rt.topic_id=t.id
                JOIN public_researches r ON r.id=rt.research_id
                WHERE t.status='active' AND r.status='published'
                    AND substr(r.research_started_at,1,10)>=?
                GROUP BY t.id""", params)]
            for row in rows:
                average_day = date.fromisoformat(row["average_started_at"])
                average_age = max(0, (date.today() - average_day).days)
                recency = max(0.0, min(1.0, 1 - average_age / max(days - 1, 1)))
                row["recent_activity"] = round(row["research_count"] * (0.25 + 0.75 * recency), 3)
            rows.sort(key=lambda row: (row["recent_activity"], row["research_count"]), reverse=True)
            selected = rows[:limit]
            db_ids = [row["id"] for row in selected]
            if not db_ids:
                return {"nodes": [], "edges": [], "days": days, "domain_slug": domain_slug}
            edge_marks = ",".join("?" for _ in db_ids)
            candidates = [dict(row) for row in db.execute(f"""SELECT ts.public_id source,tt.public_id target,
                e.cooccurrence_count,e.relation_score FROM topic_edges e
                JOIN topics ts ON ts.id=e.source_topic_id JOIN topics tt ON tt.id=e.target_topic_id
                WHERE e.source_topic_id IN ({edge_marks}) AND e.target_topic_id IN ({edge_marks})
                AND e.relation_score>0 AND e.cooccurrence_count>0
                ORDER BY e.relation_score DESC,e.cooccurrence_count DESC""", [*db_ids, *db_ids])]
        degrees = {row["public_id"]: 0 for row in selected}
        edges = []
        edge_cap = max(limit, limit * 2)
        for edge in candidates:
            source, target = edge["source"], edge["target"]
            if degrees[source] >= max_edges_per_node or degrees[target] >= max_edges_per_node:
                continue
            edges.append(edge)
            degrees[source] += 1
            degrees[target] += 1
            if len(edges) >= edge_cap:
                break
        nodes = [{
            "id": item["public_id"], "name": item["name"],
            "heat": item["recent_activity"], "recent_activity": item["recent_activity"],
            "research_count": item["research_count"],
            "average_started_at": item["average_started_at"],
            "latest_started_at": item["latest_started_at"],
        } for item in selected]
        return {"nodes": nodes, "edges": edges, "days": days, "domain_slug": domain_slug}

    def query_plan_data(self, plan):
        if plan.intent in {"rank_topics", "domain_summary"}:
            return {"topics": self.hot_topics(plan.days, plan.domain_slug, plan.limit)}
        if plan.intent == "list_researches":
            return self.list_researches(domain_slug=plan.domain_slug, limit=plan.limit)
        if plan.intent in {"related_topics", "compare_topics", "topic_trend"}:
            names = [normalize_name(x) for x in plan.topics]
            with self.connect() as db:
                if not names:
                    return {"error": "missing_topic", "message": "没有识别到要查询的研究主题，请在问题中写出具体主题名称。"}
                marks = ",".join("?" for _ in names)
                topic_rows = db.execute(f"""SELECT DISTINCT t.id,t.public_id,t.canonical_name FROM topics t
                    LEFT JOIN topic_aliases a ON a.topic_id=t.id
                    WHERE t.normalized_name IN ({marks}) OR a.normalized_alias IN ({marks})""", [*names, *names]).fetchall()
                if not topic_rows:
                    return {"error": "unknown_topic", "message": f"没有在主题库中找到：{'、'.join(plan.topics)}。可以换用更短名称或已有别名。"}
                if plan.intent == "topic_trend" or plan.intent == "compare_topics":
                    cutoff = (date.today()-timedelta(days=plan.days-1)).isoformat()
                    series = {}
                    summaries = {}
                    for row in topic_rows:
                        points = [dict(x) for x in db.execute(
                            "SELECT stat_date,heat_score,new_research_count,view_count,like_count FROM topic_daily_stats WHERE topic_id=? AND stat_date>=? ORDER BY stat_date",
                            (row["id"], cutoff))]
                        series[row["canonical_name"]] = points
                        summaries[row["canonical_name"]] = self._trend_summary(points, plan.days)
                    return {"series": series, "trend_summaries": summaries}
                related_by_name = {}
                for row in topic_rows:
                    for related in db.execute("""SELECT CASE WHEN e.source_topic_id=? THEN b.canonical_name ELSE a.canonical_name END name,
                        e.relation_score,e.cooccurrence_count FROM topic_edges e JOIN topics a ON a.id=e.source_topic_id JOIN topics b ON b.id=e.target_topic_id
                        WHERE e.source_topic_id=? OR e.target_topic_id=? ORDER BY e.relation_score DESC LIMIT ?""",
                        (row["id"], row["id"], row["id"], plan.limit)):
                        current = related_by_name.get(related["name"])
                        if current is None or related["relation_score"] > current["relation_score"]:
                            related_by_name[related["name"]] = dict(related)
                related_items = sorted(related_by_name.values(), key=lambda x: (x["relation_score"], x["cooccurrence_count"]), reverse=True)
                return {"related": related_items[:plan.limit], "matched_topics": [row["canonical_name"] for row in topic_rows]}
        return {"topics": []}

    @staticmethod
    def _trend_summary(points: list[dict], days: int) -> dict:
        """Aggregate daily points into comparable rolling periods."""
        if days >= 60:
            bucket_days = 30
        elif days >= 21:
            bucket_days = 7
        else:
            bucket_days = max(1, math.ceil(days / 3))
        window_start = date.today() - timedelta(days=days - 1)
        points_by_day = {row["stat_date"]: row for row in points}
        periods = []
        offset = 0
        while offset < days:
            start = window_start + timedelta(days=offset)
            end = min(date.today(), start + timedelta(days=bucket_days - 1))
            values = [points_by_day.get((start + timedelta(days=index)).isoformat(), {})
                      for index in range((end - start).days + 1)]
            periods.append({
                "start": start.isoformat(), "end": end.isoformat(),
                "heat": round(sum(float(row.get("heat_score") or 0) for row in values), 2),
                "new_research_count": sum(int(row.get("new_research_count") or 0) for row in values),
                "views": sum(int(row.get("view_count") or 0) for row in values),
                "likes": sum(int(row.get("like_count") or 0) for row in values),
            })
            offset += bucket_days
        for index, period in enumerate(periods):
            if index == 0:
                period["change_pct"] = None
                period["direction"] = "baseline"
                continue
            previous = periods[index - 1]["heat"]
            current = period["heat"]
            change = round((current - previous) / previous * 100, 2) if previous > 0 else None
            period["change_pct"] = change
            period["direction"] = "up" if change is not None and change > 5 else (
                "down" if change is not None and change < -5 else "stable")
        comparable = [period for period in periods[1:] if period["change_pct"] is not None]
        latest_change = comparable[-1]["change_pct"] if comparable else None
        direction = "up" if latest_change is not None and latest_change > 5 else (
            "down" if latest_change is not None and latest_change < -5 else "stable")
        return {"bucket_days": bucket_days, "periods": periods,
                "latest_change_pct": latest_change, "direction": direction}

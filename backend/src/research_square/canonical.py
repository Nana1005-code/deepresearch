from __future__ import annotations

from difflib import SequenceMatcher
from uuid import uuid4

from .store import ResearchSquareStore, normalize_name, utcnow


PROMPT_VERSION = "openalex-canonical-v1"


def _clean(value: object, limit: int = 160) -> str:
    return " ".join(str(value or "").split())[:limit]


def _language(value: str) -> str:
    return "zh" if any("\u4e00" <= char <= "\u9fff" for char in value) else "en"


def _add_alias(db, canonical_id: int, alias: str, source: str, confidence: float,
               review_status: str = "approved") -> None:
    alias = _clean(alias)
    normalized = normalize_name(alias)
    if not normalized:
        return
    db.execute("""INSERT OR IGNORE INTO openalex_canonical_aliases(
        canonical_topic_id,alias,normalized_alias,language,source,confidence,review_status,created_at)
        VALUES(?,?,?,?,?,?,?,?)""",
        (canonical_id, alias, normalized, _language(alias), source, confidence, review_status, utcnow()))


def _create_canonical(db, row, source: str = "bootstrap", model_id: str | None = None,
                      prompt_version: str | None = None) -> int:
    stamp = utcnow()
    chinese_name = _clean(row["chinese_name"] or row["display_name"])
    db.execute("""INSERT INTO openalex_canonical_topics(public_id,canonical_name_zh,canonical_name_en,
        normalized_name,summary_zh,status,resolution_status,confidence,source,model_id,prompt_version,
        created_at,updated_at) VALUES(?,?,?,?,?,'active','pending',?,?,?,?,?,?)""",
        (uuid4().hex, chinese_name, _clean(row["display_name"]), normalize_name(chinese_name),
         _clean(row["summary_zh"], 500), float(row["confidence"] or 0), source, model_id,
         prompt_version, stamp, stamp))
    canonical_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    _add_alias(db, canonical_id, chinese_name, source, float(row["confidence"] or 0))
    _add_alias(db, canonical_id, row["display_name"], "openalex", 1.0)
    return canonical_id


def bootstrap_canonical_topics(store: ResearchSquareStore, topic_ids: list[int] | None = None,
                               preferred_targets: dict[int, dict] | None = None) -> dict:
    """Map enriched OpenAlex topics without destroying their source identities.

    Exact existing names/aliases are reused first.  Only when none match is a
    new canonical entity created.  This is deterministic and safe to rerun.
    """
    created = reused = 0
    with store.connect() as db:
        where = "AND t.id IN ({})".format(",".join("?" for _ in topic_ids)) if topic_ids else ""
        rows = db.execute(f"""SELECT t.id,t.display_name,e.chinese_name,e.summary_zh,e.confidence
            FROM openalex_topics t JOIN openalex_topic_enrichments e ON e.topic_id=t.id
            LEFT JOIN openalex_topic_canonical_mappings m ON m.openalex_topic_id=t.id
            WHERE m.openalex_topic_id IS NULL {where} ORDER BY t.id""", topic_ids or []).fetchall()
        for row in rows:
            aliases = [row["chinese_name"], row["display_name"], *[x[0] for x in db.execute(
                "SELECT alias FROM openalex_topic_aliases WHERE topic_id=?", (row["id"],))]]
            normalized = [normalize_name(x) for x in aliases if x]
            marks = ",".join("?" for _ in normalized)
            candidates = [] if not normalized else db.execute(f"""SELECT DISTINCT c.id FROM openalex_canonical_topics c
                LEFT JOIN openalex_canonical_aliases a ON a.canonical_topic_id=c.id
                WHERE c.status='active' AND (c.normalized_name IN ({marks}) OR a.normalized_alias IN ({marks}))""",
                [*normalized, *normalized]).fetchall()
            preferred = (preferred_targets or {}).get(row["id"], {})
            preferred_id = preferred.get("target_canonical_id")
            preferred_valid = preferred_id and db.execute(
                "SELECT 1 FROM openalex_canonical_topics WHERE id=? AND status='active'", (preferred_id,)).fetchone()
            if preferred_valid and float(preferred.get("confidence") or 0) >= .9:
                canonical_id = int(preferred_id); reused += 1; mapping_source = "ai_reuse"
            elif len(candidates) == 1:
                canonical_id = candidates[0][0]; reused += 1; mapping_source = "exact_alias"
            else:
                canonical_id = _create_canonical(db, row); created += 1; mapping_source = "bootstrap"
            stamp = utcnow()
            db.execute("""INSERT INTO openalex_topic_canonical_mappings(openalex_topic_id,canonical_topic_id,
                relation_type,confidence,source,review_status,reason,created_at,updated_at)
                VALUES(?,?,'equivalent',?,?, 'approved',?,?,?)""",
                (row["id"], canonical_id, float(row["confidence"] or 0), mapping_source,
                 (preferred.get("reason") or "AI从现有规范主题候选中复用")[:500] if mapping_source == "ai_reuse"
                 else "规范名或别名精确命中" if mapping_source == "exact_alias" else "初始规范主题", stamp, stamp))
            for alias in aliases:
                _add_alias(db, canonical_id, alias, "openalex_ai", float(row["confidence"] or 0))
    return {"created": created, "reused": reused, "mapped": created + reused}


def raw_topic_candidates(store: ResearchSquareStore, display_name: str, limit: int = 5,
                         minimum_similarity: float = .62) -> list[dict]:
    """Retrieve existing canonical aliases before a new entity is created."""
    with store.connect() as db:
        rows = db.execute("""SELECT c.id,c.canonical_name_zh,c.canonical_name_en,
            GROUP_CONCAT(a.alias,'|||') aliases FROM openalex_canonical_topics c
            LEFT JOIN openalex_canonical_aliases a ON a.canonical_topic_id=c.id
            WHERE c.status='active' GROUP BY c.id""").fetchall()
    needle = normalize_name(display_name)
    scored = []
    for row in rows:
        values = [row["canonical_name_en"], row["canonical_name_zh"], *(row["aliases"] or "").split("|||")]
        similarity = max((SequenceMatcher(None, needle, normalize_name(value)).ratio()
                          for value in values if value), default=0)
        if similarity >= minimum_similarity:
            scored.append({"canonical_id": row["id"], "name_zh": row["canonical_name_zh"],
                           "name_en": row["canonical_name_en"], "name_similarity": round(similarity, 4)})
    return sorted(scored, key=lambda item: item["name_similarity"], reverse=True)[:limit]


def canonical_candidates(store: ResearchSquareStore, source_id: int, limit: int = 5,
                         minimum_similarity: float = .58) -> list[dict]:
    with store.connect() as db:
        source = db.execute("""SELECT id,canonical_name_zh,canonical_name_en,summary_zh
            FROM openalex_canonical_topics WHERE id=? AND status='active'""", (source_id,)).fetchone()
        if not source:
            return []
        source_aliases = [x[0] for x in db.execute(
            "SELECT alias FROM openalex_canonical_aliases WHERE canonical_topic_id=?", (source_id,))]
        rows = db.execute("""SELECT c.id,c.canonical_name_zh,c.canonical_name_en,c.summary_zh,
            GROUP_CONCAT(a.alias,'|||') aliases
            FROM openalex_canonical_topics c LEFT JOIN openalex_canonical_aliases a ON a.canonical_topic_id=c.id
            WHERE c.status='active' AND c.id<>? GROUP BY c.id""", (source_id,)).fetchall()
        source_domains = {x[0] for x in db.execute("""SELECT DISTINCT d.domain_slug
            FROM openalex_topic_canonical_mappings m JOIN openalex_topic_domains d ON d.topic_id=m.openalex_topic_id
            WHERE m.canonical_topic_id=?""", (source_id,))}
        scored = []
        source_values = [source["canonical_name_zh"], source["canonical_name_en"], *source_aliases]
        for row in rows:
            target_values = [row["canonical_name_zh"], row["canonical_name_en"], *(row["aliases"] or "").split("|||")]
            similarity = max((SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()
                              for a in source_values for b in target_values if a and b), default=0)
            target_domains = {x[0] for x in db.execute("""SELECT DISTINCT d.domain_slug
                FROM openalex_topic_canonical_mappings m JOIN openalex_topic_domains d ON d.topic_id=m.openalex_topic_id
                WHERE m.canonical_topic_id=?""", (row["id"],))}
            domain_overlap = len(source_domains & target_domains) / max(1, len(source_domains | target_domains))
            score = similarity * .85 + domain_overlap * .15
            if similarity >= minimum_similarity:
                scored.append({"canonical_id": row["id"], "name_zh": row["canonical_name_zh"],
                               "name_en": row["canonical_name_en"], "summary_zh": row["summary_zh"],
                               "aliases": target_values[2:8], "name_similarity": round(similarity, 4),
                               "domain_overlap": round(domain_overlap, 4), "retrieval_score": round(score, 4)})
        return sorted(scored, key=lambda x: x["retrieval_score"], reverse=True)[:limit]


def canonical_context(store: ResearchSquareStore, canonical_id: int) -> dict | None:
    with store.connect() as db:
        row = db.execute("""SELECT id canonical_id,canonical_name_zh name_zh,canonical_name_en name_en,
            summary_zh FROM openalex_canonical_topics WHERE id=? AND status='active'""", (canonical_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["aliases"] = [x[0] for x in db.execute(
            "SELECT alias FROM openalex_canonical_aliases WHERE canonical_topic_id=? LIMIT 12", (canonical_id,))]
        result["hierarchy"] = [dict(x) for x in db.execute("""SELECT DISTINCT t.subfield_name,t.field_name,t.domain_name
            FROM openalex_topic_canonical_mappings m JOIN openalex_topics t ON t.id=m.openalex_topic_id
            WHERE m.canonical_topic_id=? LIMIT 8""", (canonical_id,))]
        result["sample_titles"] = [x[0] for x in db.execute("""SELECT DISTINCT w.title
            FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
            JOIN openalex_works w ON w.id=wt.work_id WHERE m.canonical_topic_id=? LIMIT 5""", (canonical_id,))]
        return result


def merge_canonical(store: ResearchSquareStore, source_id: int, target_id: int, confidence: float,
                    reason: str, model_id: str, run_id: str, auto_threshold: float = .95) -> str:
    stamp = utcnow()
    action = "merged" if confidence >= auto_threshold else "proposed_merge"
    with store.connect() as db:
        source = db.execute("SELECT status FROM openalex_canonical_topics WHERE id=?", (source_id,)).fetchone()
        target = db.execute("SELECT status FROM openalex_canonical_topics WHERE id=?", (target_id,)).fetchone()
        if not source or not target or source["status"] != "active" or target["status"] != "active" or source_id == target_id:
            return "skipped"
        if action == "merged":
            db.execute("UPDATE openalex_topic_canonical_mappings SET canonical_topic_id=?,source='ai_merge',confidence=?,reason=?,model_id=?,prompt_version=?,updated_at=? WHERE canonical_topic_id=?",
                       (target_id, confidence, reason[:500], model_id, PROMPT_VERSION, stamp, source_id))
            for alias in db.execute("SELECT alias,language,source,confidence,review_status FROM openalex_canonical_aliases WHERE canonical_topic_id=?", (source_id,)).fetchall():
                _add_alias(db, target_id, alias["alias"], alias["source"], alias["confidence"], alias["review_status"])
            db.execute("UPDATE openalex_canonical_topics SET status='merged',resolution_status='resolved',merged_into_id=?,updated_at=? WHERE id=?",
                       (target_id, stamp, source_id))
        else:
            db.execute("UPDATE openalex_canonical_topics SET resolution_status='needs_review',updated_at=? WHERE id=?", (stamp, source_id))
        db.execute("""INSERT INTO openalex_canonical_decisions(run_public_id,source_canonical_id,target_canonical_id,
            action,confidence,reason,model_id,prompt_version,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (run_id, source_id, target_id, action, confidence, reason[:500], model_id, PROMPT_VERSION, stamp))
    return action


def mark_canonical_decision(store: ResearchSquareStore, source_id: int, action: str, confidence: float,
                            reason: str, model_id: str, run_id: str) -> None:
    status = "needs_review" if action == "needs_review" else "resolved"
    recorded = "needs_review" if action == "needs_review" else "kept"
    with store.connect() as db:
        db.execute("UPDATE openalex_canonical_topics SET resolution_status=?,updated_at=? WHERE id=? AND status='active'",
                   (status, utcnow(), source_id))
        db.execute("""INSERT INTO openalex_canonical_decisions(run_public_id,source_canonical_id,action,
            confidence,reason,model_id,prompt_version,created_at) VALUES(?,?,?,?,?,?,?,?)""",
            (run_id, source_id, recorded, confidence, reason[:500], model_id, PROMPT_VERSION, utcnow()))

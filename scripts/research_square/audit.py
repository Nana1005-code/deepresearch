"""Audit Research Square aggregate and privacy invariants."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"backend"/"src"))
from research_square.store import ResearchSquareStore  # noqa: E402


def main():
    store=ResearchSquareStore();problems=[]
    with store.connect() as db:
        if db.execute("PRAGMA foreign_key_check").fetchall():problems.append("存在外键错误")
        mismatches=db.execute("""SELECT COUNT(*) FROM public_researches r WHERE
            r.like_count!=(SELECT COUNT(*) FROM research_likes l WHERE l.research_id=r.id)
            OR r.favorite_count!=(SELECT COUNT(*) FROM research_favorites f WHERE f.research_id=r.id)""").fetchone()[0]
        if mismatches:problems.append(f"互动缓存不一致：{mismatches} 条")
        bad_edges=db.execute("SELECT COUNT(*) FROM topic_edges WHERE source_topic_id>=target_topic_id OR relation_score<0 OR relation_score>1").fetchone()[0]
        if bad_edges:problems.append(f"图谱边异常：{bad_edges} 条")
        duplicate_topics=db.execute("SELECT COUNT(*) FROM (SELECT normalized_name FROM topics GROUP BY normalized_name HAVING COUNT(*)>1)").fetchone()[0]
        if duplicate_topics:problems.append(f"规范主题重复：{duplicate_topics} 组")
        multiple_primary=db.execute("""SELECT COUNT(*) FROM (SELECT topic_id FROM topic_domains
            WHERE is_primary=1 GROUP BY topic_id HAVING COUNT(*)>1)""").fetchone()[0]
        if multiple_primary:problems.append(f"主题存在多个主领域：{multiple_primary} 条")
        hidden_stats=db.execute("""SELECT COUNT(*) FROM research_topics rt JOIN public_researches r ON r.id=rt.research_id
            WHERE r.status!='published' AND EXISTS(SELECT 1 FROM topic_daily_stats s WHERE s.topic_id=rt.topic_id)""").fetchone()[0]
        totals={name:db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in
                ("users","public_researches","topics","research_topics","research_events","topic_daily_stats","topic_edges")}
        totals["topic_aliases"]=db.execute("SELECT COUNT(*) FROM topic_aliases").fetchone()[0]
        totals["cross_domain_topics"]=db.execute("""SELECT COUNT(*) FROM (SELECT topic_id FROM topic_domains
            GROUP BY topic_id HAVING COUNT(*)>1)""").fetchone()[0]
        totals["openalex_works"]=db.execute("SELECT COUNT(*) FROM openalex_works").fetchone()[0]
        totals["openalex_topics"]=db.execute("SELECT COUNT(*) FROM openalex_topics").fetchone()[0]
        totals["openalex_work_topics"]=db.execute("SELECT COUNT(*) FROM openalex_work_topics").fetchone()[0]
        totals["openalex_enriched_topics"]=db.execute("SELECT COUNT(*) FROM openalex_topic_enrichments").fetchone()[0]
        totals["openalex_reviewed_works"]=db.execute("SELECT COUNT(*) FROM openalex_work_topic_reviews").fetchone()[0]
        totals["openalex_canonical_topics"]=db.execute("SELECT COUNT(*) FROM openalex_canonical_topics WHERE status='active'").fetchone()[0]
        totals["openalex_canonical_merged"]=db.execute("SELECT COUNT(*) FROM openalex_canonical_topics WHERE status='merged'").fetchone()[0]
        totals["openalex_canonical_aliases"]=db.execute("SELECT COUNT(*) FROM openalex_canonical_aliases").fetchone()[0]
        totals["openalex_canonical_needs_review"]=db.execute("SELECT COUNT(*) FROM openalex_canonical_topics WHERE resolution_status='needs_review'").fetchone()[0]
        missing_mappings=db.execute("""SELECT COUNT(*) FROM openalex_topic_enrichments e
            WHERE NOT EXISTS(SELECT 1 FROM openalex_topic_canonical_mappings m WHERE m.openalex_topic_id=e.topic_id)""").fetchone()[0]
        if missing_mappings:problems.append(f"已增强主题缺少规范映射：{missing_mappings} 条")
        inactive_mappings=db.execute("""SELECT COUNT(*) FROM openalex_topic_canonical_mappings m
            JOIN openalex_canonical_topics c ON c.id=m.canonical_topic_id WHERE c.status!='active'""").fetchone()[0]
        if inactive_mappings:problems.append(f"规范映射指向非活动主题：{inactive_mappings} 条")
        duplicate_canonical=db.execute("""SELECT COUNT(*) FROM (SELECT normalized_name
            FROM openalex_canonical_topics WHERE status='active' GROUP BY normalized_name HAVING COUNT(*)>1)""").fetchone()[0]
        if duplicate_canonical:problems.append(f"活动规范主题名称重复：{duplicate_canonical} 组")
        invalid_reviews=db.execute("""SELECT COUNT(*) FROM openalex_work_topic_reviews r WHERE
            NOT EXISTS(SELECT 1 FROM openalex_work_topics wt WHERE wt.work_id=r.work_id AND wt.topic_id=r.selected_topic_id)""").fetchone()[0]
        if invalid_reviews:problems.append(f"AI 选择了候选集外主题：{invalid_reviews} 条")
    print({"ok":not problems,"problems":problems,"counts":totals,"note":"主题统计按主题聚合，hidden_stats 仅作观察值","hidden_topic_links":hidden_stats})
    raise SystemExit(1 if problems else 0)


if __name__=="__main__":main()

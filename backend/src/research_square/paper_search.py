"""Literal matching over imported papers and their stored topic metadata."""
def pattern(query):
    return '%' + query.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def work_filter(query):
    token = pattern(query)
    sql = r"""(w.title LIKE ? ESCAPE '\' OR w.abstract LIKE ? ESCAPE '\'
        OR w.authors_json LIKE ? ESCAPE '\' OR w.source_name LIKE ? ESCAPE '\'
        OR w.doi LIKE ? ESCAPE '\' OR w.id IN (
            SELECT wt.work_id FROM openalex_work_topics wt
            JOIN openalex_topics t ON t.id=wt.topic_id
            LEFT JOIN openalex_topic_enrichments te ON te.topic_id=t.id
            LEFT JOIN openalex_topic_canonical_mappings m ON m.openalex_topic_id=t.id
            LEFT JOIN openalex_canonical_topics c ON c.id=m.canonical_topic_id AND c.status='active'
            WHERE t.display_name LIKE ? ESCAPE '\' OR te.chinese_name LIKE ? ESCAPE '\'
            OR c.canonical_name_zh LIKE ? ESCAPE '\' OR c.canonical_name_en LIKE ? ESCAPE '\'
            OR EXISTS(SELECT 1 FROM openalex_canonical_aliases a WHERE a.canonical_topic_id=c.id AND a.alias LIKE ? ESCAPE '\')
            OR EXISTS(SELECT 1 FROM openalex_topic_domains d WHERE d.topic_id=t.id AND (d.domain_name LIKE ? ESCAPE '\' OR d.domain_slug LIKE ? ESCAPE '\'))))"""
    sql = '(' + sql + r""" OR w.id IN (SELECT cw.work_id FROM academic_concept_works cw
        JOIN academic_concepts c ON c.id=cw.concept_id WHERE c.name LIKE ? ESCAPE '\'
        OR EXISTS(SELECT 1 FROM academic_concept_aliases a WHERE a.concept_id=c.id AND a.alias LIKE ? ESCAPE '\')))"""
    return sql, [token]*14


def suggestions(store, query):
    if not query.strip():
        return []
    token = pattern(query)
    with store.connect() as db:
        topics = [dict(r) for r in db.execute(r"""SELECT c.public_id id,c.canonical_name_zh label,
            COUNT(DISTINCT wt.work_id) count FROM openalex_canonical_topics c
            JOIN openalex_topic_canonical_mappings m ON m.canonical_topic_id=c.id
            JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id
            WHERE c.status='active' AND (c.canonical_name_zh LIKE ? ESCAPE '\'
                OR c.canonical_name_en LIKE ? ESCAPE '\'
                OR EXISTS(SELECT 1 FROM openalex_canonical_aliases a WHERE a.canonical_topic_id=c.id AND a.alias LIKE ? ESCAPE '\'))
            GROUP BY c.id ORDER BY count DESC,c.id LIMIT 6""", [token]*3)]
        custom = [dict(r) for r in db.execute(r"""SELECT c.id,c.name label,COUNT(*) count FROM academic_concepts c
            JOIN academic_concept_works cw ON cw.concept_id=c.id
            WHERE c.name LIKE ? ESCAPE '\' OR EXISTS(SELECT 1 FROM academic_concept_aliases a WHERE a.concept_id=c.id AND a.alias LIKE ? ESCAPE '\')
            GROUP BY c.id ORDER BY count DESC LIMIT 6""", [token]*2)]
        topics = sorted(custom+topics,key=lambda r:(r['label']==query.strip(),r['count']),reverse=True)[:8]
        papers = [dict(r) for r in db.execute(r"""SELECT openalex_id id,title label FROM openalex_works
            WHERE title LIKE ? ESCAPE '\' ORDER BY cited_by_count DESC,id DESC LIMIT 6""", (token,))]
    return [dict(r, kind='topic') for r in topics] + [dict(r,kind='paper') for r in papers]

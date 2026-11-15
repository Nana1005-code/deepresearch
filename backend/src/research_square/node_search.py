"""Search and neighborhood views backed exclusively by stored graph memberships."""
from difflib import SequenceMatcher
from datetime import date
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from .store import normalize_name


def membership(source):
    if source == 'local':
        return "SELECT rt.topic_id node, r.id work,substr(r.research_started_at,1,10) started FROM research_topics rt JOIN public_researches r ON r.id=rt.research_id WHERE r.status='published'"
    return "SELECT DISTINCT m.canonical_topic_id node, wt.work_id work,w.publication_date started FROM openalex_topic_canonical_mappings m JOIN openalex_work_topics wt ON wt.topic_id=m.openalex_topic_id JOIN openalex_works w ON w.id=wt.work_id UNION ALL SELECT cw.concept_id node,cw.work_id work,w.publication_date started FROM academic_concept_works cw JOIN openalex_works w ON w.id=cw.work_id"


def catalog(store, source):
    if source == 'local':
        table, name, alias_table, alias_fk = 'topics', 'canonical_name', 'topic_aliases', 'topic_id'
    else:
        table, name, alias_table, alias_fk = 'openalex_canonical_topics', 'canonical_name_zh', 'openalex_canonical_aliases', 'canonical_topic_id'
    with store.connect() as db:
        rows = [dict(r) for r in db.execute(f"""WITH members AS ({membership(source)})
            SELECT t.id,t.public_id,t.{name} name,COUNT(DISTINCT members.work) research_count,
            date(AVG(julianday(members.started))) average_started_at,MAX(members.started) latest_started_at
            FROM {table} t JOIN members ON members.node=t.id WHERE t.status='active' GROUP BY t.id""")]
        if source == 'openalex':
            rows.extend(dict(r) for r in db.execute("""SELECT c.id,c.id public_id,c.name,COUNT(*) research_count,
                date(AVG(julianday(w.publication_date))) average_started_at,MAX(w.publication_date) latest_started_at
                FROM academic_concepts c JOIN academic_concept_works cw ON cw.concept_id=c.id
                JOIN openalex_works w ON w.id=cw.work_id GROUP BY c.id"""))
        aliases = {}
        for r in db.execute(f'SELECT {alias_fk},alias FROM {alias_table}'):
            aliases.setdefault(r[0], []).append(r[1])
        if source == 'openalex':
            for a in db.execute('SELECT concept_id,alias FROM academic_concept_aliases'):
                aliases.setdefault(a[0], []).append(a[1])
    for r in rows:
        r['aliases'] = aliases.get(r['id'], [])
        age = (date.today() - date.fromisoformat(r['average_started_at'])).days if r['average_started_at'] else 365
        r['activity'] = round(r['research_count'] * (.25 + .75 * max(0, min(1, 1-age/364))), 3)
    return rows


def integrated_graph(store, days=365, domain=None, limit=40, max_edges=3):
    original=store.openalex_graph(days,domain,limit,max_edges)
    if domain:
        return original
    rows=catalog(store,'openalex')
    by_public={r['public_id']:r for r in rows}
    curated=sorted([r for r in rows if str(r['id']).startswith('concept-')],key=lambda r:r['activity'],reverse=True)[:max(3,limit//3)]
    if not curated:
        return original
    chosen=curated+[by_public[n['id']] for n in original['nodes'] if n['id'] in by_public][:limit-len(curated)]
    by_id={r['id']:r for r in chosen};ids=list(by_id);marks=','.join('?' for _ in ids)
    with store.connect() as db:
        edges=[dict(r) for r in db.execute(f'''WITH members AS ({membership('openalex')}),selected AS (
            SELECT * FROM members WHERE node IN ({marks}))
            SELECT a.node source,b.node target,COUNT(DISTINCT a.work) cooccurrence_count
            FROM selected a JOIN selected b ON a.work=b.work AND a.node<b.node
            GROUP BY a.node,b.node ORDER BY cooccurrence_count DESC''',ids)]
    kept=[];degrees={i:0 for i in ids}
    for e in edges:
        a,b=e['source'],e['target']
        if degrees[a]>=max_edges or degrees[b]>=max_edges:continue
        degrees[a]+=1;degrees[b]+=1
        kept.append(dict(source=by_id[a]['public_id'],target=by_id[b]['public_id'],cooccurrence_count=e['cooccurrence_count'],relation_score=e['cooccurrence_count']/(by_id[a]['research_count']+by_id[b]['research_count']-e['cooccurrence_count'])))
    return {'nodes':[dict(id=r['public_id'],name=r['name'],research_count=r['research_count'],heat=r['activity'],recent_activity=r['activity'],average_started_at=r['average_started_at'] or '',latest_started_at=r['latest_started_at'] or '') for r in chosen],'edges':kept,'source':'openalex_and_paper_evidence','scope':'all_imported'}


def router(store):
    api = APIRouter(prefix='/nodes')

    @api.get('/search')
    def search(q: str = Query('', max_length=100), source: Literal['local', 'openalex'] = 'local'):
        needle = normalize_name(q)
        if not needle:
            return []
        matches = []
        for row in catalog(store, source):
            score = 0
            for label in [row['name'], *row['aliases']]:
                candidate = normalize_name(label)
                ratio = SequenceMatcher(None, needle, candidate).ratio()
                score = max(score, 3 if needle == candidate else 2 + len(needle)/max(len(candidate),1) if needle in candidate else ratio if ratio >= .55 else 0)
            if score:
                matches.append((score, row))
        matches.sort(key=lambda pair: (pair[0], pair[1]['research_count']), reverse=True)
        return [{k: r[k] for k in ('public_id','name','research_count')} for _,r in matches[:15]]

    @api.get('/{public_id}/graph')
    def neighborhood(public_id: str, source: Literal['local', 'openalex'] = 'local'):
        rows = catalog(store, source)
        center = next((r for r in rows if r['public_id'] == public_id), None)
        if center is None:
            raise HTTPException(404, '图谱中不存在该节点')
        by_id = {r['id']: r for r in rows}
        with store.connect() as db:
            related = db.execute(f"""WITH members AS ({membership(source)})
                SELECT b.node,COUNT(DISTINCT b.work) n FROM members a JOIN members b ON b.work=a.work
                WHERE a.node=? AND b.node<>a.node GROUP BY b.node ORDER BY n DESC,b.node""", (center['id'],)).fetchall()
        related = [r for r in related if r['node'] in by_id]
        if public_id.startswith('concept-'):
            related.sort(key=lambda r:(str(r['node']).startswith('concept-'),r['n']),reverse=True)
        related=related[:60]
        selected = [center, *(by_id[r['node']] for r in related)]
        return {'nodes': [{'id': r['public_id'], 'name': r['name'], 'research_count': r['research_count'],
                           'heat': r['activity'], 'recent_activity': r['activity'],
                           'average_started_at': r['average_started_at'] or '', 'latest_started_at': r['latest_started_at'] or ''} for r in selected],
                'edges': [{'source': public_id, 'target': by_id[r['node']]['public_id'],
                           'cooccurrence_count': r['n'], 'relation_score': r['n'] / (center['research_count'] + by_id[r['node']]['research_count'] - r['n'])} for r in related],
                'center': public_id, 'source': source}
    return api

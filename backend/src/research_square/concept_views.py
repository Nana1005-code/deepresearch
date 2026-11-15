"""Evidence-linked thematic views; separate from OpenAlex's official taxonomy."""
import json
from fastapi import APIRouter, HTTPException, Query


def router(store):
    api=APIRouter(prefix='/concepts')
    with store.connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS academic_concepts(id TEXT PRIMARY KEY,name TEXT,description TEXT);
        CREATE TABLE IF NOT EXISTS academic_concept_works(concept_id TEXT REFERENCES academic_concepts(id),work_id INTEGER REFERENCES openalex_works(id) ON DELETE CASCADE,evidence TEXT,PRIMARY KEY(concept_id,work_id));''')

    @api.get('/llm-graph')
    def graph():
        with store.connect() as db:
            nodes=[dict(r) for r in db.execute('''SELECT c.id,c.name,COUNT(*) research_count,COUNT(*) heat,COUNT(*) recent_activity,
                date(AVG(julianday(w.publication_date))) average_started_at,MAX(w.publication_date) latest_started_at
                FROM academic_concepts c JOIN academic_concept_works cw ON cw.concept_id=c.id JOIN openalex_works w ON w.id=cw.work_id GROUP BY c.id''')]
            edges=[dict(r) for r in db.execute('''SELECT a.concept_id source,b.concept_id target,COUNT(*) cooccurrence_count
                FROM academic_concept_works a JOIN academic_concept_works b ON a.work_id=b.work_id AND a.concept_id<b.concept_id GROUP BY a.concept_id,b.concept_id''')]
        counts={n['id']:n['research_count'] for n in nodes}
        for e in edges:e['relation_score']=e['cooccurrence_count']/(counts[e['source']]+counts[e['target']]-e['cooccurrence_count'])
        edges.sort(key=lambda e:e['cooccurrence_count'],reverse=True)
        kept=[];degrees={n['id']:0 for n in nodes}
        for e in edges:
            a,b=e['source'],e['target']
            root='concept-llm' in (a,b)
            if not root and (degrees[a]>=4 or degrees[b]>=4):continue
            degrees[a]+=1;degrees[b]+=1;kept.append(e)
        return {'nodes':nodes,'edges':kept,'source':'paper_evidence'}

    @api.get('/{identifier}')
    def detail(identifier:str,q:str='',sort:str='citations',limit:int=Query(5,ge=1,le=100),offset:int=Query(0,ge=0)):
        order={'citations':'w.cited_by_count DESC,w.id DESC','citations_asc':'w.cited_by_count ASC,w.id ASC','latest':'w.publication_date DESC,w.id DESC','oldest':'w.publication_date ASC,w.id ASC'}.get(sort,'w.cited_by_count DESC,w.id DESC')
        with store.connect() as db:
            concept=db.execute('SELECT * FROM academic_concepts WHERE id=?',(identifier,)).fetchone()
            if not concept:raise HTTPException(404,'专题节点不存在')
            stats=dict(db.execute('''SELECT COUNT(*) works,COALESCE(SUM(w.cited_by_count),0) citations FROM academic_concept_works cw JOIN openalex_works w ON w.id=cw.work_id WHERE cw.concept_id=?''',(identifier,)).fetchone())
            filters=" AND (w.title LIKE ? OR w.abstract LIKE ? OR w.authors_json LIKE ? OR w.source_name LIKE ?)" if q.strip() else ''
            params=[identifier,*(['%'+q.strip()+'%']*4 if q.strip() else [])]
            join='FROM academic_concept_works cw JOIN openalex_works w ON w.id=cw.work_id WHERE cw.concept_id=?'+filters
            total=db.execute('SELECT COUNT(*) '+join,params).fetchone()[0]
            works=[dict(r) for r in db.execute('SELECT w.*,cw.evidence '+join+' ORDER BY '+order+' LIMIT ? OFFSET ?',[*params,limit,offset])]
        for w in works:w['authors']=json.loads(w.pop('authors_json') or '[]')
        return {'public_id':identifier,'name':concept['name'],'summary_zh':concept['description'],
                'aliases':[],'domains':[],'stats':dict(stats,source_topics=0),'works':works,'total':total,'limit':limit,'source':'paper_evidence'}
    return api

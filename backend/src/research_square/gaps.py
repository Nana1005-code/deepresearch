"""Gap analysis over the same evidence-backed memberships as node search."""
import math
import re
from .node_search import catalog, membership
from .store import normalize_name


def resolve(question, rows):
    text = normalize_name(question)
    hits = []
    for row in rows:
        for label in [row['name'], *row['aliases']]:
            key = normalize_name(label)
            if not key: continue
            found = key in text
            if re.fullmatch(r'[a-z0-9.+#]{2,12}', key):
                found = bool(re.search(r'(?<![a-z0-9])'+re.escape(label.casefold())+r'(?![a-z0-9])', question.casefold()))
            if found: hits.append((len(key), key, row))
    hits.sort(key=lambda hit:hit[0], reverse=True)
    selected=[]; labels=[]
    for _,key,row in hits:
        if any(key in label for label in labels): continue
        if any(row['id']==other['id'] for other in selected): continue
        selected.append(row);labels.append(key)
    if selected: return selected[:3]
    cleaned = question
    for token in ('从我的研究历史来看','从我的研究来看','还有哪些','相关的研究主题','相关主题','研究主题','是我遗漏的','我之前遗忘了','我没有关注','我未关注','可以了解','可以学习','关于','对于','请问','有哪些','遗漏方向','遗漏的方向','遗漏','方向'):
        cleaned=cleaned.replace(token,' ')
    fragments=[normalize_name(s) for s in re.split(r'[\s，,？?：:“”"]+',cleaned) if len(s.strip())>=2]
    candidates=[]
    for row in rows:
        score=max((len(f)/len(k) for f in fragments for label in [row['name'],*row['aliases']] if (k:=normalize_name(label)) and f in k),default=0)
        if score: candidates.append((score,row))
    candidates.sort(key=lambda item:(item[0],item[1]['research_count']),reverse=True)
    return [r for _,r in candidates[:3]]


def candidates(store, question, limit=10):
    rows=catalog(store,'openalex'); by_id={row['id']:row for row in rows}
    targets=resolve(question,rows)
    if not targets: return {'error':'missing_topic','message':'没有识别到图谱中的主题，请使用节点名称或别名。'}
    ids=[r['id'] for r in targets]
    with store.connect() as db:
        members={}
        for row in db.execute(membership('openalex')):
            members.setdefault(row['node'],set()).add(row['work'])
        target_works=set().union(*(members.get(i,set()) for i in ids))
        personal={}; all_imports=set()
        for row in db.execute("""SELECT t.canonical_name,r.id FROM topics t JOIN research_topics rt ON rt.topic_id=t.id
            JOIN public_researches r ON r.id=rt.research_id WHERE r.status='published' AND r.data_origin='user'"""):
            personal.setdefault(normalize_name(row[0]),set()).add(row[1]);all_imports.add(row[1])
        direct={}
        for row in db.execute("""SELECT m.canonical_topic_id,r.id FROM topic_openalex_mappings m
            JOIN research_topics rt ON rt.topic_id=m.topic_id JOIN public_researches r ON r.id=rt.research_id
            WHERE r.status='published' AND r.data_origin='user'"""):
            direct.setdefault(row[0],set()).add(row[1])
    suggestions=[]
    for key,row in by_id.items():
        if key in ids: continue
        works=members.get(key,set()); shared=len(works & target_works)
        if not shared: continue
        imports=set(direct.get(key,set()))
        for label in [row['name'],*row['aliases']]: imports.update(personal.get(normalize_name(label),set()))
        relation=shared/len(works | target_works)
        suggestions.append(dict(public_id=row['public_id'],name=row['name'],original_name=row['name'],cooccurrence_count=shared,
            academic_work_count=len(works),relation_score=round(relation,6),my_research_count=len(imports),
            discovery_score=round(relation*math.log1p(shared)/(1+len(imports)),6)))
    suggestions.sort(key=lambda r:(r['discovery_score'],r['cooccurrence_count']),reverse=True)
    return dict(matched_topics=[r['name'] for r in targets],my_total_imports=len(all_imports),suggestions=suggestions[:limit],source='openalex_and_local_history')

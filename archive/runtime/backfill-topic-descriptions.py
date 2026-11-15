import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend/src'))
from storage import Store
from research_square.store import ResearchSquareStore
from research_square.topic_descriptions import generate
main=Store();store=ResearchSquareStore();profile=main.profile(main.profiles()[0]['id'])
with store.connect() as db:
    rows=db.execute("SELECT public_id,canonical_name FROM topics WHERE status='active' AND (description IS NULL OR description='')").fetchall()
topics=[]
for row in rows:
    detail=store.community_topic_detail(row['public_id'])
    topics.append({'id':row['public_id'],'name':row['canonical_name'],'context':[r['research_input'][:180] for r in detail['researches'][:2]]})
def batch(items):
    result=generate(profile,items)
    with store.connect() as db:
        db.executemany("UPDATE topics SET description=? WHERE public_id=? AND (description IS NULL OR description='')",[(text,identifier) for identifier,text in result.items()])
    return len(result)
done=0
with ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(batch,topics[i:i+5]) for i in range(0,len(topics),5)]
    for future in as_completed(futures):
        try:done+=future.result();print('Saved',done,'/',len(topics),flush=True)
        except Exception as exc:print('Batch failed:',type(exc).__name__,flush=True)
with store.connect() as db:
    missing=db.execute("SELECT COUNT(*) FROM topics WHERE status='active' AND (description IS NULL OR description='')").fetchone()[0]
print('Remaining:',missing,flush=True)

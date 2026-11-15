"""Local concurrent read/write smoke test for the Research Square repository."""
from __future__ import annotations
import argparse
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"backend"/"src"))
from research_square.store import ResearchSquareStore  # noqa: E402


def percentile(values, p):
    if not values:return 0
    ordered=sorted(values);return ordered[min(len(ordered)-1,int((len(ordered)-1)*p))]


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--reads",type=int,default=500);parser.add_argument("--writes",type=int,default=100);parser.add_argument("--workers",type=int,default=32);args=parser.parse_args()
    store=ResearchSquareStore()
    with store.connect() as db:ids=[x[0] for x in db.execute("SELECT public_id FROM public_researches WHERE status='published' LIMIT 5000")]
    if not ids:raise SystemExit("没有公开研究，请先运行 seed.py")
    rng=random.Random(20261104);jobs=[]
    for i in range(args.reads):
        mode=i%4
        jobs.append(("read",lambda m=mode: store.hot_topics(30,None,15) if m==0 else store.graph(30,None,40) if m==1 else store.list_researches(sort="heat",limit=20,offset=rng.randint(0,max(0,len(ids)-20))) if m==2 else store.get_research(rng.choice(ids))))
    for i in range(args.writes):
        public_id=rng.choice(ids);jobs.append(("write",lambda p=public_id,n=i:store.record_action(p,f"load-user-{n}","view",f"load-{uuid4().hex}")))
    rng.shuffle(jobs);latencies={"read":[],"write":[]};errors=[];started=time.perf_counter()
    def execute(kind,fn):
        tick=time.perf_counter();fn();return kind,(time.perf_counter()-tick)*1000
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(execute,*job) for job in jobs]
        for future in as_completed(futures):
            try:kind,elapsed=future.result();latencies[kind].append(elapsed)
            except Exception as exc:errors.append(type(exc).__name__+": "+str(exc))
    wall=time.perf_counter()-started
    result={"requests":len(jobs),"workers":args.workers,"seconds":round(wall,3),"rps":round(len(jobs)/wall,2),"errors":len(errors)}
    for kind,values in latencies.items():result[kind]={"count":len(values),"p50_ms":round(percentile(values,.5),2),"p95_ms":round(percentile(values,.95),2),"p99_ms":round(percentile(values,.99),2)}
    if errors:result["sample_errors"]=errors[:5]
    print(result);raise SystemExit(1 if errors else 0)


if __name__=="__main__":main()

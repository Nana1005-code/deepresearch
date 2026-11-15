import sys,json,requests
from concurrent.futures import ThreadPoolExecutor,as_completed
from quality.authenticity import verify
run='f1bc957e273a474e815a4914b2136b7e'
a=requests.get('http://127.0.0.1:8000/quality/audit/'+run).json()
rows=a['references']
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(verify,r,True):r for r in rows}
    for f in as_completed(futures):
        r=futures[f];v=f.result();results.append(dict(title=r['title'],**v));print(v['status'],r['title'][:70],v['reason'],flush=True)
print('TOTAL',len(results),'REAL',sum(r['status']=='real' for r in results),flush=True)
open('.runtime/auth-improved-results.json','w',encoding='utf-8').write(json.dumps(results,ensure_ascii=False,indent=2))

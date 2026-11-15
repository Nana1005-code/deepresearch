import httpx,json,time
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=30);rid=json.loads(Path('.runtime/network-run.json').read_text())['run'];d=c.get('/research-runs/'+rid).json();tasks=next(x['event']['tasks'] for x in reversed(d['events']) if x['event']['type'] in ['todo_list','tasks_updated']);t=tasks[0]
r=c.put('/research-runs/'+rid+'/tasks',json={'tasks':[{'id':t['id'],'title':'asyncio 核心用途（修改验收）','intent':'查询Python官方文档，说明asyncio用于I/O并发。'},{'title':'asyncio 局限（新增验收）','intent':'查询Python官方文档，简述asyncio不适合CPU密集计算的原因。'}]});r.raise_for_status();print('TASK EDIT ACCEPTED',flush=True)
for n in range(36):
 time.sleep(5);d=c.get('/research-runs/'+rid).json()
 if n%6==0:print('TASK EDIT STATE',d['record']['status'],flush=True)
 if d['record']['status']!='running':break
Path('.runtime/task-edit-result.json').write_text(json.dumps(d,ensure_ascii=False),encoding='utf8');print('TASK EDIT FINAL',d['record']['status'],flush=True)

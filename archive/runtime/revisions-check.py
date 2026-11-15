import httpx,json,time
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=30);rid=json.loads(Path('.runtime/network-run.json').read_text())['run'];results=[]
def wait(label):
 for n in range(36):
  time.sleep(5);d=c.get('/research-runs/'+rid).json()
  if n%6==0:print(label,d['record']['status'],flush=True)
  if d['record']['status']!='running':break
 Path('.runtime/'+label+'.json').write_text(json.dumps(d,ensure_ascii=False),encoding='utf8');return d
d=c.get('/research-runs/'+rid).json();tasks=next(x['event']['tasks'] for x in reversed(d['events']) if x['event']['type'] in ['todo_list','tasks_updated']);t=tasks[0];r=c.put('/research-runs/'+rid+'/tasks',json={'tasks':[{'id':t['id'],'title':t['title'],'intent':t['intent']}]});r.raise_for_status();d=wait('task-delete-result');results.append({'test':'delete task','status':d['record']['status'],'revision':d['record']['revision']});r=c.put('/research-runs/'+rid+'/topic',json={'topic':'主题修改验收：Python asyncio 与线程的区别，请只规划1个任务，优先引用官方文档。'});r.raise_for_status();d=wait('topic-edit-result');results.append({'test':'edit topic','status':d['record']['status'],'revision':d['record']['revision']});Path('.runtime/revisions-results.json').write_text(json.dumps(results));print(results,flush=True)

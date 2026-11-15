import json,httpx,time
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=45);ctx=json.loads(Path('.runtime/test-context.json').read_text(encoding='utf8'));p=ctx['profile'];res={}
v=c.post('/conversations',json={}).json();r=c.post('/conversations/'+v['id']+'/messages',json={'question':'请只回复测试成功。','model_profile_id':p});res['chat']={'status':r.status_code,'body':r.json()};print('chat',res['chat'],flush=True)
r=c.post('/research-runs',json={'topic':'验收测试：Python asyncio 的用途，仅规划一个任务，报告限200字。','model_profile_id':p,'search_api':'duckduckgo'});res['research_submit']={'status':r.status_code,'id':r.json().get('id')};print('research',res['research_submit'],flush=True)
res['graph_import']=c.get('/research-square/import-status/'+ctx['run']).json();Path('.runtime/model-results.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf8')

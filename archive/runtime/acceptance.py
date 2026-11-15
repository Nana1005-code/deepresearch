import io,json,time,zipfile,sqlite3
from pathlib import Path
import httpx
from docx import Document
root=Path.cwd(); out=root/'.runtime'; c=httpx.Client(base_url='http://127.0.0.1:8000',timeout=50,trust_env=False)
results=[]
def check(name,fn):
 try:
  detail=fn(); results.append({'name':name,'status':'PASS','detail':detail}); print(name, 'PASS',str(detail)[:200],flush=True)
 except Exception as e:
  results.append({'name':name,'status':'FAIL','detail':str(e)[:350]}); print(name,'FAIL',str(e)[:200],flush=True)
def request(method,path,**kwargs):
 r=c.request(method,path,**kwargs);r.raise_for_status();return r.json()
p=request('GET','/model-profiles')[0]['id']; runs=request('GET','/research-runs'); run=next(x for x in runs if x['status']=='completed'); rid=run['id']; detail=request('GET','/research-runs/'+rid); report=next(x['event']['report'] for x in reversed(detail['events']) if x['event']['type']=='final_report')
(out/'test-context.json').write_text(json.dumps({'profile':p,'run':rid,'title':run['topic']},ensure_ascii=False),encoding='utf8')
check('health',lambda:request('GET','/healthz'))
check('history',lambda:{'runs':len(runs),'events':len(detail['events']),'report_chars':len(report)})
def quality():
 before=request('GET','/research-runs/'+rid); a=request('GET','/quality/audit/'+rid); b=request('GET','/quality/audit/'+rid); after=request('GET','/research-runs/'+rid)
 a.pop('generated_at',None);b.pop('generated_at',None);assert a==b;assert before==after
 for style in ['plain','gbt7714-lite']:
  q=request('POST','/quality/report',json={'run_id':rid,'style':style});assert q['markdown'];(out/('quality-'+style+'.md')).write_text(q['markdown'],encoding='utf8')
 (out/'quality.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf8');return {'score':a['score'],'grade':a['grade'],'issues':len(a['issues']),'read_only':True,'idempotent':True}
check('quality-audit-report-readonly',quality)
def export():
 r=c.post('/export/word',json={'title':'验收样例研究报告','markdown':report});r.raise_for_status();doc=Document(io.BytesIO(r.content));assert len(doc.paragraphs)>5;(out/'export-test.docx').write_bytes(r.content);return {'bytes':len(r.content),'paragraphs':len(doc.paragraphs)}
check('word-export',export)
def notes():
 n=request('POST','/notes',json={'title':'验收测试笔记','html':'<p>测试笔记</p>','run_id':rid}); nid=n['id'];request('PUT','/notes/'+nid,json={'title':'验收测试笔记已编辑','html':'<p>修改成功</p>','run_id':rid});assert '修改成功' in request('GET','/notes/'+nid)['html'];request('DELETE','/notes/'+nid);assert c.get('/notes/'+nid).status_code==404;return 'create/read/update/delete passed'
check('notes-CRUD',notes)
def marks():
 path='/reading/'+rid+'/acceptance-test';request('PUT',path+'/marks',json={'marks':[{'start':0,'end':2,'text':'测试'}]});assert len(request('GET',path)['marks'])==1;request('PUT',path+'/marks',json={'marks':[]});assert not request('GET',path)['marks'];return 'highlight saved and cleared'
check('highlights',marks)
def documents():
 buf=io.BytesIO();d=Document();d.add_paragraph('验收本地资料：检索增强生成结合外部文档和生成模型。');d.save(buf)
 from pypdf import PdfWriter
 pdf=PdfWriter();pdf.add_blank_page(width=300,height=200);pb=io.BytesIO();pdf.write(pb)
 data=[('acceptance.txt','验收资料TXT：检索增强生成以外部知识作为参考。'.encode()),('acceptance.md','# 验收资料MD\n测试来源编号abc123。'.encode()),('acceptance.docx',buf.getvalue())]
 output=[]
 for name,body in data:
  r=c.post('/documents',files={'file':(name,body)});r.raise_for_status(); rec=r.json();did=rec['id'];assert c.post('/documents',files={'file':(name,body)}).status_code==409;download=c.get('/documents/'+did+'/download');assert download.content==body;assert c.delete('/documents/'+did).status_code==204;output.append(name)
 assert c.post('/documents',files={'file':('blocked.exe',b'abc')}).status_code==400
 return {'formats':output,'duplicate':409,'unsupported':400,'roundtrip':True}
check('local-documents',documents)
check('openalex-metadata',lambda:request('GET','/research-square/openalex/overview'))
check('openalex-graph',lambda:request('GET','/research-square/openalex/graph?days=365'))
check('graph-empty-state',lambda:request('GET','/research-square/graph'))
check('gap-helper-no-model',lambda:request('POST','/research-square/chat',json={'question':'人工智能还有哪些尚未研究方向？','data_source':'local'}))
check('academic-helper-no-model',lambda:request('POST','/research-square/chat',json={'question':'有哪些热门主题？','data_source':'openalex'}))
check('personal-graph-submit',lambda:request('POST','/research-square/publish',json={'source_run_id':rid,'model_profile_id':p}))
check('personal-graph-duplicate',lambda: {'status':c.post('/research-square/publish',json={'source_run_id':rid,'model_profile_id':p}).status_code})
(out/'api-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8'); print('RESULTS',len(results),flush=True)


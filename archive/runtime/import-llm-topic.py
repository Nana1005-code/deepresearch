import sys,json,re,importlib.util,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend/src'))
spec=importlib.util.spec_from_file_location('oa',root/'scripts/research_square/import_openalex.py');oa=importlib.util.module_from_spec(spec);spec.loader.exec_module(oa)
store=oa.ResearchSquareStore()
queries=['"large language model"','"multimodal large language model"','(hallucination AND (detection OR evaluation OR benchmark)) AND ("large language model" OR "vision language model" OR "multimodal model")']
works={}
with oa.httpx.Client(timeout=60) as client:
 for query in queries:
  data=oa.fetch_page(client,{'search.title_and_abstract':query,'filter':'from_publication_date:2022-01-01,to_publication_date:2026-11-15,has_abstract:true','per_page':100,'select':oa.SELECT_FIELDS,'sort':'cited_by_count:desc'})
  for work in data.get('results',[]):works[oa.short_id(work['id'])]=work
  print('Fetched',len(data.get('results',[])),query,flush=True)
Path(root/'.runtime/llm-openalex-source.json').write_text(json.dumps(list(works.values()),ensure_ascii=False),encoding='utf-8')
with sqlite3.connect(store.path) as src,sqlite3.connect(root/'.runtime/before-llm-curation.sqlite3') as dest:src.backup(dest)
llm=re.compile(r'large[ -](?:language|vision.language|multimodal)[ -]models?|\b(?:llms?|mllms?|lvlms?)\b',re.I)
selected=[w for w in works.values() if llm.search(w['title']+' '+(oa.reconstruct_abstract(w.get('abstract_inverted_index')) or ''))]
oa.upsert_page(store,selected)
with store.connect() as db:
 start=db.execute("SELECT MIN(started_at) FROM openalex_import_runs WHERE public_id IN ('ab6e0f18399340b497a99cbb483e6e80','db246bd1fc1548c4a26bebacfd5a0603','8b79c4a400f94e9185da26e2497a402f')").fetchone()[0]
 rows=db.execute('SELECT id,title,abstract FROM openalex_works WHERE imported_at>=?',(start,)).fetchall()
 excluded=[r['id'] for r in rows if not llm.search(r['title']+' '+(r['abstract'] or ''))]
 for identifier in excluded:db.execute('DELETE FROM openalex_works WHERE id=?',(identifier,))
 db.executescript('''CREATE TABLE IF NOT EXISTS academic_concepts(id TEXT PRIMARY KEY,name TEXT,description TEXT);
 CREATE TABLE IF NOT EXISTS academic_concept_works(concept_id TEXT REFERENCES academic_concepts(id),work_id INTEGER REFERENCES openalex_works(id) ON DELETE CASCADE,evidence TEXT,PRIMARY KEY(concept_id,work_id));''')
 definitions=[('llm','大语言模型','通过大规模文本训练学习语言规律，用于理解、推理与生成的模型。本专题按论文标题和摘要中的明确术语整理。'),('mllm','多模态大模型','联合处理文本与图像等模态的大模型，关注跨模态理解、对齐与生成。论文须同时包含大模型与多模态或视觉语言相关证据。'),('hallucination','幻觉检测','研究如何识别、评估或基准测试大模型生成中缺乏依据的内容；同时覆盖语言和多模态场景。')]
 for identifier,name,description in definitions:db.execute('INSERT OR REPLACE INTO academic_concepts VALUES(?,?,?)',('concept-'+identifier,name,description))
 multi=re.compile(r'multi[ -]?modal|vision[ -]language|visual[ -]language|\b(?:mllms?|lvlms?)\b',re.I)
 hall=re.compile(r'hallucinat',re.I);detect=re.compile(r'detect|evaluat|benchmark|assess|identif',re.I)
 rows=db.execute('SELECT id,title,abstract FROM openalex_works WHERE imported_at>=?',(start,)).fetchall()
 for r in rows:
  text=r['title']+' '+(r['abstract'] or '')
  labels=['llm'] if llm.search(text) else []
  if labels and multi.search(text):labels.append('mllm')
  if labels and hall.search(text) and detect.search(text):labels.append('hallucination')
  for label in labels:db.execute('INSERT OR REPLACE INTO academic_concept_works VALUES(?,?,?)',('concept-'+label,r['id'],text))
 print('Excluded unrelated new rows',len(excluded),flush=True)
 print('Concept counts',[tuple(r) for r in db.execute('SELECT c.name,COUNT(*) FROM academic_concepts c JOIN academic_concept_works cw ON cw.concept_id=c.id GROUP BY c.id')],flush=True)
 print('Total works',db.execute('SELECT COUNT(*) FROM openalex_works').fetchone()[0],flush=True)

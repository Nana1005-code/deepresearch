import sys,json,re
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0,str(Path('backend/src').resolve()))
load_dotenv('backend/.env',override=True)
from agent import DeepResearchAgent
from config import Configuration
from models import SummaryState,TodoItem
from services.tool_protocol import has_tool_protocol
cfg=Configuration.from_env({'notes_workspace':str(Path('.runtime/tool-fix-live-notes').resolve()),'llm_max_tokens':4096})
a=DeepResearchAgent(cfg)
result=a.note_tool.run({'action':'create','title':'协议修复验收','content':'项目编号DSML-8472。流程分为资料采集、交叉核验、生成报告三个阶段。此资料仅用于软件验收。','note_type':'task_state','tags':['test']})
note_id=re.search(r'ID: (\S+)',result)[1]
task=TodoItem(id=1,title='协议修复验收',intent='总结资料中的项目编号和阶段',query='DSML-8472',note_id=note_id)
summary=a.summarizer.summarize_task(SummaryState(research_topic='协议修复验收'),task,'唯一测试资料：项目编号DSML-8472；三个阶段为资料采集、交叉核验、生成报告。')
assert 'DSML-8472' in summary and not has_tool_protocol(summary)
Path('.runtime/tool-fix-live-summary.txt').write_text(summary,encoding='utf8')
print('LIVE_SUMMARY_OK',len(summary),flush=True)

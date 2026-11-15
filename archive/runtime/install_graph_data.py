from pathlib import Path
from datetime import datetime
import sqlite3,json,hashlib
root=Path.cwd();current=root/'backend/data/research_square.sqlite3';incoming=root/'.runtime/research-square-import/source.sqlite3'
backup=root/'backend/data/backups'/('research_square-before-demo-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3');backup.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(current) as live,sqlite3.connect(backup) as saved:live.backup(saved)
with sqlite3.connect(incoming.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(current) as live:
 assert source.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 assert not source.execute('PRAGMA foreign_key_check').fetchall()
 source.backup(live)
 assert live.execute('PRAGMA quick_check').fetchone()[0]=='ok'
 counts={t:live.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['openalex_works','openalex_topics','public_researches','topics']}
result={'database':str(current),'backup':str(backup),'counts':counts,'source':'research-square-demo-v1.zip'}
(root/'.runtime/research-square-import/result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))

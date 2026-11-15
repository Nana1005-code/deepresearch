from pathlib import Path
import zipfile,shutil,sqlite3,json
root=Path.cwd();dest=root/'.runtime/research-square-import/source.sqlite3';dest.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(r'C:/Users/admin/xwechat_files/wxid_ljfeul68q4no22_cd54/msg/file/2026-11/research-square-demo-v1.zip') as z:
 with z.open('research_square.sqlite3') as source,dest.open('wb') as target:shutil.copyfileobj(source,target)
for label,path in [('INCOMING',dest),('CURRENT',root/'backend/data/research_square.sqlite3')]:
 db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
 print(label,'CHECK',db.execute('PRAGMA quick_check').fetchone()[0])
 for name,sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
  print(label,name,db.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0])
  if label=='INCOMING':print('COLUMNS',[x[1] for x in db.execute('PRAGMA table_info("'+name+'")')]);print('FK',db.execute('PRAGMA foreign_key_list("'+name+'")').fetchall())
 db.close()

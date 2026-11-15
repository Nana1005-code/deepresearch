"""Rebase bundled document/note paths after moving the project (stdlib only)."""
from pathlib import Path
import json
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'

def rebase(value, key=''):
    if isinstance(value, dict): return {k: rebase(v, k) for k, v in value.items()}
    if isinstance(value, list): return [rebase(v, key) for v in value]
    if isinstance(value, str) and key in {'note_path', 'report_note_path', 'notes_workspace'}:
        normalized=value.replace('\\', '/')
        marker='/backend/notes/'
        if marker in normalized:
            tail=normalized.split(marker, 1)[1]
        elif normalized.startswith(('notes/', './notes/')):
            tail=normalized.split('notes/',1)[1]
        else:return value
        candidate=(BACKEND/'notes'/tail).resolve()
        if candidate.is_relative_to((BACKEND/'notes').resolve()):return str(candidate)
    return value

def main():
    path=BACKEND/'data/research.sqlite3'
    if not path.exists():
        raise SystemExit('Missing backend/data/research.sqlite3: copy the complete final_upload folder.')
    changed=0
    with sqlite3.connect(path) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'documents' in tables:
            for identifier,raw in db.execute('SELECT id,data FROM documents').fetchall():
                record=json.loads(raw)
                extension=record.get('extension','')
                if not re.fullmatch(r'[0-9a-f]{32}',identifier) or extension not in {'.pdf','.docx','.txt','.md','.markdown'}:
                    raise ValueError('Unexpected document identifier/extension')
                file=(BACKEND/'data/library_files'/f'{identifier}{extension}').resolve()
                if not file.is_file():raise FileNotFoundError(f'Missing bundled original: {file.name}')
                if record.get('stored_path')!=str(file):
                    record['stored_path']=str(file)
                    db.execute('UPDATE documents SET data=? WHERE id=?',(json.dumps(record,ensure_ascii=False),identifier));changed+=1
        for table in ('runs','events','reading_objects'):
            if table not in tables:continue
            for rowid,raw in db.execute(f'SELECT rowid,data FROM {table}').fetchall():
                old=json.loads(raw);new=rebase(old)
                if new!=old:
                    db.execute(f'UPDATE {table} SET data=? WHERE rowid=?',(json.dumps(new,ensure_ascii=False),rowid));changed+=1
    print(f'Portable data ready: {changed} path records updated; history retained.')

if __name__=='__main__':main()

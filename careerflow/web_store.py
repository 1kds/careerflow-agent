"""Persistent, local web archive, separate from the agent's scratch database."""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date


class WebStore:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS web_jobs (
                    id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL,
                    company TEXT, position TEXT, posting TEXT, deadline TEXT,
                    source_url TEXT, result TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS web_tasks (
                    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES web_jobs(id),
                    title TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT DEFAULT 'todo',
                    UNIQUE(job_id, title, due_date));
            ''')
            if 'deleted_at' not in {row[1] for row in db.execute('PRAGMA table_info(web_tasks)')}:
                db.execute('ALTER TABLE web_tasks ADD COLUMN deleted_at TEXT')
            db.commit()

    def query(self, sql, args=()):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            rows = db.execute(sql, args).fetchall()
            db.commit()
            return [dict(row) for row in rows]

    def save(self, payload, result):
        fields = [str(payload.get(k, '')).strip() for k in ('company', 'position', 'posting')]
        identity = hashlib.sha256(json.dumps([' '.join(x.split()).casefold() for x in fields]).encode()).hexdigest()
        return self.query('''INSERT INTO web_jobs(identity,company,position,posting,deadline,source_url,result)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET
            deadline=excluded.deadline,source_url=excluded.source_url,result=excluded.result,
            updated_at=CURRENT_TIMESTAMP RETURNING id''',
            (identity, *fields, str(payload.get('deadline', ''))[:20],
             str(payload.get('source_url', ''))[:2000], json.dumps(result, ensure_ascii=False)))[0]['id']

    def jobs(self):
        return self.query('SELECT id,company,position,deadline,updated_at FROM web_jobs ORDER BY updated_at DESC,id DESC')

    def detail(self, job_id):
        rows = self.query('SELECT * FROM web_jobs WHERE id=?', (job_id,))
        if not rows:
            raise ValueError('공고를 찾을 수 없습니다.')
        job = rows[0]
        job['result'] = json.loads(job['result'])
        job['tasks'] = self.query('SELECT * FROM web_tasks WHERE job_id=? AND deleted_at IS NULL ORDER BY id', (job_id,))
        return job

    def tasks(self):
        return self.query('''SELECT t.*,j.company,j.position FROM web_tasks t
            JOIN web_jobs j ON j.id=t.job_id WHERE t.deleted_at IS NULL ORDER BY t.status DESC,t.due_date,t.id''')

    def add_task(self, payload):
        if payload.get('approved') is not True:
            raise ValueError('할 일 내용을 확인한 뒤 등록을 승인해주세요.')
        job = self.detail(payload.get('job_id'))
        title = str(payload.get('title', '')).strip()
        if not 1 <= len(title) <= 300:
            raise ValueError('할 일은 1~300자로 입력해주세요.')
        due = date.fromisoformat(str(payload.get('due_date', '')))
        if job['deadline'] and due > date.fromisoformat(job['deadline']):
            raise ValueError('할 일 기한은 지원 마감일 이후로 지정할 수 없습니다.')
        # Serialize the check and insert, including requests from multiple tabs.
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id,due_date FROM web_tasks WHERE job_id=? AND title=? AND deleted_at IS NULL ORDER BY id LIMIT 1', (job['id'], title)).fetchone()
            if existing:
                db.commit()
                return {'ok': True, 'already_registered': True, 'task_id': existing[0], 'due_date': existing[1]}
            row = db.execute('''INSERT INTO web_tasks(job_id,title,due_date) VALUES(?,?,?)
                ON CONFLICT(job_id,title,due_date) DO UPDATE SET deleted_at=NULL,status='todo'
                RETURNING id''', (job['id'], title, due.isoformat())).fetchone()
            db.commit()
        return {'ok': True, 'task_id': row[0], 'due_date': due.isoformat()}

    def delete_tasks(self, payload):
        ids = payload.get('task_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 500 or any(type(i) is not int or i <= 0 for i in ids):
            raise ValueError('삭제할 할 일을 선택해주세요. 한 번에 최대 500개까지 가능합니다.')
        ids = list(set(ids))
        placeholders = ','.join('?' for _ in ids)
        rows = self.query(f'UPDATE web_tasks SET deleted_at=CURRENT_TIMESTAMP WHERE deleted_at IS NULL AND id IN ({placeholders}) RETURNING id', tuple(ids))
        return {'ok': True, 'deleted_count': len(rows)}

    def set_status(self, payload):
        if payload.get('status') not in ('todo', 'done'):
            raise ValueError('잘못된 진행 상태입니다.')
        rows = self.query('UPDATE web_tasks SET status=? WHERE id=? AND deleted_at IS NULL RETURNING id',
                          (payload['status'], payload.get('task_id')))
        if not rows:
            raise ValueError('할 일을 찾을 수 없습니다.')
        return {'ok': True}

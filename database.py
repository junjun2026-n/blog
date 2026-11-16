import json
import sqlite3
from pathlib import Path


class Record(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def record_factory(cursor):
    names = [column.name for column in cursor.description or []]
    return lambda values: Record(zip(names, values))


class Cursor:
    def __init__(self, raw, inserted=False):
        self.raw = raw
        self.lastrowid = raw.fetchone()[0] if inserted else None

    def fetchone(self):
        return self.raw.fetchone()

    def fetchall(self):
        return self.raw.fetchall()

    def __iter__(self):
        return iter(self.raw)


class PostgresConnection:
    def __init__(self, url):
        import psycopg
        self.raw = psycopg.connect(url, row_factory=record_factory, connect_timeout=10)

    def execute(self, query, params=None):
        if query == 'BEGIN IMMEDIATE':
            return self.raw.execute('SELECT pg_advisory_xact_lock(870001)')
        if query.startswith('PRAGMA table_info('):
            table = query.partition('(')[2].rstrip(')')
            return self.raw.execute('SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s', (table,))
        inserted = query.startswith(('INSERT INTO users(', 'INSERT INTO posts(', 'INSERT INTO comments('))
        query = query.replace('?', '%s').replace("datetime('now','localtime')", 'CAST(LOCALTIMESTAMP AS TEXT)').replace(' LIKE ', ' ILIKE ')
        if inserted:
            query += ' RETURNING id'
        return Cursor(self.raw.execute(query, params), inserted)

    def executescript(self, schema):
        schema = schema.replace('id INTEGER PRIMARY KEY', 'id BIGSERIAL PRIMARY KEY').replace(' COLLATE NOCASE', '').replace("datetime('now','localtime')", 'CAST(LOCALTIMESTAMP AS TEXT)')
        for statement in schema.split(';'):
            if statement.strip() and not statement.strip().startswith('PRAGMA'):
                self.raw.execute(statement)
        self.raw.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower ON users(lower(username))')
        self.raw.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower ON users(lower(email))')
        self.raw.commit()

    def executemany(self, query, params):
        for values in params:
            self.execute(query, values)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def database_url(root):
    import os
    if os.environ.get('BLOG_DATABASE_URL'):
        return os.environ['BLOG_DATABASE_URL']
    config = Path(root) / 'data/database.json'
    if config.exists():
        return json.loads(config.read_text(encoding='utf-8'))['url']
    return str(Path(root) / 'data/blog.sqlite3')


def connect(target):
    if str(target).startswith(('postgresql://', 'postgres://')):
        return PostgresConnection(target)
    connection = sqlite3.connect(target, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection

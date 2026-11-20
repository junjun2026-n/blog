# ============================================================
# 文件名称：migrate_postgres.py
# 生成日期：2026-11-16
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：执行 migrate_postgres 对应的启动、构建或运维任务。
#           文件用途：供博客的 BLOG/migrate_postgres.py 模块使用。
#           注意事项：运行前检查依赖与配置；涉及数据或服务变更时先备份并验证。
# ============================================================
"""Offline SQLite to empty PostgreSQL migration; verifies all table contents."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from app import create_app
from database import connect, database_url

ROOT = Path(__file__).resolve().parent
TABLES = ('settings', 'users', 'posts', 'comments')


def digest(rows):
    return hashlib.sha256(json.dumps([dict(row) for row in rows], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def migrate(source, target):
    if not str(target).startswith(('postgresql://', 'postgres://')):
        raise ValueError('Target must be PostgreSQL')
    # Create schema without inserting an administrator.
    create_app({'DATABASE': target, 'SEED_ADMIN': False})
    origin = sqlite3.connect(source)
    origin.row_factory = sqlite3.Row
    destination = connect(target)
    report = {}
    try:
        origin.execute('BEGIN')
        destination.execute('SELECT pg_advisory_xact_lock(870002)')
        for table in TABLES:
            if destination.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:
                raise ValueError(f'Target {table} is not empty; refusing overwrite')
        for table in TABLES:
            order = 'key' if table == 'settings' else 'id'
            rows = origin.execute(f'SELECT * FROM {table} ORDER BY {order}').fetchall()
            for row in rows:
                columns = ','.join(row.keys())
                placeholders = ','.join('?' for _ in row.keys())
                destination.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', tuple(row))
            copied = destination.execute(f'SELECT * FROM {table} ORDER BY {order}').fetchall()
            if digest(rows) != digest(copied):
                raise ValueError(f'Content verification failed: {table}')
            report[table] = {'rows': len(rows), 'sha256': digest(rows)}
            if table != 'settings':
                destination.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'),COALESCE(MAX(id),1),MAX(id) IS NOT NULL) FROM {table}")
        destination.commit()
    except Exception:
        destination.rollback()
        raise
    finally:
        destination.close()
        origin.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(ROOT/'data/blog.sqlite3'))
    args = parser.parse_args()
    print(json.dumps(migrate(args.source, database_url(ROOT)), indent=2))

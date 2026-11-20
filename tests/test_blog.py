# ============================================================
# 文件名称：test_blog.py
# 生成日期：2026-11-11
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：验证 blog 相关功能。
#           文件用途：用于开发验证及功能回归。
#           注意事项：使用隔离测试环境，避免操作正式业务数据。
# ============================================================
import re
import sqlite3

import pytest

from app import create_app


@pytest.fixture(params=['sqlite', 'postgresql'] if __import__('os').getenv('BLOG_TEST_POSTGRES_URL') else ['sqlite'])
def site(tmp_path, monkeypatch, request):
    monkeypatch.setenv('BLOG_ADMIN_PASSWORD', 'TestAdmin123!')
    if request.param == 'sqlite':
        yield create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'test.sqlite3')})
        return
    import os
    import uuid
    import psycopg
    from psycopg import sql
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    url = os.environ['BLOG_TEST_POSTGRES_URL']
    schema = 'blog_test_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        parts = urlsplit(url)
        args = dict(parse_qsl(parts.query))
        args['options'] = '-csearch_path=' + schema
        target = urlunsplit(parts._replace(query=urlencode(args)))
        try:
            yield create_app({'TESTING': True, 'DATABASE': target})
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def submit(client, url, data=None, token_page='/login'):
    html = client.get(token_page).get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    return client.post(url, data={**(data or {}), 'csrf_token':token})


def register(client, name='alice'):
    return submit(client, '/register', {'username':name, 'email':name+'@example.com', 'password':'Password123!', 'confirm':'Password123!'})


def login(client, name='alice', password='Password123!'):
    return submit(client, '/login', {'username':name,'password':password})


def write(client, **changes):
    return submit(client, '/write', {'title':'测试文章','content':'# Hello\n\n这是内容','category':'技术','published':'on','comments_open':'on',**changes})


def test_registration_and_login(site):
    c = site.test_client()
    assert register(c).status_code == 302
    assert login(c).status_code == 302
    assert 'alice' in c.get('/').get_data(as_text=True)
    assert register(c).status_code == 200
    assert c.get('/account').status_code == 200


def test_author_can_close_comments_and_server_enforces(site):
    c = site.test_client()
    register(c)
    login(c)
    assert write(c).status_code == 302
    assert submit(c,'/posts/1/comment',{'content':'第一条评论'}).status_code == 302
    assert submit(c,'/posts/1/edit',{'title':'已关闭评论','content':'正文','category':'随笔','published':'on'}).status_code == 302
    assert submit(c,'/posts/1/comment',{'content':'不允许'}).status_code == 403
    html = c.get('/posts/1').get_data(as_text=True)
    assert '作者已关闭这篇文章的评论' in html
    assert '第一条评论' in html


def test_permissions_and_draft_visibility(site):
    owner, other = site.test_client(), site.test_client()
    register(owner)
    login(owner)
    write(owner)
    submit(owner,'/posts/1/edit',{'title':'私人草稿','content':'正文','category':'随笔'})
    register(other,'bob')
    login(other,'bob')
    assert other.get('/posts/1').status_code == 404
    assert other.get('/posts/1/edit').status_code == 403
    assert submit(other,'/posts/1/delete').status_code == 403
    assert other.get('/admin').status_code == 403
    assert '私人草稿' not in other.get('/').get_data(as_text=True)
    assert owner.get('/posts/1').status_code == 200


def test_admin_management(site):
    c, admin = site.test_client(), site.test_client()
    register(c)
    login(c)
    write(c)
    submit(c,'/posts/1/comment',{'content':'测试评论'})
    login(admin,'admin','TestAdmin123!')
    for tab in ('posts','users','comments'):
        assert admin.get('/admin?tab='+tab).status_code == 200
    assert submit(admin,'/admin/users/2',{'action':'password','password':'NewPassword123!'}).status_code == 302
    fresh = site.test_client()
    login(fresh,'alice','NewPassword123!')
    assert fresh.get('/mine').status_code == 200
    submit(admin,'/admin/users/2',{'action':'toggle_active'})
    assert c.get('/mine').status_code == 302
    assert submit(admin,'/comments/1/delete').status_code == 302
    assert submit(admin,'/posts/1/delete').status_code == 302


def test_csrf_and_safe_rendering(site):
    c = site.test_client()
    assert c.post('/register',data={'username':'bad'}).status_code == 400
    register(c)
    login(c)
    write(c, content='<script>alert(1)</script>\n\n[恶意链接](javascript:alert(1))',title='<img src=x onerror=alert(1)>')
    html = c.get('/posts/1').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert 'href="javascript:' not in html
    assert '<img src=x onerror=' not in html


def test_comment_delete_authorization(site):
    owner, other, stranger = [site.test_client() for _ in range(3)]
    for client,name in ((owner,'alice'),(other,'bob'),(stranger,'carol')):
        register(client,name)
        login(client,name)
    write(owner)
    submit(other,'/posts/1/comment',{'content':'评论'})
    assert submit(stranger,'/comments/1/delete').status_code == 403
    assert submit(owner,'/comments/1/delete').status_code == 302


def test_account_password_change(site):
    c = site.test_client()
    register(c)
    login(c)
    submit(c,'/account',{'old_password':'Password123!','password':'Changed123!','confirm':'Changed123!'})
    fresh = site.test_client()
    login(fresh,'alice','Changed123!')
    assert fresh.get('/mine').status_code == 200

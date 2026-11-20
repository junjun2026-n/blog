# ============================================================
# 文件名称：test_database_settings.py
# 生成日期：2026-11-16
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：验证 database_settings 相关功能。
#           文件用途：用于开发验证及功能回归。
#           注意事项：使用隔离测试环境，避免操作正式业务数据。
# ============================================================
from test_blog import site, login, register, submit


def test_database_configuration_requires_administrator(site):
    client=site.test_client()
    assert client.get('/admin/database').status_code==302
    register(client)
    login(client)
    assert client.get('/admin/database').status_code==403
    login(client,'admin','TestAdmin123!')
    response=client.get('/admin/database')
    assert response.status_code==200
    assert b'name="password"' in response.data
    result=submit(client,'/admin/database',dict(host='127.0.0.1',port='1',database='missing',user='test',password='private-test-secret',sslmode='prefer',action='initialize'),token_page='/admin/database')
    assert result.status_code==200
    assert 'private-test-secret' not in result.get_data(as_text=True)
    assert client.get('/').status_code==200

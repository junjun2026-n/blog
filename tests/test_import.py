# ============================================================
# 文件名称：test_import.py
# 生成日期：2026-11-11
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：验证 import 相关功能。
#           文件用途：用于开发验证及功能回归。
#           注意事项：使用隔离测试环境，避免操作正式业务数据。
# ============================================================
import io
import zipfile
import pytest
from document_import import import_document
from test_blog import site, login, submit


def test_text_and_json():
    assert import_document('中文.txt', '## 原样显示\n你好'.encode('utf-8-sig'))['content_format'] == 'text'
    assert import_document('test.md', b'# Heading')['content_format'] == 'markdown'
    assert '测试' in import_document('test.json', '{"名称":"测试"}'.encode())['content']
    for name, data in [('test.json', b'{broken'), ('bad.txt', b'\xff'), ('bad.doc', b'bad'), ('bad.docx', b'bad'), ('large.txt', b'x' * (1024*1024+1))]:
        with pytest.raises(ValueError):
            import_document(name, data)


def test_word_conversion():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Word 中文正文</w:t></w:r></w:p></w:body></w:document>')
    assert 'Word 中文正文' in import_document('测试.docx', buf.getvalue())['content']


def test_import_api_and_persistence(site):
    c = site.test_client()
    login(c, 'admin', 'TestAdmin123!')
    assert 'document-file' in c.get('/write').get_data(as_text=True)
    response = submit(c, '/api/import', {'file': (io.BytesIO(b'{"hello":123}'), 'example.json')})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['content_format'] == 'json'
    assert submit(c, '/write', {**payload, 'category':'技术', 'published':'on'}).status_code == 302
    html = c.get('/posts/1').get_data(as_text=True)
    assert 'plain-content' in html and 'hello' in html
    assert '<script>' not in submit(c, '/api/preview', {'content':'<script>x</script>', 'content_format':'text'}).get_json()['html']
    assert submit(c, '/write', {'title':'bad','category':'test','content':'bad','content_format':'json'}).status_code == 400
    assert site.test_client().post('/api/import').status_code == 400

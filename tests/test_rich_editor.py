import io
from PIL import Image
from test_blog import site, login, submit


def test_image_upload_and_publish(site, tmp_path):
    site.config['UPLOAD_FOLDER'] = str(tmp_path / 'images')
    c = site.test_client()
    login(c,'admin','TestAdmin123!')
    image = io.BytesIO()
    Image.new('RGB',(40,30),'red').save(image,'PNG')
    response = submit(c,'/api/images',{'file':(io.BytesIO(image.getvalue()),'test.png')})
    assert response.status_code == 200
    url = response.get_json()['url']
    fetched = c.get(url)
    assert fetched.status_code == 200 and fetched.content_type == 'image/webp'
    assert fetched.headers['X-Content-Type-Options'] == 'nosniff'
    html = f'<h2>图文文章</h2><p><strong>加粗</strong></p><img src="{url}" alt="图片"><table><tr><td>表格</td></tr></table>'
    assert submit(c,'/write',{'title':'图文','category':'测试','content':html,'content_format':'html','published':'on'}).status_code == 302
    page = c.get('/posts/1').get_data(as_text=True)
    assert '<strong>加粗</strong>' in page and f'src="{url}"' in page and '<td>表格</td>' in page
    assert 'rich-editor.js' in c.get('/posts/1/edit').get_data(as_text=True)
    assert submit(c,'/api/images',{'file':(io.BytesIO(b'<svg onload="alert(1)"></svg>'),'bad.svg')}).status_code == 400
    assert submit(c,'/api/images',{'file':(io.BytesIO(b'x'*(5*1024*1024+1)),'big.png')}).status_code == 400


def test_rich_html_sanitized(site):
    c = site.test_client()
    login(c,'admin','TestAdmin123!')
    html='<p style="color: red; position: fixed" onclick="alert(1)">文字</p><img src="https://evil.test/a" onerror="alert(1)"><a href="javascript:alert(1)">link</a><iframe src="https://evil.test"></iframe>'
    rendered=submit(c,'/api/preview',{'content':html,'content_format':'html'}).get_json()['html']
    assert 'onclick' not in rendered and 'onerror' not in rendered
    assert 'javascript:' not in rendered and 'https://evil.test' not in rendered and '<iframe' not in rendered
    assert 'position' not in rendered and 'color: red' in rendered
    assert submit(c,'/write',{'title':'安全','category':'测试','content':html,'content_format':'html','published':'on'}).status_code == 302
    assert 'onclick' not in c.get('/posts/1').get_data(as_text=True)

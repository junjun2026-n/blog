import io
from PIL import Image
from test_blog import site, login, register, submit


def test_branding_permissions_and_persistence(site, tmp_path):
    site.config['UPLOAD_FOLDER']=str(tmp_path/'images')
    c=site.test_client()
    register(c); login(c)
    assert c.get('/admin/settings').status_code==403
    assert submit(c,'/admin/settings',{'platform_name':'非法修改'}).status_code==403
    login(c,'admin','TestAdmin123!')
    assert c.get('/admin/settings').status_code==200
    image=io.BytesIO(); Image.new('RGBA',(30,30),(100,20,100,200)).save(image,'PNG')
    logo=submit(c,'/api/images',{'file':(io.BytesIO(image.getvalue()),'logo.png')}).get_json()['url']
    assert submit(c,'/admin/settings',{'platform_name':'分享空间','platform_logo':logo}).status_code==302
    html=c.get('/').get_data(as_text=True)
    assert '<title>分享空间' in html and html.count('class="platform-logo"')==2
    assert logo in html
    assert submit(c,'/admin/settings',{'platform_name':'','platform_logo':logo}).status_code==400
    assert submit(c,'/admin/settings',{'platform_name':'test','platform_logo':'https://evil.test/logo'}).status_code==400
    assert submit(c,'/admin/settings',{'platform_name':'新名称','remove_logo':'on','platform_logo':logo}).status_code==302
    html=c.get('/').get_data(as_text=True)
    assert '<title>新名称' in html and 'class="platform-logo"' not in html

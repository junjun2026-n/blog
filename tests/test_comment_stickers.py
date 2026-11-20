# ============================================================
# 文件名称：test_comment_stickers.py
# 生成日期：2026-11-11
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：验证 comment_stickers 相关功能。
#           文件用途：用于开发验证及功能回归。
#           注意事项：使用隔离测试环境，避免操作正式业务数据。
# ============================================================
import io
from PIL import Image
from test_blog import site, login, submit, write


def test_sticker_comment(site, tmp_path):
    site.config['UPLOAD_FOLDER'] = str(tmp_path / 'images')
    c=site.test_client()
    login(c,'admin','TestAdmin123!')
    write(c)
    image=io.BytesIO()
    Image.new('RGB',(10,10),'blue').save(image,'PNG')
    url=submit(c,'/api/images',{'file':(io.BytesIO(image.getvalue()),'sticker.png')}).get_json()['url']
    assert submit(c,'/posts/1/comment',{'content':'','images':url}).status_code==302
    assert 'comment-stickers' in c.get('/posts/1').get_data(as_text=True)
    assert f'src="{url}"' in c.get('/posts/1').get_data(as_text=True)
    assert submit(c,'/posts/1/comment',{'content':'👍😊'}).status_code==302
    assert '👍😊' in c.get('/posts/1').get_data(as_text=True)
    assert submit(c,'/posts/1/comment',{'images':'https://evil.test/image'}).status_code==400
    assert submit(c,'/posts/1/comment',{'images':[url]*4}).status_code==400
    submit(c,'/posts/1/edit',{'title':'closed','content':'test','category':'test','published':'on'})
    assert submit(c,'/posts/1/comment',{'images':url}).status_code==403

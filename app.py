# ============================================================
# 文件名称：app.py
# 生成日期：2026-11-11
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：组织应用界面或应用服务逻辑。
#           文件用途：供博客的 BLOG/app.py 模块使用。
#           注意事项：运行前检查依赖与配置；涉及数据或服务变更时先备份并验证。
# ============================================================
import os
import json
import io
import warnings
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

import bleach
import markdown
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from bleach.css_sanitizer import CSSSanitizer
from PIL import Image, ImageOps, UnidentifiedImageError
from flask_wtf.csrf import CSRFProtect
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash
from document_import import import_document
from database import connect, database_url
from psycopg import IntegrityError as PostgresIntegrityError

ROOT = Path(__file__).resolve().parent


def create_app(test_config=None):
    app = Flask(__name__)
    data_dir = ROOT / 'data'
    data_dir.mkdir(exist_ok=True)
    secret_file = data_dir / '.secret'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding='utf-8')
    app.config.update(SECRET_KEY=os.environ.get('BLOG_SECRET_KEY') or secret_file.read_text().strip(),
                      DATABASE=database_url(ROOT), SEED_ADMIN=True, VERSION='v0.261115', MAX_CONTENT_LENGTH=6 * 1024 * 1024,
                      UPLOAD_FOLDER=str(data_dir / 'images'),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    if test_config:
        app.config.update(test_config)
    CSRFProtect(app)

    def db():
        if 'db' not in g:
            g.db = connect(app.config['DATABASE'])
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        conn = g.pop('db', None)
        if conn is not None:
            conn.close()

    with app.app_context():
        db().executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          email TEXT NOT NULL UNIQUE COLLATE NOCASE, password TEXT NOT NULL,
          is_admin INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS posts (
          id INTEGER PRIMARY KEY, author_id INTEGER NOT NULL REFERENCES users(id),
          title TEXT NOT NULL, content TEXT NOT NULL, category TEXT NOT NULL DEFAULT '随笔',
          published INTEGER NOT NULL DEFAULT 1, comments_open INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS comments (
          id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
          author_id INTEGER NOT NULL REFERENCES users(id), content TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
        CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published, id DESC);
        CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, id);
        ''')
        if 'content_format' not in {row['name'] for row in db().execute('PRAGMA table_info(posts)')}:
            db().execute("ALTER TABLE posts ADD COLUMN content_format TEXT NOT NULL DEFAULT 'markdown'")
            db().commit()
        if 'images' not in {row['name'] for row in db().execute('PRAGMA table_info(comments)')}:
            db().execute("ALTER TABLE comments ADD COLUMN images TEXT NOT NULL DEFAULT '[]'")
            db().commit()
        if app.config['SEED_ADMIN'] and not db().execute('SELECT 1 FROM users WHERE is_admin=1').fetchone():
            password = os.environ.get('BLOG_ADMIN_PASSWORD') or secrets.token_urlsafe(14)
            db().execute('INSERT INTO users(username,email,password,is_admin) VALUES(?,?,?,1)',
                         ('admin', 'admin@blog.local', generate_password_hash(password)))
            db().commit()
            if not app.testing:
                (data_dir / 'initial-admin.txt').write_text(f'用户名：admin (admin)\n初始密码：{password}\n登录后请在账户设置修改密码。\n', encoding='utf-8')

    @app.before_request
    def load_user():
        g.user = db().execute('SELECT * FROM users WHERE id=? AND active=1', (session.get('uid'),)).fetchone()
        if session.get('uid') and not g.user:
            session.clear()

    def login_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash('请先登录后继续。', 'info')
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapped

    def admin_required(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if not g.user['is_admin']:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped

    @app.context_processor
    def platform_branding():
        settings = {row['key']: row['value'] for row in db().execute('SELECT key,value FROM settings')}
        return {'platform_name': settings.get('platform_name', 'BLOG'),
                'platform_logo': settings.get('platform_logo', '')}

    @app.route('/admin/settings', methods=['GET', 'POST'])
    @admin_required
    def platform_settings():
        if request.method == 'POST':
            import re
            name = request.form.get('platform_name', '').strip()
            logo = request.form.get('platform_logo', '').strip()
            if 'remove_logo' in request.form:
                logo = ''
            if not 1 <= len(name) <= 40:
                flash('平台名称需为 1～40 字。', 'error')
                return render_template('settings.html'), 400
            if logo and (not re.fullmatch(r'/media/[a-f0-9]{32}\.webp', logo) or not (Path(app.config['UPLOAD_FOLDER']) / logo.rsplit('/', 1)[-1]).is_file()):
                flash('LOGO 无效，请重新上传。', 'error')
                return render_template('settings.html'), 400
            db().executemany('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                             [('platform_name', name), ('platform_logo', logo)])
            db().commit()
            flash('平台名称和 LOGO 已保存。', 'success')
            return redirect(url_for('platform_settings'))
        return render_template('settings.html')

    @app.route('/admin/database', methods=['GET', 'POST'])
    @admin_required
    def database_settings():
        from urllib.parse import urlsplit, unquote
        active=app.config['DATABASE']
        configured=database_url(ROOT)
        parts=urlsplit(configured) if str(configured).startswith(('postgresql://','postgres://')) else None
        values=dict(host=parts.hostname or '' if parts else '',port=parts.port or 5432 if parts else 5432,
                    database=unquote(parts.path.lstrip('/')) if parts else '',user=unquote(parts.username or '') if parts else '',
                    sslmode=dict(__import__('urllib.parse',fromlist=['parse_qsl']).parse_qsl(parts.query)).get('sslmode','prefer') if parts else 'prefer')
        if request.method=='POST':
            values={key:request.form.get(key,'').strip() for key in values}
            target=None
            try:
                from urllib.parse import quote, urlencode
                port=int(values['port'])
                if not all(values[key] for key in ('host','database','user')) or not 1<=port<=65535 or values['sslmode'] not in ('disable','prefer','require','verify-ca','verify-full'):
                    raise ValueError()
                password=request.form.get('password','')
                if not password and parts and (values['host'],port,values['database'],values['user'])==(parts.hostname,parts.port or 5432,unquote(parts.path.lstrip('/')),unquote(parts.username or '')):
                    password=unquote(parts.password or '')
                if not password:raise ValueError()
                from urllib.parse import urlunsplit
                host='['+values['host']+']' if ':' in values['host'] else values['host']
                url=urlunsplit(('postgresql',quote(values['user'],safe='')+':'+quote(password,safe='')+'@'+host+':'+str(port),'/'+quote(values['database'],safe=''),urlencode({'sslmode':values['sslmode']}),''))
                action=request.form.get('action')
                if action=='initialize':
                    create_app({'DATABASE':url,'SEED_ADMIN':False})
                    target=connect(url)
                    target.execute('SELECT pg_advisory_xact_lock(870003)')
                    if not target.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                        target.execute('INSERT INTO users(username,email,password,is_admin) VALUES(?,?,?,1)',(g.user['username'],g.user['email'],g.user['password']))
                    target.commit()
                    flash('初始化完成，已有数据及密码保留；空库已创建当前用户的管理员账号。未切换连接，未迁移文章和评论。','success')
                elif action in ('test','save'):
                    target=connect(url)
                    target.execute('SELECT 1')
                    if action=='save':
                        for table in ('users','posts','comments','settings'):
                            target.execute(f'SELECT 1 FROM {table} LIMIT 1')
                        config_file=ROOT/'data/database.json'
                        temporary=config_file.with_suffix('.tmp')
                        temporary.write_text(json.dumps({'url':url},indent=2)+'\n',encoding='utf-8')
                        temporary.replace(config_file)
                    flash('配置已保存，重启后生效；不会迁移历史数据，环境变量 BLOG_DATABASE_URL 优先。' if action=='save' else '数据库连接成功。','success')
                else:raise ValueError()
            except Exception:
                flash('操作失败，请检查连接参数、密码、数据库是否存在及建表权限。保存前需先初始化目标库。','error')
            finally:
                if target is not None:target.close()
        return render_template('database.html',values=values,postgresql=str(active).startswith(('postgresql://','postgres://')))

    def get_post(post_id, edit=False):
        post = db().execute('SELECT p.*,u.username FROM posts p JOIN users u ON u.id=p.author_id WHERE p.id=?', (post_id,)).fetchone()
        if not post:
            abort(404)
        owner = g.user and (g.user['id'] == post['author_id'] or g.user['is_admin'])
        if (edit or not post['published']) and not owner:
            abort(403 if edit else 404)
        return post

    @app.template_filter('markdown')
    def render_markdown(value):
        html = markdown.markdown(value, extensions=['fenced_code', 'tables', 'nl2br'])
        return clean_html(html)

    def clean_html(html):
        def attribute(tag, name, value):
            if tag == 'img' and name == 'src':
                import re
                return bool(re.fullmatch(r'/media/[a-f0-9]{32}\.(?:jpg|png|webp)', value))
            return name in {'title','style'} or (tag == 'a' and name == 'href') or (tag == 'img' and name in {'alt','width','height'}) or (tag in {'td','th'} and name in {'colspan','rowspan'})
        return Markup(bleach.clean(html, tags={'p','div','span','br','h1','h2','h3','h4','h5','h6','strong','b','em','i','u','s','ul','ol','li','blockquote','pre','code','a','hr','table','thead','tbody','tr','th','td','del','img','sub','sup'},
            attributes=attribute, protocols={'http','https','mailto'}, strip=True,
            css_sanitizer=CSSSanitizer(allowed_css_properties=['color','background-color','text-align','font-size','font-weight','font-style','text-decoration','width','height','max-width','padding','border','border-collapse'])))

    @app.template_filter('article_content')
    def article_content(post):
        if post['content_format'] in ('text', 'json'):
            from markupsafe import escape
            return Markup('<pre class="plain-content">') + escape(post['content']) + Markup('</pre>')
        if post['content_format'] == 'html':
            return clean_html(post['content'])
        return render_markdown(post['content'])

    @app.template_filter('comment_images')
    def comment_images(value):
        import re
        try:
            items = json.loads(value)
            return [item for item in items if isinstance(item, str) and re.fullmatch(r'/media/[a-f0-9]{32}\.webp', item)][:3] if isinstance(items, list) else []
        except (ValueError, TypeError):
            return []

    @app.post('/api/images')
    @login_required
    def upload_image():
        uploaded = request.files.get('file')
        if not uploaded:
            return jsonify(error='请选择图片。'), 400
        raw = uploaded.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            return jsonify(error='单张图片不能超过 5MB。'), 400
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if source.format not in ('JPEG','PNG','WEBP','GIF') or source.width * source.height > 20_000_000:
                        raise ValueError()
                    source.load()
                    image = ImageOps.exif_transpose(source).convert('RGBA' if 'A' in source.getbands() else 'RGB')
                    image.thumbnail((2560,2560))
                    target = Path(app.config['UPLOAD_FOLDER'])
                    target.mkdir(parents=True, exist_ok=True)
                    filename = secrets.token_hex(16) + '.webp'
                    image.save(target / filename, 'WEBP', quality=88)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            return jsonify(error='请上传有效的 JPG、PNG、WebP 或 GIF 图片（最多 2000 万像素）。'), 400
        return jsonify(url=url_for('media', filename=filename))

    @app.get('/media/<filename>')
    def media(filename):
        import re
        if not re.fullmatch(r'[a-f0-9]{32}\.webp', filename):
            abort(404)
        response = send_from_directory(app.config['UPLOAD_FOLDER'], filename, max_age=86400, mimetype='image/webp')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.post('/api/import')
    @login_required
    def upload_document():
        uploaded = request.files.get('file')
        if not uploaded or not uploaded.filename:
            return jsonify(error='请选择要导入的文件。'), 400
        try:
            return jsonify(import_document(uploaded.filename, uploaded.read()))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post('/api/preview')
    @login_required
    def preview_document():
        content = request.form.get('content', '')
        fmt = request.form.get('content_format', 'markdown')
        if len(content) > 100000 or fmt not in ('markdown','text','json','html'):
            return jsonify(error='内容过长或格式无效。'), 400
        return jsonify(html=str(article_content({'content': content, 'content_format': fmt})))

    @app.route('/')
    def index():
        q = request.args.get('q', '').strip()[:100]
        category = request.args.get('category', '').strip()[:30]
        page = max(1, request.args.get('page', 1, type=int))
        where, args = ['p.published=1'], []
        if q:
            where.append('(p.title LIKE ? OR p.content LIKE ?)')
            args += [f'%{q}%', f'%{q}%']
        if category:
            where.append('p.category=?')
            args.append(category)
        clause = ' AND '.join(where)
        total = db().execute('SELECT COUNT(*) FROM posts p WHERE ' + clause, args).fetchone()[0]
        pages = max(1, (total + 8) // 9)
        page = min(page, pages)
        posts = db().execute('SELECT p.*,u.username,(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) comment_count FROM posts p JOIN users u ON u.id=p.author_id WHERE ' + clause + ' ORDER BY p.id DESC LIMIT 9 OFFSET ?', args + [(page-1)*9]).fetchall()
        categories = db().execute('SELECT category,COUNT(*) n FROM posts WHERE published=1 GROUP BY category ORDER BY n DESC').fetchall()
        stats = dict(posts=db().execute('SELECT COUNT(*) FROM posts WHERE published=1').fetchone()[0], users=db().execute('SELECT COUNT(*) FROM users WHERE active=1').fetchone()[0], comments=db().execute('SELECT COUNT(*) FROM comments c JOIN posts p ON p.id=c.post_id WHERE p.published=1').fetchone()[0])
        return render_template('index.html', posts=posts, categories=categories, stats=stats, q=q, category=category, page=page, pages=pages)

    @app.route('/register', methods=['GET','POST'])
    def register():
        if request.method == 'POST':
            username, email, password = (request.form.get(k, '').strip() if k != 'password' else request.form.get(k, '') for k in ('username','email','password'))
            if not (2 <= len(username) <= 30 and all(c.isalnum() or c in '_-' for c in username)):
                flash('用户名需为 2～30 位文字、数字、下划线或短横线。', 'error')
            elif '@' not in email or len(email) > 200:
                flash('请输入有效邮箱地址。', 'error')
            elif not 8 <= len(password) <= 128:
                flash('密码长度需为 8～128 位。', 'error')
            elif password != request.form.get('confirm'):
                flash('两次输入的密码不一致。', 'error')
            else:
                try:
                    db().execute('INSERT INTO users(username,email,password) VALUES(?,?,?)', (username,email,generate_password_hash(password)))
                    db().commit()
                    flash('注册成功，请登录。', 'success')
                    return redirect(url_for('login'))
                except (sqlite3.IntegrityError, PostgresIntegrityError):
                    db().rollback()
                    flash('用户名或邮箱已被使用。', 'error')
        return render_template('auth.html', mode='register')

    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method == 'POST':
            user = db().execute('SELECT * FROM users WHERE lower(username)=lower(?)', (request.form.get('username',''),)).fetchone()
            if user and user['active'] and check_password_hash(user['password'], request.form.get('password','')):
                session.clear()
                session['uid'] = user['id']
                return redirect(url_for('index'))
            flash('用户名、密码错误或账户已停用。', 'error')
        return render_template('auth.html', mode='login')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('index'))

    @app.route('/account', methods=['GET','POST'])
    @login_required
    def account():
        if request.method == 'POST':
            password = request.form.get('password','')
            if not check_password_hash(g.user['password'], request.form.get('old_password','')):
                flash('当前密码错误。', 'error')
            elif not 8 <= len(password) <= 128:
                flash('新密码需为 8～128 位。', 'error')
            elif password != request.form.get('confirm'):
                flash('两次新密码不一致。', 'error')
            else:
                db().execute('UPDATE users SET password=? WHERE id=?', (generate_password_hash(password),g.user['id']))
                db().commit()
                flash('密码已更新。', 'success')
        return render_template('account.html')

    @app.get('/mine')
    @login_required
    def mine():
        posts = db().execute('SELECT * FROM posts WHERE author_id=? ORDER BY id DESC', (g.user['id'],)).fetchall()
        return render_template('mine.html', posts=posts)

    @app.route('/write', methods=['GET','POST'])
    @app.route('/posts/<int:post_id>/edit', methods=['GET','POST'])
    @login_required
    def edit(post_id=None):
        post = get_post(post_id, edit=True) if post_id else None
        if request.method == 'POST':
            title, content, category = (request.form.get(k,'').strip() for k in ('title','content','category'))
            content_format = request.form.get('content_format', 'markdown')
            if content_format not in ('markdown','text','json','html'):
                abort(400)
            if content_format == 'html':
                content = str(clean_html(content))
            if content_format == 'json':
                try:
                    content = json.dumps(json.loads(content), ensure_ascii=False, indent=2, allow_nan=False)
                except (ValueError, RecursionError):
                    flash('JSON 格式无效，请检查后保存。', 'error')
                    return render_template('editor.html', post=post), 400
            if not 1 <= len(title) <= 160 or not 1 <= len(content) <= 100000 or not 1 <= len(category) <= 30:
                flash('请填写标题、分类与正文；标题最多 160 字，分类最多 30 字，正文最多 10 万字。', 'error')
            else:
                values = (title, content, category, int('published' in request.form), int('comments_open' in request.form), content_format)
                if post:
                    db().execute("UPDATE posts SET title=?,content=?,category=?,published=?,comments_open=?,content_format=?,updated_at=datetime('now','localtime') WHERE id=?", values + (post_id,))
                else:
                    cur = db().execute('INSERT INTO posts(title,content,category,published,comments_open,content_format,author_id) VALUES(?,?,?,?,?,?,?)', values + (g.user['id'],))
                    post_id = cur.lastrowid
                db().commit()
                flash('文章已保存。', 'success')
                return redirect(url_for('detail', post_id=post_id))
        return render_template('editor.html', post=post)

    @app.get('/posts/<int:post_id>')
    def detail(post_id):
        post = get_post(post_id)
        comments = db().execute('SELECT c.*,u.username FROM comments c JOIN users u ON u.id=c.author_id WHERE post_id=? ORDER BY c.id', (post_id,)).fetchall()
        return render_template('detail.html', post=post, comments=comments)

    @app.post('/posts/<int:post_id>/comment')
    @login_required
    def comment(post_id):
        post = get_post(post_id)
        if not post['comments_open'] or not post['published']:
            abort(403, description='作者已关闭评论或文章尚未发布。')
        content = request.form.get('content','').strip()
        images = request.form.getlist('images')
        import re
        if len(images) > 3 or any(not re.fullmatch(r'/media/[a-f0-9]{32}\.webp', item) or not (Path(app.config['UPLOAD_FOLDER']) / item.rsplit('/', 1)[-1]).is_file() for item in images):
            abort(400)
        if (not content and not images) or len(content) > 3000:
            flash('请输入评论或添加表情包，文字最多 3000 字。', 'error')
        else:
            db().execute('INSERT INTO comments(post_id,author_id,content,images) VALUES(?,?,?,?)', (post_id,g.user['id'],content,json.dumps(images)))
            db().commit()
            flash('评论已发表。', 'success')
        return redirect(url_for('detail', post_id=post_id) + '#comments')

    @app.post('/posts/<int:post_id>/delete')
    @login_required
    def delete_post(post_id):
        get_post(post_id, edit=True)
        db().execute('DELETE FROM posts WHERE id=?', (post_id,))
        db().commit()
        flash('文章已删除。', 'success')
        return redirect(url_for('mine'))

    @app.post('/comments/<int:comment_id>/delete')
    @login_required
    def delete_comment(comment_id):
        item = db().execute('SELECT c.*,p.author_id post_author FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=?', (comment_id,)).fetchone()
        if not item:
            abort(404)
        if not g.user['is_admin'] and g.user['id'] not in (item['author_id'],item['post_author']):
            abort(403)
        db().execute('DELETE FROM comments WHERE id=?', (comment_id,))
        db().commit()
        return redirect(url_for('detail', post_id=item['post_id']))

    @app.get('/admin')
    @admin_required
    def admin():
        tab = request.args.get('tab','posts')
        if tab not in ('posts','users','comments'):
            tab = 'posts'
        page = max(1, request.args.get('page',1,type=int))
        queries = {'posts':'SELECT p.*,u.username FROM posts p JOIN users u ON u.id=p.author_id ORDER BY p.id DESC', 'users':'SELECT id,username,email,is_admin,active,created_at FROM users ORDER BY id DESC', 'comments':'SELECT c.*,u.username,p.title FROM comments c JOIN users u ON u.id=c.author_id JOIN posts p ON p.id=c.post_id ORDER BY c.id DESC'}
        total = db().execute('SELECT COUNT(*) FROM ' + tab).fetchone()[0]
        pages = max(1,(total+19)//20)
        page = min(page,pages)
        rows = db().execute(queries[tab] + ' LIMIT 20 OFFSET ?', ((page-1)*20,)).fetchall()
        counts = {name: db().execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in queries}
        return render_template('admin.html', tab=tab, rows=rows, counts=counts, page=page, pages=pages)

    @app.post('/admin/users/<int:user_id>')
    @admin_required
    def manage_user(user_id):
        target = db().execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not target:
            abort(404)
        action = request.form.get('action')
        if user_id == g.user['id']:
            flash('请通过账户设置修改自己的密码；不能停用或撤销自己的管理员权限。', 'error')
        elif action in ('toggle_active','toggle_admin'):
            # Keep at least one enabled administrator, including during concurrent requests.
            db().execute('BEGIN IMMEDIATE')
            target = db().execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            field = 'active' if action == 'toggle_active' else 'is_admin'
            if target['is_admin'] and target['active'] and db().execute('SELECT COUNT(*) FROM users WHERE is_admin=1 AND active=1').fetchone()[0] <= 1:
                flash('至少需要保留一个启用的管理员。', 'error')
            else:
                db().execute(f'UPDATE users SET {field}=1-{field} WHERE id=?', (user_id,))
                flash('用户状态已更新。', 'success')
            db().commit()
        elif action == 'password':
            password = request.form.get('password','')
            if not 8 <= len(password) <= 128:
                flash('密码需为 8～128 位。', 'error')
            else:
                db().execute('UPDATE users SET password=? WHERE id=?', (generate_password_hash(password),user_id))
                db().commit()
                flash('用户密码已重置。', 'success')
        else:
            abort(400)
        return redirect(url_for('admin',tab='users'))

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error(exc):
        return render_template('error.html', code=exc.code, message={400:'请求无效，请刷新页面后重试。',403:'你没有此操作权限，或文章已关闭评论。',404:'页面或文章不存在。',413:'提交内容过大。'}.get(exc.code)), exc.code

    return app


if __name__ == '__main__':
    from waitress import serve
    serve(create_app(), host=os.environ.get('BLOG_HOST','0.0.0.0'), port=int(os.environ.get('BLOG_PORT','8700')), threads=8)

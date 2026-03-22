import os
import sqlite3
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.utils import get_column_letter
from collections import defaultdict
import random
import string
from datetime import datetime, timedelta, timezone
from functools import wraps
from collections import defaultdict
import io
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_mail import Mail, Message
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
import calendar
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo('Asia/Jerusalem')


def now_israel():
    return datetime.now(ISRAEL_TZ).replace(tzinfo=None)


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.permanent_session_lifetime = timedelta(days=30)
DATABASE = os.environ.get('DATABASE_PATH', 'finance_tracker.db')


def is_admin():
    return bool(session.get('is_admin'))


csrf = CSRFProtect(app)
# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = ('OurHome IL', os.environ.get('MAIL_USERNAME', ''))
mail = Mail(app)


# Exempt JSON API endpoints — protected by session auth
@app.after_request
def inject_csrf_token(response):
    response.set_cookie('csrf_token', generate_csrf())
    return response


@app.after_request
def add_no_cache(response):
    if request.endpoint in ('login', 'register'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    return response


@app.before_request
def make_session_permanent():
    session.permanent = True


def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def generate_invite_code():
    """Generate unique 6-char invite code"""
    with get_db() as conn:
        for _ in range(10):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            exists = conn.execute('SELECT id FROM families WHERE invite_code=?', (code,)).fetchone()
            if not exists:
                return code
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))  # fallback longer code


def get_family_id():
    return session.get('family_id')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if user:
                token = secrets.token_urlsafe(32)
                exp = (now_israel() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('UPDATE users SET reset_token=?, reset_token_exp=? WHERE id=?',
                             (token, exp, user['id']))
                reset_url = url_for('reset_password', token=token, _external=True)
                try:
                    msg = Message(
                        subject='איפוס סיסמה — OurHome IL',
                        recipients=[email],
                        html=f'''
                        <div dir="rtl" style="font-family:Arial;max-width:500px;margin:0 auto;">
                            <h2>איפוס סיסמה</h2>
                            <p>קיבלנו בקשה לאיפוס הסיסמה שלך.</p>
                            <p>לחץ על הכפתור כדי לאפס:</p>
                            <a href="{reset_url}"
                               style="display:inline-block;padding:12px 24px;
                                      background:#2563eb;color:white;
                                      border-radius:8px;text-decoration:none;
                                      font-weight:bold;">
                                אפס סיסמה
                            </a>
                            <p style="color:#888;font-size:0.85rem;margin-top:20px;">
                                הקישור תקף לשעה אחת.<br>
                                אם לא ביקשת איפוס — התעלם מהודעה זו.
                            </p>
                        </div>
                        '''
                    )
                    mail.send(msg)
                except Exception as e:
                    print(f'Mail error: {e}')
        # תמיד מראה הודעה זהה — לא חושף אם המייל קיים
        flash('אם האימייל קיים במערכת — נשלחה הודעה עם קישור לאיפוס', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    with get_db() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE reset_token=? AND reset_token_exp > ?',
            (token, now_israel().strftime('%Y-%m-%d %H:%M:%S'))
        ).fetchone()
    if not user:
        flash('הקישור לא תקין או פג תוקף', 'error')
        return redirect(url_for('login'))
    if request.method == 'POST':
        pw = request.form.get('password', '')
        pw2 = request.form.get('password2', '')
        if len(pw) < 6:
            flash('סיסמה חייבת להיות לפחות 6 תווים', 'error')
            return render_template('reset_password.html', token=token)
        if pw != pw2:
            flash('הסיסמאות לא תואמות', 'error')
            return render_template('reset_password.html', token=token)
        with get_db() as conn:
            conn.execute(
                'UPDATE users SET password_hash=?, reset_token="", reset_token_exp=NULL WHERE id=?',
                (generate_password_hash(pw), user['id'])
            )
        flash('סיסמה שונתה בהצלחה!', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            invite_code TEXT UNIQUE NOT NULL, created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            email TEXT DEFAULT '', display_name TEXT DEFAULT '',
            password_hash TEXT NOT NULL, family_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (family_id) REFERENCES families(id));
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER,
            description TEXT NOT NULL, amount REAL NOT NULL,
            category TEXT DEFAULT 'כללי', date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            month TEXT NOT NULL, year INTEGER NOT NULL, archived BOOLEAN DEFAULT FALSE);
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#007bff');
        CREATE TABLE IF NOT EXISTS archived_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER,
            label TEXT NOT NULL, total REAL NOT NULL, count INTEGER NOT NULL,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER NOT NULL,
            name TEXT NOT NULL, quantity INTEGER DEFAULT 1,
            checked BOOLEAN DEFAULT FALSE, image TEXT DEFAULT '',
            category TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS shopping_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER NOT NULL,
            name TEXT NOT NULL, quantity INTEGER DEFAULT 1,
            category TEXT DEFAULT '',
            UNIQUE(family_id, name));
        CREATE TABLE IF NOT EXISTS feedings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER NOT NULL,
            feeding_type TEXT NOT NULL, amount REAL DEFAULT 0,
            duration INTEGER DEFAULT 0, notes TEXT DEFAULT '',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS recurring_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, family_id INTEGER NOT NULL,
            description TEXT NOT NULL, amount REAL NOT NULL,
            category TEXT DEFAULT 'כללי',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """)
    for t, c, ct in [
        ('users','email','TEXT DEFAULT ""'),
        ('users','display_name','TEXT DEFAULT ""'),
        ('users','family_id','INTEGER'),
        ('users','is_admin','BOOLEAN DEFAULT FALSE'),
        ('users','reset_token','TEXT DEFAULT ""'),
        ('users','reset_token_exp','TIMESTAMP'),
        ('shopping_items','image','TEXT DEFAULT ""'),
        ('shopping_items','family_id','INTEGER'),
        ('shopping_items','favorite','BOOLEAN DEFAULT FALSE'),
        ('shopping_items','category','TEXT DEFAULT ""'),
        ('payments','family_id','INTEGER'),
        ('feedings','family_id','INTEGER'),
        ('recurring_payments','family_id','INTEGER'),
        ('archived_cycles','family_id','INTEGER'),
    ]:
        try: conn.execute(f'ALTER TABLE {t} ADD COLUMN {c} {ct}')
        except sqlite3.OperationalError: pass
    for cat, color in [
        ('קבועים','#6f42c1'),('משק בית','#28a745'),('קניות - סופר','#ffc107'),
        ('קניות - אופנה','#17a2b8'),('רכב','#dc3545'),('תינוק','#e83e8c'),
        ('בילויים / פנאי','#20c997'),('טיפוח','#fd7e14'),('כללי','#6c757d'),
    ]:
        conn.execute('INSERT OR IGNORE INTO categories (name, color) VALUES (?, ?)', (cat, color))
    conn.commit()
    conn.close()

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if not session.get('family_id') and request.endpoint not in (
                'family_setup', 'create_family', 'join_family', 'logout', 'service_worker'):
            return redirect(url_for('family_setup'))
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin():
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    return decorated


@app.route('/admin')
@require_admin
def admin_dashboard():
    with get_db() as conn:
        # ── KPIs ──
        total_users = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
        total_families = conn.execute('SELECT COUNT(*) as c FROM families').fetchone()['c']
        # משפחות עם 2+ חברים = פעילות אמיתית
        active_families = conn.execute('''
            SELECT COUNT(*) as c FROM (
                SELECT family_id FROM users WHERE family_id IS NOT NULL
                GROUP BY family_id HAVING COUNT(*) >= 2
            )''').fetchone()['c']

        week_ago = (now_israel() - timedelta(days=7)).strftime('%Y-%m-%d')
        month_ago = (now_israel() - timedelta(days=30)).strftime('%Y-%m-%d')

        new_week = conn.execute('SELECT COUNT(*) as c FROM users WHERE created_at >= ?', (week_ago,)).fetchone()['c']
        new_month = conn.execute('SELECT COUNT(*) as c FROM users WHERE created_at >= ?', (month_ago,)).fetchone()['c']

        # ── גרף הרשמות יומי — 30 ימים אחרונים ──
        reg_daily = conn.execute('''
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM users
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY day
        ''', (month_ago,)).fetchall()

        # ── גרף הרשמות חודשי — 12 חודשים אחרונים ──
        reg_monthly = conn.execute('''
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
            FROM users
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month DESC
            LIMIT 12
        ''').fetchall()
        reg_monthly = list(reversed(reg_monthly))

        # ── פעילות תשלומים — ללא פרטים ──
        payments_month = conn.execute('''
            SELECT COUNT(*) as c FROM payments
            WHERE date >= ?
        ''', (month_ago,)).fetchone()['c']

        payments_by_month = conn.execute('''
            SELECT month, COUNT(*) as cnt, COUNT(DISTINCT family_id) as families
            FROM payments
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        ''').fetchall()
        payments_by_month = list(reversed(payments_by_month))

        # ── משפחות לפי גודל ──
        family_sizes = conn.execute('''
            SELECT COUNT(*) as members, COUNT(*) as families
            FROM users
            WHERE family_id IS NOT NULL
            GROUP BY family_id
        ''').fetchall()
        solo = sum(1 for f in family_sizes if f['members'] == 1)
        pairs = sum(1 for f in family_sizes if f['members'] == 2)
        large = sum(1 for f in family_sizes if f['members'] >= 3)

        # ── משתמשים ללא משפחה ──
        no_family = conn.execute(
            'SELECT COUNT(*) as c FROM users WHERE family_id IS NULL'
        ).fetchone()['c']

    return render_template('admin.html',
                           total_users=total_users,
                           total_families=total_families,
                           active_families=active_families,
                           new_week=new_week,
                           new_month=new_month,
                           no_family=no_family,
                           solo=solo, pairs=pairs, large=large,
                           payments_month=payments_month,
                           reg_daily=[dict(r) for r in reg_daily],
                           reg_monthly=[dict(r) for r in reg_monthly],
                           payments_by_month=[dict(r) for r in payments_by_month],
                           now_israel=now_israel,
                           )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session and session.get('family_id'):
        return redirect(url_for('home'))
    if request.method == 'POST':
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
            if user and check_password_hash(user['password_hash'], request.form['password']):
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['display_name'] = user['display_name'] or user['username']
                session['family_id'] = user['family_id']
                session['is_admin'] = bool(user['is_admin'])
                if not user['family_id']: return redirect(url_for('family_setup'))
                return redirect(url_for('home'))
            flash('שם משתמש או סיסמה שגויים', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session and session.get('family_id'):
        return redirect(url_for('home'))
    if request.method == 'POST':
        dn = request.form['display_name'].strip()
        un = request.form['username'].strip().lower()
        em = request.form.get('email', '').strip()
        pw = request.form['password']
        pw2 = request.form['password2']
        # Validate username - alphanumeric only, 3-20 chars
        import re
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', un):
            flash('שם משתמש חייב להכיל 3-20 תווים באנגלית, מספרים או _', 'error')
            return render_template('register.html')
        # Validate email
        if em and not re.match(r'^[^@]+@[^@]+\.[^@]+$', em):
            flash('כתובת אימייל לא תקינה', 'error')
            return render_template('register.html')
        if len(pw) < 6:
            flash('סיסמה חייבת להיות לפחות 6 תווים', 'error')
            return render_template('register.html')
        if pw != pw2:
            flash('הסיסמאות לא תואמות', 'error')
            return render_template('register.html')
        with get_db() as conn:
            if conn.execute('SELECT id FROM users WHERE username=?', (un,)).fetchone():
                flash('שם משתמש כבר תפוס', 'error')
                return render_template('register.html')
            conn.execute('INSERT INTO users (username,email,display_name,password_hash) VALUES (?,?,?,?)',
                         (un, em, dn, generate_password_hash(pw)))
            user = conn.execute('SELECT * FROM users WHERE username=?', (un,)).fetchone()
            session.clear()
            session['user_id'] = user['id']
            session['username'] = un
            session['display_name'] = dn
            flash('נרשמת בהצלחה!', 'success')
            return redirect(url_for('family_setup'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    response = redirect(url_for('login'))
    response.delete_cookie('csrf_token')
    return response


@app.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    if len(new_pw) < 6:
        flash('סיסמה חדשה חייבת להיות לפחות 6 תווים', 'error')
        return redirect(url_for('settings'))

    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if user and check_password_hash(user['password_hash'], current_pw):
            conn.execute('UPDATE users SET password_hash=? WHERE id=?',
                         (generate_password_hash(new_pw), session['user_id']))
            # שליחת מייל בתוך ה-with כשה-conn עדיין פתוח
            try:
                if user['email']:
                    msg = Message(
                        subject='סיסמתך שונתה — OurHome IL',
                        recipients=[user['email']],
                        html=f'''
                        <div dir="rtl" style="font-family:Arial;max-width:500px;margin:0 auto;">
                            <h2>סיסמה שונתה</h2>
                            <p>הסיסמה לחשבון שלך באפליקציית OurHome IL שונתה זה עתה.</p>
                            <p style="color:#888;font-size:0.85rem;">
                                אם לא ביקשת שינוי זה — פנה אלינו מיד.
                            </p>
                        </div>
                        '''
                    )
                    mail.send(msg)
            except Exception as e:
                print(f'Mail error: {e}')
            flash('סיסמה שונתה בהצלחה!', 'success')
            return redirect(url_for('home'))

    flash('סיסמה נוכחית שגויה', 'error')
    return redirect(url_for('settings'))


@app.route('/family')
@require_auth
def family_setup():
    family = None
    members = []
    if session.get('family_id'):
        with get_db() as conn:
            family = conn.execute('SELECT * FROM families WHERE id=?', (session['family_id'],)).fetchone()
            members = conn.execute('SELECT id,display_name,username FROM users WHERE family_id=?',
                                   (session['family_id'],)).fetchall()
    return render_template('family_setup.html', family=family, members=members)


@app.route('/family/create', methods=['POST'])
def create_family():
    if 'user_id' not in session: return redirect(url_for('login'))
    name = request.form['family_name'].strip()
    code = generate_invite_code()
    with get_db() as conn:
        conn.execute('INSERT INTO families (name,invite_code,created_by) VALUES (?,?,?)',
                     (name, code, session['user_id']))
        fam = conn.execute('SELECT * FROM families WHERE invite_code=?', (code,)).fetchone()
        conn.execute('UPDATE users SET family_id=? WHERE id=?', (fam['id'], session['user_id']))
        session['family_id'] = fam['id']
    flash(f'משפחה "{name}" נוצרה! קוד: {code}', 'success')
    return redirect(url_for('family_setup'))


@app.route('/family/join', methods=['POST'])
def join_family():
    if 'user_id' not in session: return redirect(url_for('login'))
    code = request.form['invite_code'].strip().upper()
    with get_db() as conn:
        fam = conn.execute('SELECT * FROM families WHERE invite_code=?', (code,)).fetchone()
        if not fam:
            flash('קוד הזמנה לא נמצא', 'error')
            return redirect(url_for('family_setup'))
        conn.execute('UPDATE users SET family_id=? WHERE id=?', (fam['id'], session['user_id']))
        session['family_id'] = fam['id']
    flash(f'הצטרפת למשפחת {fam["name"]}!', 'success')
    return redirect(url_for('family_setup'))


@app.route('/sw.js')
def service_worker():
    return send_file('static/sw.js', mimetype='application/javascript')


@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/home')
@require_auth
def home():
    return render_template('home.html')


@app.route('/api/home-summary')
@require_auth
def home_summary():
    fid = get_family_id()
    now = now_israel()
    cm = now.strftime('%Y-%m')
    today = now.strftime('%Y-%m-%d')
    with get_db() as conn:
        # Finance
        fin = conn.execute(
            'SELECT COALESCE(SUM(amount),0) as total, COUNT(*) as count FROM payments WHERE month=? AND archived=FALSE AND family_id=?',
            (cm, fid)).fetchone()
        last_payment = conn.execute(
            'SELECT description, amount FROM payments WHERE month=? AND archived=FALSE AND family_id=? ORDER BY date DESC LIMIT 1',
            (cm, fid)).fetchone()
        # Shopping
        shop_total = conn.execute('SELECT COUNT(*) as total FROM shopping_items WHERE family_id=?', (fid,)).fetchone()[
            'total']
        shop_done = conn.execute('SELECT COUNT(*) as done FROM shopping_items WHERE family_id=? AND checked=TRUE',
                                 (fid,)).fetchone()['done']
        shop_left = shop_total - shop_done
        # Baby
        baby_bottles = conn.execute(
            'SELECT COUNT(*) as c, COALESCE(SUM(amount),0) as ml FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, today, 'bottle')).fetchone()
        baby_bf = conn.execute(
            'SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, today, 'breastfeeding')).fetchone()
        baby_diapers = conn.execute(
            'SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, today, 'diaper')).fetchone()
        baby_sleep = conn.execute(
            'SELECT COUNT(*) as c, COALESCE(SUM(amount),0) as mins FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, today, 'sleep')).fetchone()
        baby_all = conn.execute('SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=?',
                                (fid, today)).fetchone()
        last_feed = conn.execute(
            'SELECT date FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type IN (?,?,?) ORDER BY time(date) DESC LIMIT 1',
            (fid, today, 'bottle', 'breastfeeding', 'solid')).fetchone()
        last_feed_ago = '--'
        if last_feed:
            try:
                ldt = datetime.strptime(last_feed['date'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                mins = int((now - ldt).total_seconds() // 60)
                if mins < 0:
                    last_feed_ago = 'עוד מעט'
                elif mins < 60:
                    last_feed_ago = f'{mins} דק\''
                else:
                    last_feed_ago = f'{mins // 60}:{mins % 60:02d}h'
            except:
                pass
        sleep_mins = int(baby_sleep['mins']) if baby_sleep['mins'] else 0
        sleep_str = f'{sleep_mins // 60}:{sleep_mins % 60:02d}h' if sleep_mins >= 60 else (
            f'{sleep_mins} דק\'' if sleep_mins > 0 else '--')
    return jsonify({
        'finance': {'total': float(fin['total']), 'count': fin['count'],
                    'last': {'desc': last_payment['description'],
                             'amount': float(last_payment['amount'])} if last_payment else None},
        'shopping': {'total': shop_total, 'done': shop_done, 'left': shop_left},
        'baby': {
            'count': baby_all['c'],
            'total_ml': float(baby_bottles['ml']),
            'bottles': baby_bottles['c'],
            'breastfeedings': baby_bf['c'],
            'diapers': baby_diapers['c'],
            'sleep_str': sleep_str,
            'last_ago': last_feed_ago
        }
    })


@app.route('/settings')
@require_auth
def settings():
    family = None
    members = []
    if session.get('family_id'):
        with get_db() as conn:
            family = conn.execute('SELECT * FROM families WHERE id=?', (session['family_id'],)).fetchone()
            members = conn.execute('SELECT id,display_name,username FROM users WHERE family_id=?',
                                   (session['family_id'],)).fetchall()
    return render_template('settings.html', family=family, members=members)


@app.route('/update-profile', methods=['POST'])
@require_auth
def update_profile():
    dn = request.form.get('display_name', '').strip()
    if dn:
        with get_db() as conn:
            conn.execute('UPDATE users SET display_name=? WHERE id=?', (dn, session['user_id']))
        session['display_name'] = dn
        flash('שם תצוגה עודכן!', 'success')
    return redirect(url_for('settings'))


@app.route('/api/categories', methods=['GET'])
@require_auth
def get_categories():
    with get_db() as conn:
        cats = conn.execute('SELECT name, color FROM categories ORDER BY name').fetchall()
    return jsonify([dict(c) for c in cats])


@app.route('/api/categories', methods=['POST'])
@require_auth
def add_category():
    data = request.get_json()
    name = data.get('name', '').strip()
    color = data.get('color', '#6c757d')
    if not name: return jsonify({'error': 'Missing name'}), 400
    with get_db() as conn:
        conn.execute('INSERT OR IGNORE INTO categories (name, color) VALUES (?,?)', (name, color))
    return jsonify({'success': True}), 201


@app.route('/api/family/remove-member', methods=['POST'])
@require_auth
def remove_family_member():
    fid = get_family_id()
    data = request.get_json()
    target_id = data.get('user_id')
    with get_db() as conn:
        family = conn.execute('SELECT created_by FROM families WHERE id=?', (fid,)).fetchone()
        if not family or family['created_by'] != session['user_id']:
            return jsonify({'error': 'Only admin can remove members'}), 403
        if target_id == session['user_id']:
            return jsonify({'error': 'Cannot remove yourself'}), 400
        conn.execute('UPDATE users SET family_id=NULL WHERE id=? AND family_id=?', (target_id, fid))
    return jsonify({'success': True})


@app.route('/api/family/leave', methods=['POST'])
@require_auth
def leave_family():
    fid = get_family_id()
    with get_db() as conn:
        family = conn.execute('SELECT created_by FROM families WHERE id=?', (fid,)).fetchone()
        if family and family['created_by'] == session['user_id']:
            return jsonify({'error': 'Admin cannot leave. Delete family or transfer ownership first.'}), 400
        conn.execute('UPDATE users SET family_id=NULL WHERE id=?', (session['user_id'],))
    session['family_id'] = None
    return jsonify({'success': True})


@app.route('/dashboard')
@require_auth
def dashboard():
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    cy = now_israel().year
    with get_db() as conn:
        payments = conn.execute(
            'SELECT * FROM payments WHERE month=? AND archived=FALSE AND family_id=? ORDER BY date DESC',
            (cm, fid)).fetchall()
        mt = conn.execute(
            'SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE month=? AND archived=FALSE AND family_id=?',
            (cm, fid)).fetchone()['total']
        cs = conn.execute(
            'SELECT p.category,SUM(p.amount) as total,c.color FROM payments p LEFT JOIN categories c ON p.category=c.name WHERE p.month=? AND p.archived=FALSE AND p.family_id=? GROUP BY p.category ORDER BY total DESC',
            (cm, fid)).fetchall()
        lar = conn.execute("SELECT value FROM app_settings WHERE key=?", (f'last_archived_total_{fid}',)).fetchone()
        pmt = float(lar['value']) if lar else \
            conn.execute('SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE month=? AND family_id=?',
                         ((now_israel().replace(day=1) - timedelta(days=1)).strftime('%Y-%m'), fid)).fetchone()['total']
        cats = conn.execute('SELECT name FROM categories ORDER BY name').fetchall()
    cd = now_israel().day
    da = mt / cd if cd > 0 else 0
    return render_template('dashboard.html', payments=payments, monthly_total=mt, daily_average=da,
                           weekly_average=da * 7,
                           category_stats=cs, prev_month_total=pmt,
                           comparison_pct=((mt - pmt) / pmt * 100) if pmt > 0 else 0,
                           categories=cats, current_month=cm, comparison_label='vs Last Month')


@app.route('/add_payment', methods=['POST'])
@require_auth
def add_payment():
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    cy = now_israel().year
    try:
        amount = float(request.form.get('amount', 0))
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('סכום לא תקין', 'error')
        return redirect(url_for('dashboard'))
    desc = request.form.get('description', '').strip()
    if not desc:
        flash('נא להכניס תיאור', 'error')
        return redirect(url_for('dashboard'))
    with get_db() as conn:
        conn.execute('INSERT INTO payments (family_id,description,amount,category,month,year) VALUES (?,?,?,?,?,?)',
                     (fid, desc, amount, request.form.get('category', 'כללי'), cm, cy))
    return redirect(url_for('dashboard'))


@app.route('/api/payments/add', methods=['POST'])
@require_auth
def add_payment_api():
    fid = get_family_id()
    data = request.get_json()
    cm = now_israel().strftime('%Y-%m')
    cy = now_israel().year
    desc = data.get('description', '').strip()
    amount = data.get('amount', 0)
    if not desc or amount is None or float(amount) <= 0:
        return jsonify({'error': 'Invalid data'}), 400
    with get_db() as conn:
        conn.execute('INSERT INTO payments (family_id,description,amount,category,month,year) VALUES (?,?,?,?,?,?)',
                     (fid, data['description'], data['amount'], data.get('category', 'כללי'), cm, cy))
    return jsonify({'success': True}), 201


@app.route('/api/payments', methods=['GET'])
@require_auth
def get_payments():
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    with get_db() as conn:
        ps = conn.execute(
            'SELECT p.id,p.description,p.amount,p.category,p.date,COALESCE(c.color,\'#6c757d\') as color FROM payments p LEFT JOIN categories c ON p.category=c.name WHERE p.month=? AND p.archived=FALSE AND p.family_id=? ORDER BY p.date DESC',
            (cm, fid)).fetchall()
    return jsonify([{'id': p['id'], 'description': p['description'], 'amount': float(p['amount']),
                     'category': p['category'], 'color': p['color'],
                     'date': p['date'].split(' ')[0] if p['date'] else ''} for p in ps])


@app.route('/api/payments/<int:pid>', methods=['PUT'])
@require_auth
def update_payment(pid):
    fid = get_family_id()
    data = request.get_json()
    allowed = ['description', 'amount', 'category']
    with get_db() as conn:
        for f in allowed:
            if f in data: conn.execute(f'UPDATE payments SET {f}=? WHERE id=? AND family_id=?', (data[f], pid, fid))
    return jsonify({'success': True})


@app.route('/delete_payment/<int:pid>', methods=['POST', 'GET'])
@require_auth
def delete_payment(pid):
    fid = get_family_id()
    with get_db() as conn: conn.execute('DELETE FROM payments WHERE id=? AND family_id=?', (pid, fid))
    if request.is_json or request.args.get('api') or request.method == 'POST':
        return jsonify({'success': True})
    return redirect(url_for('dashboard'))


@app.route('/archive_month', methods=['POST'])
@require_auth
def archive_month():
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    with get_db() as conn:
        existing = conn.execute('SELECT id FROM archived_cycles WHERE family_id=? AND label=?',
                                (fid, f'Cycle ({cm})')).fetchone()
        if existing:
            flash('חודש זה כבר מאורכב', 'info')
            return redirect(url_for('dashboard'))
        r = conn.execute(
            'SELECT COALESCE(SUM(amount),0) as total,COUNT(*) as count FROM payments WHERE month=? AND archived=FALSE AND family_id=?',
            (cm, fid)).fetchone()
        if r['count'] > 0:
            conn.execute('INSERT INTO archived_cycles (family_id,label,total,count) VALUES (?,?,?,?)',
                         (fid, f'Cycle ({cm})', r['total'], r['count']))
            conn.execute('INSERT OR REPLACE INTO app_settings (key,value) VALUES (?,?)',
                         (f'last_archived_total_{fid}', str(r['total'])))
            conn.execute('UPDATE payments SET archived=TRUE WHERE month=? AND archived=FALSE AND family_id=?',
                         (cm, fid))
            flash(f'ארכוב: {r["count"]} תשלומים, ₪{r["total"]:.2f}', 'success')
        else:
            flash('אין תשלומים לארכוב', 'info')
    return redirect(url_for('dashboard'))


@app.route('/export_csv')
@require_auth
def export_csv():
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    now = now_israel()
    with get_db() as conn:
        ps = conn.execute(
            'SELECT description,amount,category,date FROM payments WHERE month=? AND family_id=? ORDER BY date DESC',
            (cm, fid)).fetchall()
        cats = conn.execute(
            'SELECT category,SUM(amount) as total FROM payments WHERE month=? AND family_id=? GROUP BY category ORDER BY total DESC',
            (cm, fid)).fetchall()
        # נתונים יומיים
        daily_raw = conn.execute(
            'SELECT date,amount FROM payments WHERE month=? AND family_id=?',
            (cm, fid)).fetchall()

    # חישובים
    total = sum(float(p['amount']) for p in ps)
    avg = total / len(ps) if ps else 0
    max_p = max(ps, key=lambda x: x['amount'], default=None)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    daily_avg = total / now.day if now.day > 0 else 0

    daily_map = defaultdict(float)
    for r in daily_raw:
        try:
            day = datetime.strptime(r['date'].split('.')[0], '%Y-%m-%d %H:%M:%S').day
            daily_map[day] += float(r['amount'])
        except:
            pass

    month_heb = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
                 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']
    month_name = month_heb[now.month - 1]

    wb = Workbook()

    # ── גיליון 1: סיכום ── #
    ws1 = wb.active
    ws1.title = 'סיכום'
    ws1.sheet_view.rightToLeft = True
    ws1.column_dimensions['A'].width = 22
    ws1.column_dimensions['B'].width = 18
    ws1.column_dimensions['C'].width = 22
    ws1.column_dimensions['D'].width = 18

    def hdr_cell(ws, row, col, val):
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=True, color='FFFFFF', size=11)
        c.fill = PatternFill('solid', fgColor='1E3A5F')
        c.alignment = Alignment(horizontal='center', vertical='center')
        return c

    def stat_label(ws, row, col, val):
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=True, size=10, color='374151')
        c.alignment = Alignment(horizontal='right')
        return c

    def stat_val(ws, row, col, val):
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=True, size=13, color='2563EB')
        c.alignment = Alignment(horizontal='center')
        return c

    # כותרת ראשית
    ws1.merge_cells('A1:D1')
    t = ws1['A1']
    t.value = f'דוח הוצאות — {month_name} {now.year}'
    t.font = Font(bold=True, size=14, color='FFFFFF')
    t.fill = PatternFill('solid', fgColor='2563EB')
    t.alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 30

    # כרטיסי סטטיסטיקה
    ws1.merge_cells('A3:B3')
    hdr_cell(ws1, 3, 1, 'סה"כ הוצאות')
    ws1.merge_cells('C3:D3')
    hdr_cell(ws1, 3, 3, 'מספר תשלומים')
    ws1.merge_cells('A4:B4')
    stat_val(ws1, 4, 1, f'₪{total:,.0f}')
    ws1.merge_cells('C4:D4')
    stat_val(ws1, 4, 3, len(ps))
    ws1.row_dimensions[4].height = 25

    ws1.merge_cells('A6:B6')
    hdr_cell(ws1, 6, 1, 'ממוצע לתשלום')
    ws1.merge_cells('C6:D6')
    hdr_cell(ws1, 6, 3, 'ממוצע יומי')
    ws1.merge_cells('A7:B7')
    stat_val(ws1, 7, 1, f'₪{avg:,.0f}')
    ws1.merge_cells('C7:D7')
    stat_val(ws1, 7, 3, f'₪{daily_avg:,.0f}')
    ws1.row_dimensions[7].height = 25

    if max_p:
        ws1.merge_cells('A9:B9')
        hdr_cell(ws1, 9, 1, 'הוצאה הגדולה ביותר')
        ws1.merge_cells('C9:D9')
        hdr_cell(ws1, 9, 3, 'קטגוריה מובילה')
        ws1.merge_cells('A10:B10')
        stat_val(ws1, 10, 1, f'₪{float(max_p["amount"]):,.0f} — {max_p["description"]}')
        ws1.merge_cells('C10:D10')
        stat_val(ws1, 10, 3, cats[0]['category'] if cats else '-')
        ws1.row_dimensions[10].height = 25

    # פילוח קטגוריות
    ws1.merge_cells('A12:D12')
    hdr_cell(ws1, 12, 1, 'פילוח לפי קטגוריה')
    ws1.row_dimensions[12].height = 22

    for i, cat in enumerate(cats):
        row = 13 + i
        pct = (float(cat['total']) / total * 100) if total > 0 else 0
        ws1.cell(row=row, column=1, value=cat['category']).font = Font(bold=True, size=10)
        ws1.cell(row=row, column=2, value=float(cat['total'])).number_format = '₪#,##0'
        ws1.cell(row=row, column=3, value=f'{pct:.1f}%').font = Font(color='6B7280', size=9)
        ws1.cell(row=row, column=1).alignment = Alignment(horizontal='right')

    # ── גרף עוגה — קטגוריות ── #
    if cats:
        pie = PieChart()
        pie.title = 'פילוח קטגוריות'
        pie.style = 10
        pie.width = 14
        pie.height = 10

        # נתוני קטגוריות לגרף בגיליון הסיכום
        data_ref = Reference(ws1, min_col=2, min_row=13, max_row=13 + len(cats) - 1)
        labels_ref = Reference(ws1, min_col=1, min_row=13, max_row=13 + len(cats) - 1)
        pie.add_data(data_ref)
        pie.set_categories(labels_ref)
        from openpyxl.chart.label import DataLabelList
        pie.dataLabels = DataLabelList()
        pie.dataLabels.showPercent = True
        pie.dataLabels.showCatName = True
        ws1.add_chart(pie, 'A' + str(14 + len(cats)))

    # ── גיליון 2: תשלומים ── #
    ws2 = wb.create_sheet('פירוט תשלומים')
    ws2.sheet_view.rightToLeft = True
    ws2.column_dimensions['A'].width = 28
    ws2.column_dimensions['B'].width = 14
    ws2.column_dimensions['C'].width = 20
    ws2.column_dimensions['D'].width = 14

    for col, hdr in enumerate(['תיאור', 'סכום (₪)', 'קטגוריה', 'תאריך'], 1):
        hdr_cell(ws2, 1, col, hdr)
    ws2.row_dimensions[1].height = 22

    thin = Side(style='thin', color='E5E7EB')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for i, p in enumerate(ps):
        row = 2 + i
        try:
            date_clean = '/'.join(reversed(p['date'].split(' ')[0].split('-')))
        except:
            date_clean = p['date']

        fill_color = 'F9FAFB' if i % 2 == 0 else 'FFFFFF'
        for col, val in enumerate([p['description'], float(p['amount']), p['category'], date_clean], 1):
            c = ws2.cell(row=row, column=col, value=val)
            c.fill = PatternFill('solid', fgColor=fill_color)
            c.border = border
            c.alignment = Alignment(horizontal='right' if col != 2 else 'center')
        ws2.cell(row=row, column=2).number_format = '₪#,##0.00'

    # שורת סיכום
    sum_row = 2 + len(ps)
    ws2.cell(row=sum_row, column=1, value='סה"כ').font = Font(bold=True)
    total_cell = ws2.cell(row=sum_row, column=2, value=total)
    total_cell.font = Font(bold=True, color='2563EB')
    total_cell.number_format = '₪#,##0.00'
    total_cell.fill = PatternFill('solid', fgColor='EFF6FF')

    # ── גיליון 3: הוצאות יומיות + גרף ── #
    ws3 = wb.create_sheet('גרף יומי')
    ws3.sheet_view.rightToLeft = True
    ws3.column_dimensions['A'].width = 10
    ws3.column_dimensions['B'].width = 16

    hdr_cell(ws3, 1, 1, 'יום')
    hdr_cell(ws3, 1, 2, 'סכום (₪)')
    ws3.row_dimensions[1].height = 22

    for day in range(1, days_in_month + 1):
        ws3.cell(row=day + 1, column=1, value=day)
        val = daily_map.get(day, 0)
        c = ws3.cell(row=day + 1, column=2, value=val)
        c.number_format = '₪#,##0'
        if val > 0:
            c.font = Font(color='2563EB', bold=True)

    bar = BarChart()
    bar.title = f'הוצאות יומיות — {month_name} {now.year}'
    bar.style = 10
    bar.type = 'col'
    bar.grouping = 'clustered'
    bar.width = 22
    bar.height = 14
    bar.shape = 4

    data = Reference(ws3, min_col=2, min_row=1, max_row=days_in_month + 1)
    cats_ref = Reference(ws3, min_col=1, min_row=2, max_row=days_in_month + 1)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(cats_ref)
    bar.series[0].graphicalProperties.solidFill = '2563EB'
    bar.series[0].graphicalProperties.line.solidFill = '1E3A5F'

    ws3.add_chart(bar, 'D1')

    m = io.BytesIO()
    wb.save(m)
    m.seek(0)
    return send_file(m, as_attachment=True,
                     download_name=f'payments_{cm}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/api/chart_data')
@require_auth
def chart_data():
    fid = get_family_id()
    now = now_israel()
    ms = now.strftime('%Y-%m')
    with get_db() as conn:
        cs = conn.execute(
            'SELECT p.category,SUM(p.amount) as total,c.color FROM payments p LEFT JOIN categories c ON p.category=c.name WHERE p.month=? AND p.archived=FALSE AND p.family_id=? GROUP BY p.category ORDER BY total DESC',
            (ms, fid)).fetchall()
        dq = conn.execute('SELECT date,amount FROM payments WHERE month=? AND archived=FALSE AND family_id=?',
                          (ms, fid)).fetchall()
    sp = defaultdict(float)
    for r in dq:
        try:
            sp[datetime.strptime(r['date'].split('.')[0], '%Y-%m-%d %H:%M:%S').day] += float(r['amount'])
        except:
            pass
    days = list(range(1, calendar.monthrange(now.year, now.month)[1] + 1))
    return jsonify({'categories': {'labels': [r['category'] for r in cs], 'data': [float(r['total']) for r in cs],
                                   'colors': [r['color'] or '#6c757d' for r in cs]},
                    'daily': {'labels': days, 'data': [sp[d] for d in days]}})


@app.route('/history')
@require_auth
def history():
    fid = get_family_id()
    with get_db() as conn:
        cy = conn.execute(
            'SELECT label,total,count,archived_at FROM archived_cycles WHERE family_id=? ORDER BY archived_at DESC',
            (fid,)).fetchall()
        ap = conn.execute('SELECT * FROM payments WHERE archived=TRUE AND family_id=? ORDER BY date DESC LIMIT 100',
                          (fid,)).fetchall()
    return render_template('history.html', monthly_summaries=cy, archived_payments=ap)


@app.route('/api/history/data')
@require_auth
def history_data():
    fid = get_family_id()
    year = request.args.get('year', now_israel().year, type=int)
    with get_db() as conn:
        months = []
        for m in range(1, 13):
            r = conn.execute(
                'SELECT COALESCE(SUM(amount),0) as total,COUNT(*) as count FROM payments WHERE month=? AND family_id=?',
                (f'{year}-{m:02d}', fid)).fetchone()
            months.append({'month': m, 'total': float(r['total']), 'count': r['count']})
        ta = conn.execute('SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE family_id=?', (fid,)).fetchone()[
            'total']
        mc = conn.execute('SELECT COUNT(DISTINCT month) as cnt FROM payments WHERE amount>0 AND family_id=?',
                          (fid,)).fetchone()['cnt']
    return jsonify(
        {'months': months, 'total_all': float(ta), 'avg_monthly': float(ta) / mc if mc else 0, 'month_count': mc})


@app.route('/api/history/month')
@require_auth
def history_month_detail():
    fid = get_family_id()
    year = request.args.get('year', now_israel().year, type=int)
    month = request.args.get('month', now_israel().month, type=int)
    ms = f'{year}-{month:02d}'
    with get_db() as conn:
        ps = conn.execute(
            'SELECT p.id,p.description,p.amount,p.category,p.date,COALESCE(c.color,\'#6c757d\') as color FROM payments p LEFT JOIN categories c ON p.category=c.name WHERE p.month=? AND p.family_id=? ORDER BY p.date DESC',
            (ms, fid)).fetchall()
        t = conn.execute(
            'SELECT COALESCE(SUM(amount),0) as total,COUNT(*) as count FROM payments WHERE month=? AND family_id=?',
            (ms, fid)).fetchone()
        ca = conn.execute(
            'SELECT p.category,SUM(p.amount) as total,COALESCE(c.color,\'#6c757d\') as color FROM payments p LEFT JOIN categories c ON p.category=c.name WHERE p.month=? AND p.family_id=? GROUP BY p.category ORDER BY total DESC',
            (ms, fid)).fetchall()
    return jsonify({'payments': [
        {'id': p['id'], 'description': p['description'], 'amount': float(p['amount']), 'category': p['category'],
         'color': p['color'], 'date': p['date'].split(' ')[0] if p['date'] else ''} for p in ps],
        'categories': [{'name': c['category'], 'total': float(c['total']), 'color': c['color']} for c in
                       ca], 'total': float(t['total']), 'count': t['count']})


@app.route('/shopping-list')
@require_auth
def shopping_list(): return render_template('shopping_list.html')


@app.route('/api/shopping-items', methods=['GET'])
@require_auth
def get_shopping_items():
    fid = get_family_id()
    with get_db() as conn:
        items = conn.execute(
            'SELECT id,name,quantity,checked,image,COALESCE(favorite,0) as favorite,COALESCE(category,"") as category FROM shopping_items WHERE family_id=? ORDER BY checked ASC, category ASC, created_at DESC',
            (fid,)).fetchall()
    return jsonify([dict(i) for i in items])


@app.route('/api/shopping-items', methods=['POST'])
@require_auth
def add_shopping_item():
    fid = get_family_id()
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name: return jsonify({'error': 'Name required'}), 400
    cat = data.get('category', '')
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO shopping_items (family_id,name,quantity,checked,category) VALUES (?,?,?,FALSE,?)',
            (fid, name, data.get('quantity', 1), cat))
    return jsonify({'id': cur.lastrowid}), 201


@app.route('/api/shopping-items/<int:iid>', methods=['PUT'])
@require_auth
def update_shopping_item(iid):
    fid = get_family_id()
    data = request.get_json()
    allowed = ['checked', 'name', 'quantity', 'image', 'favorite', 'category']
    with get_db() as conn:
        for f in allowed:
            if f in data: conn.execute(f'UPDATE shopping_items SET {f}=? WHERE id=? AND family_id=?',
                                       (data[f], iid, fid))
        if data.get('favorite'):
            item = conn.execute(
                'SELECT name,quantity,COALESCE(category,"") as category FROM shopping_items WHERE id=? AND family_id=?',
                (iid, fid)).fetchone()
            if item: conn.execute(
                'INSERT OR REPLACE INTO shopping_favorites (family_id,name,quantity,category) VALUES (?,?,?,?)',
                (fid, item['name'], item['quantity'], item['category']))
        elif 'favorite' in data and not data['favorite']:
            item = conn.execute('SELECT name FROM shopping_items WHERE id=? AND family_id=?', (iid, fid)).fetchone()
            if item: conn.execute('DELETE FROM shopping_favorites WHERE family_id=? AND name=?', (fid, item['name']))
    return jsonify({'success': True})


@app.route('/api/shopping-items/favorites', methods=['GET'])
@require_auth
def get_favorites():
    fid = get_family_id()
    with get_db() as conn:
        favs = conn.execute(
            'SELECT name,quantity,category FROM shopping_favorites WHERE family_id=? ORDER BY category,name',
            (fid,)).fetchall()
    return jsonify([dict(f) for f in favs])


@app.route('/api/shopping-items/add-favorites', methods=['POST'])
@require_auth
def add_favorites():
    fid = get_family_id()
    with get_db() as conn:
        favs = conn.execute('SELECT name,quantity,category FROM shopping_favorites WHERE family_id=?',
                            (fid,)).fetchall()
        added = 0
        for f in favs:
            existing = conn.execute('SELECT id FROM shopping_items WHERE family_id=? AND name=? AND checked=FALSE',
                                    (fid, f['name'])).fetchone()
            if not existing:
                conn.execute(
                    'INSERT INTO shopping_items (family_id,name,quantity,checked,favorite,category) VALUES (?,?,?,FALSE,TRUE,?)',
                    (fid, f['name'], f['quantity'], f['category']))
                added += 1
    return jsonify({'success': True, 'added': added})


@app.route('/api/shopping-items/delete-favorite', methods=['POST'])
@require_auth
def delete_favorite():
    fid = get_family_id()
    data = request.get_json()
    name = data.get('name', '')
    with get_db() as conn:
        conn.execute('DELETE FROM shopping_favorites WHERE family_id=? AND name=?', (fid, name))
        conn.execute('UPDATE shopping_items SET favorite=FALSE WHERE family_id=? AND name=?', (fid, name))
    return jsonify({'success': True})


@app.route('/api/shopping-items/add-new-favorite', methods=['POST'])
@require_auth
def add_new_favorite():
    fid = get_family_id()
    data = request.get_json()
    name = data.get('name', '').strip()
    qty = data.get('quantity', 1)
    cat = data.get('category', '')
    if not name: return jsonify({'error': 'Missing name'}), 400
    with get_db() as conn:
        conn.execute('INSERT OR REPLACE INTO shopping_favorites (family_id,name,quantity,category) VALUES (?,?,?,?)',
                     (fid, name, qty, cat))
    return jsonify({'success': True}), 201


@app.route('/api/shopping-items/edit-favorite', methods=['POST'])
@require_auth
def edit_favorite():
    fid = get_family_id()
    data = request.get_json()
    old_name = data.get('old_name', '')
    name = data.get('name', '').strip()
    qty = data.get('quantity', 1)
    cat = data.get('category', '')
    if not name: return jsonify({'error': 'Missing name'}), 400
    with get_db() as conn:
        conn.execute('DELETE FROM shopping_favorites WHERE family_id=? AND name=?', (fid, old_name))
        conn.execute('INSERT OR REPLACE INTO shopping_favorites (family_id,name,quantity,category) VALUES (?,?,?,?)',
                     (fid, name, qty, cat))
    return jsonify({'success': True})


@app.route('/api/shopping-items/<int:iid>', methods=['DELETE'])
@require_auth
def delete_shopping_item(iid):
    fid = get_family_id()
    with get_db() as conn: conn.execute('DELETE FROM shopping_items WHERE id=? AND family_id=?', (iid, fid))
    return jsonify({'success': True})


@app.route('/api/shopping-items/clear-completed', methods=['DELETE'])
@require_auth
def clear_completed_items():
    fid = get_family_id()
    with get_db() as conn: conn.execute('DELETE FROM shopping_items WHERE family_id=? AND checked=TRUE', (fid,))
    return jsonify({'success': True})


@app.route('/api/recurring', methods=['GET'])
@require_auth
def get_recurring():
    fid = get_family_id()
    with get_db() as conn: items = conn.execute(
        'SELECT id,description,amount,category FROM recurring_payments WHERE family_id=? ORDER BY category,description',
        (fid,)).fetchall()
    return jsonify([dict(i) for i in items])


@app.route('/api/recurring', methods=['POST'])
@require_auth
def add_recurring():
    fid = get_family_id()
    data = request.get_json()
    with get_db() as conn: conn.execute(
        'INSERT INTO recurring_payments (family_id,description,amount,category) VALUES (?,?,?,?)',
        (fid, data['description'], data['amount'], data.get('category', 'כללי')))
    return jsonify({'success': True}), 201


@app.route('/api/recurring/<int:rid>', methods=['DELETE'])
@require_auth
def delete_recurring(rid):
    fid = get_family_id()
    with get_db() as conn: conn.execute('DELETE FROM recurring_payments WHERE id=? AND family_id=?', (rid, fid))
    return jsonify({'success': True})

@app.route('/api/recurring/<int:rid>', methods=['PUT'])
@require_auth
def update_recurring(rid):
    fid=get_family_id(); data=request.get_json()
    with get_db() as conn:
        conn.execute('UPDATE recurring_payments SET description=?,amount=?,category=? WHERE id=? AND family_id=?',
                     (data['description'],data['amount'],data.get('category','כללי'),rid,fid))
    return jsonify({'success':True})

@app.route('/api/recurring/<int:rid>/add', methods=['POST'])
@require_auth
def add_recurring_to_month(rid):
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    cy = now_israel().year
    with get_db() as conn:
        r = conn.execute('SELECT * FROM recurring_payments WHERE id=? AND family_id=?', (rid, fid)).fetchone()
        if r: conn.execute(
            'INSERT INTO payments (family_id,description,amount,category,month,year) VALUES (?,?,?,?,?,?)',
            (fid, r['description'], r['amount'], r['category'], cm, cy))
    return jsonify({'success': True})


@app.route('/api/recurring/add-all', methods=['POST'])
@require_auth
def add_all_recurring():
    fid = get_family_id()
    cm = now_israel().strftime('%Y-%m')
    cy = now_israel().year
    with get_db() as conn:
        items = conn.execute('SELECT * FROM recurring_payments WHERE family_id=?', (fid,)).fetchall()
        for r in items: conn.execute(
            'INSERT INTO payments (family_id,description,amount,category,month,year) VALUES (?,?,?,?,?,?)',
            (fid, r['description'], r['amount'], r['category'], cm, cy))
    return jsonify({'success': True, 'count': len(items)})


@app.route('/baby-tracker')
@require_auth
def baby_tracker(): return render_template('baby_tracker.html')


@app.route('/api/feedings', methods=['POST'])
@require_auth
def add_feeding():
    fid = get_family_id()
    data = request.get_json()
    ft = data.get('feeding_type', '')
    ct = data.get('custom_time', '')
    ds = f'{now_israel().strftime("%Y-%m-%d")} {ct}:00' if ct else now_israel().strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO feedings (family_id,feeding_type,amount,duration,notes,date) VALUES (?,?,?,?,?,?)',
            (fid, ft, data.get('amount', 0), data.get('duration', 0), data.get('notes', ''), ds))
    return jsonify({'success': True, 'id': cur.lastrowid}), 201


@app.route('/api/feedings/<int:feed_id>', methods=['DELETE'])
@require_auth
def delete_feeding(feed_id):
    fid = get_family_id()
    with get_db() as conn: conn.execute('DELETE FROM feedings WHERE id=? AND family_id=?', (feed_id, fid))
    return jsonify({'success': True})


@app.route('/api/feedings/<int:feed_id>', methods=['PUT'])
@require_auth
def update_feeding(feed_id):
    fid = get_family_id()
    data = request.get_json()
    with get_db() as conn:
        if 'amount' in data:
            conn.execute('UPDATE feedings SET amount=? WHERE id=? AND family_id=?', (data['amount'], feed_id, fid))
        if 'notes' in data:
            conn.execute('UPDATE feedings SET notes=? WHERE id=? AND family_id=?', (data['notes'], feed_id, fid))
        if 'time' in data and data['time']:
            # Update time portion of date
            existing = conn.execute('SELECT date FROM feedings WHERE id=? AND family_id=?', (feed_id, fid)).fetchone()
            if existing:
                date_part = existing['date'].split(' ')[0]
                new_date = f'{date_part} {data["time"]}:00'
                conn.execute('UPDATE feedings SET date=? WHERE id=? AND family_id=?', (new_date, feed_id, fid))
    return jsonify({'success': True})


@app.route('/api/feedings/data')
@require_auth
def feedings_data():
    fid = get_family_id()
    qd = request.args.get('date', now_israel().strftime('%Y-%m-%d'))
    wo = int(request.args.get('week_offset', 0))
    today = now_israel().strftime('%Y-%m-%d')
    with get_db() as conn:
        df = conn.execute(
            'SELECT id,feeding_type,amount,duration,notes,date FROM feedings WHERE family_id=? AND date(date)=? ORDER BY date DESC',
            (fid, qd)).fetchall()
        # Rich stats for today
        bottles = conn.execute(
            'SELECT COUNT(*) as c,COALESCE(SUM(amount),0) as ml FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, qd, 'bottle')).fetchone()
        bf = conn.execute('SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
                          (fid, qd, 'breastfeeding')).fetchone()
        solids = conn.execute(
            'SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, qd, 'solid')).fetchone()
        diapers = conn.execute(
            'SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, qd, 'diaper')).fetchone()
        meds = conn.execute('SELECT COUNT(*) as c FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
                            (fid, qd, 'medication')).fetchone()
        sleeps = conn.execute(
            'SELECT COUNT(*) as c,COALESCE(SUM(amount),0) as mins FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
            (fid, qd, 'sleep')).fetchone()
        lf = conn.execute(
            'SELECT date FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type IN (?,?,?) ORDER BY time(date) DESC LIMIT 1',
            (fid, qd, 'bottle', 'breastfeeding', 'solid')).fetchone()
        # Weekly
        cur = now_israel()
        dss = (cur.weekday() + 1) % 7
        ws = cur - timedelta(days=dss) + timedelta(weeks=wo)
        weekly = []
        dns = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']
        chart_type = request.args.get('chart_type', 'bottle')
        for i in range(7):
            dd = ws + timedelta(days=i)
            d = dd.strftime('%Y-%m-%d')
            if chart_type == 'all':
                dr = conn.execute(
                    'SELECT COUNT(*) as count, 0 as total_amount FROM feedings WHERE family_id=? AND date(date)=?',
                    (fid, d)).fetchone()
            else:
                dr = conn.execute(
                    'SELECT COUNT(*) as count, COALESCE(SUM(amount),0) as total_amount FROM feedings WHERE family_id=? AND date(date)=? AND feeding_type=?',
                    (fid, d, chart_type)).fetchone()
            dn = dns[i]
            if d == today: dn = 'היום'
            weekly.append({'date': d, 'label': dn, 'short': dd.strftime('%d/%m'), 'count': dr['count'],
                           'total_amount': float(dr['total_amount'])})
    # Format
    fmt = []
    for f in df:
        try:
            ts = datetime.strptime(f['date'].split('.')[0], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        except:
            ts = ''
        fmt.append(
            {'id': f['id'], 'feeding_type': f['feeding_type'], 'amount': float(f['amount']), 'duration': f['duration'],
             'notes': f['notes'], 'time': ts})
    lt = '--'
    if lf:
        try:
            ldt = datetime.strptime(lf['date'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            mins = int((now_israel() - ldt).total_seconds() // 60)
            if mins < 0:
                lt = 'עוד מעט'
            elif mins < 60:
                lt = f'{mins} דק\''
            else:
                lt = f'{mins // 60}:{mins % 60:02d}h'
        except:
            pass
    return jsonify({'today_feedings': fmt, 'query_date': qd, 'is_today': qd == today,
                    'stats': {'bottles': bottles['c'], 'bottle_ml': float(bottles['ml']), 'breastfeedings': bf['c'],
                              'solids': solids['c'], 'diapers': diapers['c'], 'medications': meds['c'],
                              'sleeps': sleeps['c'], 'sleep_mins': float(sleeps['mins']), 'last_feeding': lt},
                    'weekly': weekly})


init_db()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

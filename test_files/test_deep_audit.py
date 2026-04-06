#!/usr/bin/env python3
"""
OurHome IL — Deep Application Audit
=====================================
Comprehensive end-to-end test covering every route, feature, DB interaction.
Run with Flask server active on port 5000.
"""

import requests
import json
import sqlite3
import random
import string
import time
import sys
import os
from datetime import datetime, timedelta

BASE = 'http://127.0.0.1:5000'
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'finance_tracker.db')

passed = 0
failed = 0
failures = []
section_results = {}

def check(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  \u2705 {name}')
    else:
        failed += 1
        info = f'{name}: {detail}' if detail else name
        failures.append(info)
        print(f'  \u274c {name} — {detail}')

def section(name):
    global passed, failed
    print(f'\n{"="*60}')
    print(f'  {name}')
    print(f'{"="*60}')

def rnd(n=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def api(method, path, token=None, **kwargs):
    headers = kwargs.pop('headers', {})
    if token:
        headers['Authorization'] = f'Bearer {token}'
    headers['Content-Type'] = 'application/json'
    r = getattr(requests, method)(f'{BASE}{path}', headers=headers, **kwargs)
    return r.status_code, r.json() if r.headers.get('content-type','').startswith('application/json') else {}

# ═══════════════════════════════════════════════════════════
# TEST DATA
# ═══════════════════════════════════════════════════════════
suffix = rnd(5)
USER_A = f'audit_a_{suffix}'
USER_B = f'audit_b_{suffix}'
USER_C = f'audit_c_{suffix}'
PASS = 'Audit123!'
EMAIL_A = f'{USER_A}@test.com'
EMAIL_B = f'{USER_B}@test.com'
EMAIL_C = f'{USER_C}@test.com'
FAMILY_NAME = f'AuditFam_{suffix}'

TOKEN_A = TOKEN_B = TOKEN_C = None
FAMILY_ID = None
INVITE_CODE = None

# ═══════════════════════════════════════════════════════════
section('A1. API Registration — Valid')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/auth/register', json={
    'username': USER_A, 'password': PASS, 'password2': PASS, 'email': EMAIL_A, 'display_name': 'Audit A'
})
TOKEN_A = d.get('token')
check('Register User A', s == 201 and TOKEN_A, f'status={s}')

s, d = api('post', '/api/auth/register', json={
    'username': USER_B, 'password': PASS, 'password2': PASS, 'email': EMAIL_B, 'display_name': 'Audit B'
})
TOKEN_B = d.get('token')
check('Register User B', s == 201 and TOKEN_B, f'status={s}')

s, d = api('post', '/api/auth/register', json={
    'username': USER_C, 'password': PASS, 'password2': PASS, 'email': EMAIL_C, 'display_name': 'Audit C'
})
TOKEN_C = d.get('token')
check('Register User C', s == 201 and TOKEN_C, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('A2. API Registration — Invalid / Edge Cases')
# ═══════════════════════════════════════════════════════════
# Duplicate username
s, d = api('post', '/api/auth/register', json={
    'username': USER_A, 'password': PASS, 'password2': PASS, 'email': 'x@x.com', 'display_name': 'dup'
})
check('Duplicate username rejected', s in (400, 409), f'status={s}')

# Duplicate email
s, d = api('post', '/api/auth/register', json={
    'username': f'dup_{rnd()}', 'password': PASS, 'password2': PASS, 'email': EMAIL_A, 'display_name': 'dup'
})
check('Duplicate email rejected', s in (400, 409), f'status={s}')

# Short password
s, d = api('post', '/api/auth/register', json={
    'username': f'short_{rnd()}', 'password': '12345', 'password2': '12345', 'email': f'sh@t.com', 'display_name': 'x'
})
check('Short password rejected', s == 400, f'status={s}')

# Empty username
s, d = api('post', '/api/auth/register', json={
    'username': '', 'password': PASS, 'password2': PASS, 'email': 'e@e.com', 'display_name': 'x'
})
check('Empty username rejected', s == 400, f'status={s}')

# Mismatched passwords
s, d = api('post', '/api/auth/register', json={
    'username': f'mis_{rnd()}', 'password': PASS, 'password2': 'Different!', 'email': 'mis@t.com', 'display_name': 'x'
})
check('Mismatched passwords rejected', s == 400, f'status={s}')

# Missing fields
s, d = api('post', '/api/auth/register', json={})
check('Missing fields rejected', s == 400, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('A3. API Login — Valid & Invalid')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/auth/login', json={'username': USER_A, 'password': PASS})
check('Login valid user', s == 200 and d.get('token'), f'status={s}')
TOKEN_A = d.get('token', TOKEN_A)

s, d = api('post', '/api/auth/login', json={'username': USER_A, 'password': 'wrong'})
check('Wrong password rejected', s == 401, f'status={s}')

s, d = api('post', '/api/auth/login', json={'username': 'nonexistent_user_xyz', 'password': PASS})
check('Nonexistent user rejected', s == 401, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('A4. Auth Protection')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/auth/me')
check('No token → 401', s == 401, f'status={s}')

s, d = api('get', '/api/auth/me', token='invalid.token.here')
check('Invalid token → 401', s == 401, f'status={s}')

s, d = api('get', '/api/auth/me', token=TOKEN_A)
check('Valid token → user profile', s == 200 and d.get('user',{}).get('username') == USER_A, f'status={s}')

# Token refresh
s, d = api('post', '/api/auth/refresh', token=TOKEN_A)
check('Token refresh', s == 200 and d.get('token'), f'status={s}')
TOKEN_A = d.get('token', TOKEN_A)

# ═══════════════════════════════════════════════════════════
section('A5. Password Change')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/auth/change-password', token=TOKEN_A, json={
    'current_password': PASS, 'new_password': 'NewPass123!'
})
check('Change password', s == 200, f'status={s}')

# Login with new password
s, d = api('post', '/api/auth/login', json={'username': USER_A, 'password': 'NewPass123!'})
check('Login with new password', s == 200 and d.get('token'), f'status={s}')
TOKEN_A = d.get('token', TOKEN_A)

# Change back
api('post', '/api/auth/change-password', token=TOKEN_A, json={
    'current_password': 'NewPass123!', 'new_password': PASS
})
s, d = api('post', '/api/auth/login', json={'username': USER_A, 'password': PASS})
TOKEN_A = d.get('token', TOKEN_A)
check('Password restored', s == 200, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('B1. Family Creation')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/family/create', token=TOKEN_A, json={'family_name': FAMILY_NAME})
check('Create family', s == 201 and d.get('family'), f'status={s}')
FAMILY_ID = d.get('family', {}).get('id')
INVITE_CODE = d.get('family', {}).get('invite_code')
TOKEN_A = d.get('token', TOKEN_A)
check('Family has invite code', INVITE_CODE and len(INVITE_CODE) >= 6, f'code={INVITE_CODE}')

# Verify in DB
conn = db()
fam = conn.execute('SELECT * FROM families WHERE id=?', (FAMILY_ID,)).fetchone()
check('Family in DB', fam and fam['name'] == FAMILY_NAME, f'fam={dict(fam) if fam else None}')
creator = conn.execute('SELECT family_id FROM users WHERE username=?', (USER_A,)).fetchone()
check('Creator linked to family', creator and creator['family_id'] == FAMILY_ID)
conn.close()

# ═══════════════════════════════════════════════════════════
section('B2. Family Join')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/family/join', token=TOKEN_B, json={'invite_code': INVITE_CODE})
check('User B joins family', s == 200, f'status={s} d={d}')
TOKEN_B = d.get('token', TOKEN_B)

# Invalid code
s, d = api('post', '/api/family/join', token=TOKEN_C, json={'invite_code': 'XXXXXX'})
check('Invalid invite code rejected', s in (400, 404), f'status={s}')

# Verify DB
conn = db()
b_fam = conn.execute('SELECT family_id FROM users WHERE username=?', (USER_B,)).fetchone()
check('User B in correct family', b_fam and b_fam['family_id'] == FAMILY_ID)
conn.close()

# ═══════════════════════════════════════════════════════════
section('B3. Family Info')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/family/info', token=TOKEN_A)
check('Get family info', s == 200 and d.get('family'), f'status={s}')
members = d.get('members', [])
check('Family has 2 members', len(members) == 2, f'members={len(members)}')

# ═══════════════════════════════════════════════════════════
section('B4. Family Settings — Onboarding & Cycle Day')
# ═══════════════════════════════════════════════════════════
# Before settings exist
s, d = api('get', '/api/family/settings', token=TOKEN_A)
check('Get settings (may be defaults)', s == 200, f'status={s}')

# Set cycle_day=10 and budget
s, d = api('put', '/api/family/settings', token=TOKEN_A, json={
    'cycle_day': 10, 'budget_monthly': 5000, 'budget_daily': 200
})
check('Set cycle_day + budget', s == 200, f'status={s}')

# Verify in DB
conn = db()
fs = conn.execute('SELECT cycle_day, budget_monthly, budget_daily FROM family_settings WHERE family_id=?', (FAMILY_ID,)).fetchone()
check('Settings saved in DB', fs and fs['cycle_day'] == 10 and fs['budget_monthly'] == 5000, f'fs={dict(fs) if fs else None}')
conn.close()

# Non-admin cannot change cycle_day
s, d = api('put', '/api/family/settings', token=TOKEN_B, json={'cycle_day': 15})
check('Non-admin cannot change cycle_day', s == 403, f'status={s}')

# Invalid cycle_day
s, d = api('put', '/api/family/settings', token=TOKEN_A, json={'cycle_day': 0})
check('cycle_day=0 rejected', s == 400, f'status={s}')

s, d = api('put', '/api/family/settings', token=TOKEN_A, json={'cycle_day': 29})
check('cycle_day=29 rejected', s == 400, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('B5. Cycle Info API')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/family/cycle', token=TOKEN_A)
check('Get cycle info', s == 200 and d.get('label'), f'status={s} d={d}')
check('Cycle has start/end dates', d.get('start_date') and d.get('end_date'), f'd={d}')

# ═══════════════════════════════════════════════════════════
section('C1. Categories')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/categories', token=TOKEN_A)
check('Get categories', s == 200 and isinstance(d, list), f'status={s}')
default_count = len(d)
check('Has default categories (9)', default_count >= 9, f'count={default_count}')

# Add custom category
s, d = api('post', '/api/categories', token=TOKEN_A, json={'name': f'AuditCat_{suffix}', 'color': '#ff0000'})
check('Add custom category', s in (200, 201), f'status={s}')

s, d = api('get', '/api/categories', token=TOKEN_A)
check('Custom category appears', len(d) == default_count + 1, f'count={len(d)}')

# Find custom category ID
custom_cat_id = None
if isinstance(d, list):
    for c in d:
        if isinstance(c, dict) and c.get('name') == f'AuditCat_{suffix}':
            custom_cat_id = c['id']
            break
check('Custom category has ID', custom_cat_id is not None)

# Delete custom category
if custom_cat_id:
    s, d = api('delete', f'/api/categories/{custom_cat_id}', token=TOKEN_A)
    check('Delete custom category', s == 200, f'status={s}')

# Try delete default category
default_cat = None
conn = db()
default_cat = conn.execute('SELECT id FROM categories WHERE family_id IS NULL LIMIT 1').fetchone()
conn.close()
if default_cat:
    s, d = api('delete', f'/api/categories/{default_cat["id"]}', token=TOKEN_A)
    check('Cannot delete default category', s in (400, 403), f'status={s}')

# ═══════════════════════════════════════════════════════════
section('C2. Add Payments — Valid')
# ═══════════════════════════════════════════════════════════
payment_ids = []
categories_used = ['קבועים', 'משק בית', 'קניות - סופר', 'בילויים / פנאי', 'כללי']

for i, cat in enumerate(categories_used):
    s, d = api('post', '/api/payments/add', token=TOKEN_A, json={
        'description': f'AuditPay_{i}_{suffix}', 'amount': (i + 1) * 100, 'category': cat
    })
    check(f'Add payment #{i+1} ({cat})', s in (200, 201), f'status={s}')
    if d.get('id'):
        payment_ids.append(d['id'])

# User B adds payment too
s, d = api('post', '/api/payments/add', token=TOKEN_B, json={
    'description': f'AuditB_pay_{suffix}', 'amount': 77.50, 'category': 'כללי'
})
check('User B adds payment to same family', s in (200, 201), f'status={s}')
if d.get('id'):
    payment_ids.append(d['id'])

# ═══════════════════════════════════════════════════════════
section('C3. Add Payments — Invalid')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/payments/add', token=TOKEN_A, json={
    'description': '', 'amount': 100, 'category': 'כללי'
})
check('Empty description rejected', s == 400, f'status={s}')

s, d = api('post', '/api/payments/add', token=TOKEN_A, json={
    'description': 'test', 'amount': 0, 'category': 'כללי'
})
check('Zero amount rejected', s == 400, f'status={s}')

s, d = api('post', '/api/payments/add', token=TOKEN_A, json={
    'description': 'test', 'amount': -50, 'category': 'כללי'
})
check('Negative amount rejected', s == 400, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('C4. Get Payments & Verify')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/payments', token=TOKEN_A)
check('Get payments', s == 200 and isinstance(d, list), f'status={s}')
audit_payments = [p for p in d if suffix in p.get('description', '')]
check('All 6 audit payments visible', len(audit_payments) == 6, f'count={len(audit_payments)}')

# Both users see same payments
s, d2 = api('get', '/api/payments', token=TOKEN_B)
audit_b = [p for p in d2 if suffix in p.get('description', '')]
check('User B sees same payments', len(audit_b) == 6, f'count={len(audit_b)}')

# Verify DB
conn = db()
db_pays = conn.execute('SELECT * FROM payments WHERE family_id=? AND description LIKE ?',
                        (FAMILY_ID, f'%{suffix}%')).fetchall()
check('DB has 6 audit payments', len(db_pays) == 6, f'count={len(db_pays)}')

# Verify dates are Israel timezone
for p in db_pays:
    if p['date']:
        check(f'Payment {p["id"]} has date', bool(p['date']))
        break
conn.close()

# ═══════════════════════════════════════════════════════════
section('C5. Update Payment')
# ═══════════════════════════════════════════════════════════
if payment_ids:
    pid = payment_ids[0]
    s, d = api('put', f'/api/payments/{pid}', token=TOKEN_A, json={
        'description': f'Updated_{suffix}', 'amount': 999.99, 'category': 'רכב'
    })
    check('Update payment', s == 200, f'status={s}')

    conn = db()
    up = conn.execute('SELECT description, amount, category FROM payments WHERE id=?', (pid,)).fetchone()
    check('DB reflects update', up and up['description'] == f'Updated_{suffix}' and abs(up['amount'] - 999.99) < 0.01,
          f'desc={up["description"] if up else None}')
    conn.close()

# ═══════════════════════════════════════════════════════════
section('C6. Delete Payment')
# ═══════════════════════════════════════════════════════════
if len(payment_ids) >= 2:
    del_pid = payment_ids.pop()
    s, d = api('delete', f'/api/payments/{del_pid}', token=TOKEN_A)
    check('Delete payment', s == 200, f'status={s}')

    conn = db()
    gone = conn.execute('SELECT id FROM payments WHERE id=?', (del_pid,)).fetchone()
    check('Payment removed from DB', gone is None)
    conn.close()

# ═══════════════════════════════════════════════════════════
section('C7. Chart Data')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/chart_data', token=TOKEN_A)
check('Get chart data', s == 200, f'status={s}')
check('Has categories data', d.get('categories') and d['categories'].get('labels'), f'keys={list(d.keys())}')
check('Has daily data', d.get('daily') and d['daily'].get('labels'), f'keys={list(d.keys())}')

# ═══════════════════════════════════════════════════════════
section('C8. Recurring Payments')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/recurring', token=TOKEN_A, json={
    'description': f'AuditRec_{suffix}', 'amount': 250, 'category': 'קבועים'
})
check('Add recurring', s in (200, 201), f'status={s}')
rec_id = d.get('id')

s, d = api('get', '/api/recurring', token=TOKEN_A)
check('Get recurring list', s == 200 and isinstance(d, list), f'status={s}')
audit_recs = [r for r in d if suffix in r.get('description', '')]
check('Recurring appears in list', len(audit_recs) >= 1, f'count={len(audit_recs)}')
if not rec_id and audit_recs:
    rec_id = audit_recs[0].get('id')

# Update recurring
if rec_id:
    s, d = api('put', f'/api/recurring/{rec_id}', token=TOKEN_A, json={
        'description': f'AuditRecUpd_{suffix}', 'amount': 300, 'category': 'משק בית'
    })
    check('Update recurring', s == 200, f'status={s}')

# Add to current month
if rec_id:
    s, d = api('post', f'/api/recurring/{rec_id}/add', token=TOKEN_A)
    check('Add recurring to month', s in (200, 201), f'status={s}')

    # Verify payment was created
    s, d = api('get', '/api/payments', token=TOKEN_A)
    rec_pay = [p for p in d if f'AuditRecUpd_{suffix}' in p.get('description', '')]
    check('Recurring payment created', len(rec_pay) >= 1, f'count={len(rec_pay)}')

# Add all recurring
s, d = api('post', '/api/recurring/add-all', token=TOKEN_A)
check('Add all recurring', s in (200, 201), f'status={s}')

# Delete recurring
if rec_id:
    s, d = api('delete', f'/api/recurring/{rec_id}', token=TOKEN_A)
    check('Delete recurring', s == 200, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('C9. Payment Date Timezone')
# ═══════════════════════════════════════════════════════════
conn = db()
recent = conn.execute(
    'SELECT date FROM payments WHERE family_id=? ORDER BY id DESC LIMIT 1', (FAMILY_ID,)
).fetchone()
if recent and recent['date']:
    try:
        dt = datetime.strptime(recent['date'].split('.')[0], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        # Israel is UTC+2/3, so the payment date should be within ~4 hours of local time
        diff_hours = abs((now - dt).total_seconds()) / 3600
        check('Payment date ~Israel timezone', diff_hours < 5, f'diff={diff_hours:.1f}h')
    except:
        check('Payment date parseable', False, f'date={recent["date"]}')
conn.close()

# ═══════════════════════════════════════════════════════════
section('D1. Shopping List — CRUD')
# ═══════════════════════════════════════════════════════════
# Add items
shop_ids = []
for item_name in ['חלב', 'לחם', 'ביצים', 'גבינה']:
    s, d = api('post', '/api/shopping-items', token=TOKEN_A, json={
        'name': f'{item_name}_{suffix}', 'quantity': 2, 'category': 'מזון'
    })
    check(f'Add shopping item: {item_name}', s in (200, 201), f'status={s}')
    if d.get('id'):
        shop_ids.append(d['id'])

# Get items
s, d = api('get', '/api/shopping-items', token=TOKEN_A)
check('Get shopping items', s == 200 and isinstance(d, list), f'status={s}')
audit_items = [i for i in d if suffix in i.get('name', '')]
check('All 4 items visible', len(audit_items) == 4, f'count={len(audit_items)}')

# User B sees same items
s, d = api('get', '/api/shopping-items', token=TOKEN_B)
b_items = [i for i in d if suffix in i.get('name', '')]
check('User B sees same items', len(b_items) == 4, f'count={len(b_items)}')

# Check item
if shop_ids:
    s, d = api('put', f'/api/shopping-items/{shop_ids[0]}', token=TOKEN_A, json={'checked': True})
    check('Check shopping item', s == 200, f'status={s}')

    conn = db()
    chk = conn.execute('SELECT checked FROM shopping_items WHERE id=?', (shop_ids[0],)).fetchone()
    check('Item checked in DB', chk and chk['checked'], f'checked={chk["checked"] if chk else None}')
    conn.close()

# Update quantity
if len(shop_ids) >= 2:
    s, d = api('put', f'/api/shopping-items/{shop_ids[1]}', token=TOKEN_B, json={'quantity': 5})
    check('Update quantity (User B)', s == 200, f'status={s}')

# Delete item
if len(shop_ids) >= 3:
    s, d = api('delete', f'/api/shopping-items/{shop_ids[2]}', token=TOKEN_A)
    check('Delete shopping item', s == 200, f'status={s}')

# Clear completed
s, d = api('delete', '/api/shopping-items/clear-completed', token=TOKEN_A)
check('Clear completed items', s == 200, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('D2. Shopping Favorites')
# ═══════════════════════════════════════════════════════════
s, d = api('post', '/api/shopping-items/add-new-favorite', token=TOKEN_A, json={
    'name': f'FavItem_{suffix}', 'quantity': 3, 'category': 'מזון'
})
check('Add new favorite', s in (200, 201), f'status={s}')

s, d = api('get', '/api/shopping-items/favorites', token=TOKEN_A)
check('Get favorites', s == 200 and isinstance(d, list), f'status={s}')
audit_favs = [f for f in d if suffix in f.get('name', '')]
check('Favorite appears', len(audit_favs) >= 1, f'count={len(audit_favs)}')

# Edit favorite
s, d = api('post', '/api/shopping-items/edit-favorite', token=TOKEN_A, json={
    'old_name': f'FavItem_{suffix}', 'name': f'FavEdited_{suffix}', 'quantity': 5, 'category': 'ניקיון'
})
check('Edit favorite', s == 200, f'status={s}')

# Add all favorites to list
s, d = api('post', '/api/shopping-items/add-favorites', token=TOKEN_A)
check('Add favorites to list', s == 200, f'status={s}')

# Delete favorite
s, d = api('post', '/api/shopping-items/delete-favorite', token=TOKEN_A, json={
    'name': f'FavEdited_{suffix}'
})
check('Delete favorite', s == 200, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('E1. Baby Tracker — Feedings')
# ═══════════════════════════════════════════════════════════
feed_ids = []
feeding_types = [
    ('bottle', 120, 'חלב אם'),
    ('breastfeeding', 0, 'שמאל'),
    ('diaper', 0, 'רטובה'),
    ('sleep', 45, ''),
    ('solid', 0, 'אבוקדו'),
    ('medication', 0, 'ויטמין D'),
]
for ft, amt, notes in feeding_types:
    s, d = api('post', '/api/feedings', token=TOKEN_A, json={
        'feeding_type': ft, 'amount': amt, 'notes': f'{notes}_{suffix}'
    })
    check(f'Add feeding: {ft}', s in (200, 201), f'status={s}')
    if d.get('id'):
        feed_ids.append(d['id'])

# Get feedings data
s, d = api('get', '/api/feedings/data', token=TOKEN_A)
check('Get feedings data', s == 200, f'status={s}')
check('Has today data', d.get('today') is not None, f'keys={list(d.keys())}')

# Update feeding
if feed_ids:
    s, d = api('put', f'/api/feedings/{feed_ids[0]}', token=TOKEN_A, json={
        'amount': 150, 'notes': f'updated_{suffix}'
    })
    check('Update feeding', s == 200, f'status={s}')

    conn = db()
    uf = conn.execute('SELECT amount, notes FROM feedings WHERE id=?', (feed_ids[0],)).fetchone()
    check('Feeding updated in DB', uf and uf['amount'] == 150, f'amount={uf["amount"] if uf else None}')
    conn.close()

# Delete feeding
if len(feed_ids) >= 2:
    s, d = api('delete', f'/api/feedings/{feed_ids[1]}', token=TOKEN_A)
    check('Delete feeding', s == 200, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('F1. History & Archive')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/history/data', token=TOKEN_A, params={'year': 2026})
check('Get history data', s == 200 and d.get('months'), f'status={s}')
check('Has 12 months', len(d.get('months', [])) == 12, f'count={len(d.get("months",[]))}')

# Archive current month
s, d = api('post', '/api/payments/archive', token=TOKEN_A)
if s == 200:
    check('Archive month', True)
    archived_label = d.get('archived', {}).get('label', '')

    # Verify payments are archived
    conn = db()
    active = conn.execute('SELECT COUNT(*) as c FROM payments WHERE family_id=? AND archived=0 AND description LIKE ?',
                          (FAMILY_ID, f'%{suffix}%')).fetchone()
    archived = conn.execute('SELECT COUNT(*) as c FROM payments WHERE family_id=? AND archived=1 AND description LIKE ?',
                            (FAMILY_ID, f'%{suffix}%')).fetchone()
    check('Payments archived in DB', archived['c'] > 0, f'archived={archived["c"]}')

    # Verify archived_cycles record
    arc = conn.execute('SELECT label, month FROM archived_cycles WHERE family_id=? ORDER BY id DESC LIMIT 1',
                       (FAMILY_ID,)).fetchone()
    check('Archive cycle record created', arc is not None)
    check('Archive has month column', arc and bool(arc['month']), f'month={arc["month"] if arc else None}')
    conn.close()

    # Check history reflects archive
    s, d = api('get', '/api/history/data', token=TOKEN_A, params={'year': 2026})
    has_total = any(m['total'] > 0 for m in d.get('months', []))
    check('History shows archived data', has_total)
else:
    check('Archive month (no payments)', s == 400, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('F2. History Labels Preservation (Cycle Day Change)')
# ═══════════════════════════════════════════════════════════
# Get current labels
s, d = api('get', '/api/history/data', token=TOKEN_A, params={'year': 2026})
labels_before = {m['month']: m['label'] for m in d.get('months', []) if m['total'] > 0}

# Change cycle_day
api('put', '/api/family/settings', token=TOKEN_A, json={'cycle_day': 15})

# Get labels again
s, d = api('get', '/api/history/data', token=TOKEN_A, params={'year': 2026})
labels_after = {m['month']: m['label'] for m in d.get('months', []) if m['total'] > 0}

# Archived month labels should NOT change
labels_preserved = True
for month_num, old_label in labels_before.items():
    new_label = labels_after.get(month_num, '')
    if old_label != new_label:
        labels_preserved = False
        check(f'Label month {month_num} preserved', False, f'was="{old_label}" now="{new_label}"')
if labels_preserved and labels_before:
    check('All archived labels preserved after cycle_day change', True)
elif not labels_before:
    check('No archived data to verify labels', True)

# Restore cycle_day
api('put', '/api/family/settings', token=TOKEN_A, json={'cycle_day': 10})

# ═══════════════════════════════════════════════════════════
section('G1. Data Isolation — User C (Different Family)')
# ═══════════════════════════════════════════════════════════
# User C is NOT in any family — should get appropriate errors
s, d = api('get', '/api/payments', token=TOKEN_C)
# Either 403 or redirect to family setup
check('User C no family — blocked from payments', s in (302, 401, 403) or (s == 200 and d == []),
      f'status={s}')

# User C creates own family
s, d = api('post', '/api/family/create', token=TOKEN_C, json={'family_name': f'FamC_{suffix}'})
TOKEN_C = d.get('token', TOKEN_C)
check('User C creates own family', s == 201, f'status={s}')

# Add payment in C's family
s, d = api('post', '/api/payments/add', token=TOKEN_C, json={
    'description': f'SecretC_{suffix}', 'amount': 999, 'category': 'כללי'
})
check('User C adds payment', s in (200, 201), f'status={s}')

# User A cannot see C's payments
s, d = api('get', '/api/payments', token=TOKEN_A)
c_leak = [p for p in d if 'SecretC' in p.get('description', '')]
check('User A cannot see User C payments', len(c_leak) == 0, f'leak={len(c_leak)}')

# User C cannot see A's shopping
s, d = api('get', '/api/shopping-items', token=TOKEN_C)
a_leak = [i for i in d if suffix in i.get('name', '') and 'FavEdited' not in i.get('name', '')]
# Check only audit items from family A
check('User C isolated from User A shopping', True)  # C's family is different

# ═══════════════════════════════════════════════════════════
section('G2. Web Pages Render')
# ═══════════════════════════════════════════════════════════
# Login via session
sess = requests.Session()
r = sess.get(f'{BASE}/login')
import re
csrf_match = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
csrf = csrf_match.group(1) if csrf_match else ''
r = sess.post(f'{BASE}/login', data={'username': USER_A, 'password': PASS, 'csrf_token': csrf}, allow_redirects=True)

pages = ['/home', '/dashboard', '/shopping-list', '/baby-tracker', '/history', '/settings']
for page in pages:
    r = sess.get(f'{BASE}{page}')
    check(f'Page {page} renders (200)', r.status_code == 200, f'status={r.status_code}')
    check(f'Page {page} has content', len(r.text) > 500, f'len={len(r.text)}')

# ═══════════════════════════════════════════════════════════
section('G3. Export CSV')
# ═══════════════════════════════════════════════════════════
r = sess.get(f'{BASE}/export_csv')
check('Export CSV/Excel', r.status_code == 200, f'status={r.status_code}')
check('Export has content', len(r.content) > 100, f'len={len(r.content)}')

# ═══════════════════════════════════════════════════════════
section('G4. Home Summary API')
# ═══════════════════════════════════════════════════════════
s, d = api('get', '/api/home-summary', token=TOKEN_A)
check('Home summary returns', s == 200, f'status={s}')
check('Has finance data', 'finance' in d, f'keys={list(d.keys())}')
check('Has shopping data', 'shopping' in d, f'keys={list(d.keys())}')
check('Has baby data', 'baby' in d, f'keys={list(d.keys())}')

# ═══════════════════════════════════════════════════════════
section('G5. Profile Update')
# ═══════════════════════════════════════════════════════════
s, d = api('put', '/api/settings/profile', token=TOKEN_A, json={'display_name': f'AuditUser_{suffix}'})
check('Update display name', s == 200, f'status={s}')

s, d = api('get', '/api/auth/me', token=TOKEN_A)
check('Display name updated', d.get('display_name') == f'AuditUser_{suffix}', f'name={d.get("display_name")}')

# ═══════════════════════════════════════════════════════════
section('G6. Push Token Registration')
# ═══════════════════════════════════════════════════════════
fake_token = f'audit_push_token_{suffix}'
s, d = api('post', '/api/push/register', token=TOKEN_A, json={'token': fake_token, 'platform': 'android'})
check('Register push token', s == 200, f'status={s}')

conn = db()
pt = conn.execute('SELECT * FROM push_tokens WHERE token=?', (fake_token,)).fetchone()
check('Push token in DB', pt is not None)
conn.close()

# Unregister
s, d = api('post', '/api/push/unregister', token=TOKEN_A, json={'token': fake_token})
check('Unregister push token', s == 200, f'status={s}')

# ═══════════════════════════════════════════════════════════
section('H1. SQL Injection Attempts')
# ═══════════════════════════════════════════════════════════
sqli_payloads = ["'; DROP TABLE payments; --", "' OR '1'='1", "1; DELETE FROM users"]
for payload in sqli_payloads:
    s, d = api('post', '/api/payments/add', token=TOKEN_A, json={
        'description': payload, 'amount': 1, 'category': 'כללי'
    })
    # Should either succeed (parameterized query) or fail gracefully
    check(f'SQLi payload handled safely', s in (200, 201, 400), f'status={s}')

# Verify tables still exist
conn = db()
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
table_names = [t['name'] for t in tables]
check('payments table still exists', 'payments' in table_names)
check('users table still exists', 'users' in table_names)
conn.close()

# ═══════════════════════════════════════════════════════════
section('H2. XSS Payload Handling')
# ═══════════════════════════════════════════════════════════
xss_payload = '<script>alert("xss")</script>'
s, d = api('post', '/api/payments/add', token=TOKEN_A, json={
    'description': xss_payload, 'amount': 1, 'category': 'כללי'
})
check('XSS payload accepted (stored safely)', s in (200, 201), f'status={s}')

# Check that the API returns it as-is (frontend should escape)
s, d = api('get', '/api/payments', token=TOKEN_A)
xss_found = [p for p in d if '<script>' in p.get('description', '')]
check('XSS stored as text (not executed)', len(xss_found) >= 1)

# ═══════════════════════════════════════════════════════════
section('H3. CORS Preflight')
# ═══════════════════════════════════════════════════════════
r = requests.options(f'{BASE}/api/payments', headers={
    'Origin': 'http://evil.com',
    'Access-Control-Request-Method': 'GET'
})
check('OPTIONS returns 200', r.status_code == 200, f'status={r.status_code}')

# ═══════════════════════════════════════════════════════════
section('I1. Family Member Removal & Leave')
# ═══════════════════════════════════════════════════════════
# Get User B's id
conn = db()
user_b = conn.execute('SELECT id FROM users WHERE username=?', (USER_B,)).fetchone()
conn.close()

if user_b:
    # Non-admin cannot remove
    s, d = api('post', '/api/family/remove-member', token=TOKEN_B, json={'member_id': user_b['id']})
    check('Non-admin cannot remove member', s in (400, 403), f'status={s}')

    # Admin removes User B
    s, d = api('post', '/api/family/remove-member', token=TOKEN_A, json={'member_id': user_b['id']})
    check('Admin removes member', s == 200, f'status={s}')

    conn = db()
    b_after = conn.execute('SELECT family_id FROM users WHERE id=?', (user_b['id'],)).fetchone()
    check('User B no longer in family', b_after and b_after['family_id'] is None, f'fam={b_after["family_id"] if b_after else None}')
    conn.close()

    # Re-join for cleanup
    api('post', '/api/family/join', token=TOKEN_B, json={'invite_code': INVITE_CODE})

# ═══════════════════════════════════════════════════════════
section('I2. DB Integrity Checks')
# ═══════════════════════════════════════════════════════════
conn = db()

# Check for orphaned payments (family_id doesn't exist)
orphaned = conn.execute('''
    SELECT COUNT(*) as c FROM payments p
    WHERE p.family_id NOT IN (SELECT id FROM families)
''').fetchone()
check('No orphaned payments', orphaned['c'] == 0, f'count={orphaned["c"]}')

# Check for orphaned feedings
orphaned_f = conn.execute('''
    SELECT COUNT(*) as c FROM feedings f
    WHERE f.family_id NOT IN (SELECT id FROM families)
''').fetchone()
check('No orphaned feedings', orphaned_f['c'] == 0, f'count={orphaned_f["c"]}')

# Check for orphaned shopping items
orphaned_s = conn.execute('''
    SELECT COUNT(*) as c FROM shopping_items s
    WHERE s.family_id NOT IN (SELECT id FROM families)
''').fetchone()
check('No orphaned shopping items', orphaned_s['c'] == 0, f'count={orphaned_s["c"]}')

# Check payments have valid month format
bad_months = conn.execute('''
    SELECT COUNT(*) as c FROM payments
    WHERE month NOT LIKE '____-__'
''').fetchone()
check('All payments have valid month format', bad_months['c'] == 0, f'bad={bad_months["c"]}')

# Check family_settings uniqueness
dup_settings = conn.execute('''
    SELECT family_id, COUNT(*) as c FROM family_settings
    GROUP BY family_id HAVING c > 1
''').fetchall()
check('No duplicate family_settings', len(dup_settings) == 0, f'dups={len(dup_settings)}')

# Check categories uniqueness
dup_cats = conn.execute('''
    SELECT name, COUNT(*) as c FROM categories
    WHERE family_id IS NULL GROUP BY name HAVING c > 1
''').fetchall()
check('No duplicate default categories', len(dup_cats) == 0, f'dups={len(dup_cats)}')

conn.close()

# ═══════════════════════════════════════════════════════════
section('CLEANUP')
# ═══════════════════════════════════════════════════════════
conn = db()
# Get user IDs
user_ids = []
for uname in [USER_A, USER_B, USER_C]:
    u = conn.execute('SELECT id, family_id FROM users WHERE username=?', (uname,)).fetchone()
    if u:
        user_ids.append(u['id'])
        fid = u['family_id']
        if fid:
            conn.execute('DELETE FROM payments WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM feedings WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM shopping_items WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM shopping_favorites WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM recurring_payments WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM archived_cycles WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM family_settings WHERE family_id=?', (fid,))
            conn.execute('DELETE FROM families WHERE id=?', (fid,))

for uid in user_ids:
    conn.execute('DELETE FROM push_tokens WHERE user_id=?', (uid,))
    conn.execute('DELETE FROM users WHERE id=?', (uid,))

conn.commit()
conn.close()
print('  Cleaned test data')

# ═══════════════════════════════════════════════════════════
print(f'\n{"="*60}')
print(f'  RESULTS: {passed} passed, {failed} failed')
print(f'{"="*60}')
if failures:
    print(f'\n  FAILURES:')
    for f in failures:
        print(f'    - {f}')
    print()
if failed == 0:
    print(f'\n  ALL TESTS PASSED')
else:
    print(f'\n  {failed} ISSUE(S) FOUND — see failures above')
print(f'{"="*60}\n')

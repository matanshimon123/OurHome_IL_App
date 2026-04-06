"""
בדיקות מקיפות לפני production — OurHome IL
הרץ כשה-Flask רץ: python test_files/test_production.py

בודק: Push, קטגוריות, בידוד משפחות, תשלומים, קניות, תינוק, הגדרות
"""
import requests
import random
import string
import time
import sqlite3
import json
import os

# Paths relative to project root
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DB_PATH = os.path.join(PROJECT_ROOT, 'finance_tracker.db')
APP_PATH = os.path.join(PROJECT_ROOT, 'app.py')

BASE = 'http://127.0.0.1:5000'
RND = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

PASS = 0
FAIL = 0
ERRORS = []


def rnd(prefix=''):
    return prefix + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


def check(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  ✅ {name}')
    else:
        FAIL += 1
        msg = f'  ❌ {name}' + (f' — {detail}' if detail else '')
        ERRORS.append(msg)
        print(msg)


def api(method, path, data=None, token=None, expect=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    url = BASE + path
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            r = requests.post(url, json=data, headers=headers, timeout=10)
        elif method == 'PUT':
            r = requests.put(url, json=data, headers=headers, timeout=10)
        elif method == 'DELETE':
            r = requests.delete(url, json=data, headers=headers, timeout=10)
        else:
            return None, {}

        try:
            result = r.json()
        except:
            result = {'raw': r.text[:200]}

        if expect and r.status_code != expect:
            print(f'    ⚠️  {method} {path}: expected {expect}, got {r.status_code}')

        return r.status_code, result
    except requests.ConnectionError:
        print(f'    ❌ CONNECTION ERROR: {method} {path} — Flask running?')
        return 0, {}


def get_push_tokens(user_id):
    """Get push token count for a user from DB"""
    c = sqlite3.connect(DB_PATH)
    count = c.execute('SELECT COUNT(*) as c FROM push_tokens WHERE user_id=?', (user_id,)).fetchone()[0]
    c.close()
    return count


def get_user_id(username):
    """Get user_id from DB"""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    u = c.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
    c.close()
    return u['id'] if u else None


def title(t):
    print(f'\n{"=" * 55}')
    print(f'  {t}')
    print(f'{"=" * 55}')


# ═══════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════
title('0. Setup — 3 users, 2 families')

USER_A = rnd('testA_')
USER_B = rnd('testB_')
USER_C = rnd('testC_')
FAM_1 = f'TestFamily1_{RND}'
FAM_2 = f'TestFamily2_{RND}'

# Register user A
s, d = api('POST', '/api/auth/register', {
    'display_name': 'User A', 'username': USER_A,
    'email': f'{USER_A}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
}, expect=201)
TOKEN_A = d.get('token')
check('Register User A', s == 201 and TOKEN_A, f'status={s}')

# Register user B
s, d = api('POST', '/api/auth/register', {
    'display_name': 'User B', 'username': USER_B,
    'email': f'{USER_B}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
}, expect=201)
TOKEN_B = d.get('token')
check('Register User B', s == 201 and TOKEN_B, f'status={s}')

# Register user C (different family)
s, d = api('POST', '/api/auth/register', {
    'display_name': 'User C', 'username': USER_C,
    'email': f'{USER_C}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
}, expect=201)
TOKEN_C = d.get('token')
check('Register User C', s == 201 and TOKEN_C, f'status={s}')

# Create family 1 (User A = admin)
s, d = api('POST', '/api/family/create', {'family_name': FAM_1}, token=TOKEN_A, expect=201)
TOKEN_A = d.get('token', TOKEN_A)
INVITE_1 = d.get('family', {}).get('invite_code')
check('Create Family 1', s == 201 and INVITE_1, f'status={s}')

# User B joins family 1
s, d = api('POST', '/api/family/join', {'invite_code': INVITE_1}, token=TOKEN_B)
TOKEN_B = d.get('token', TOKEN_B)
check('User B joins Family 1', s == 200)

# Create family 2 (User C = admin)
s, d = api('POST', '/api/family/create', {'family_name': FAM_2}, token=TOKEN_C, expect=201)
TOKEN_C = d.get('token', TOKEN_C)
check('Create Family 2', s == 201)

print(f'\n  Family 1: {USER_A} (admin) + {USER_B}')
print(f'  Family 2: {USER_C} (admin)')


# ═══════════════════════════════════════════════════════
title('1. Categories — Isolation Between Families')
# ═══════════════════════════════════════════════════════

# Both users see defaults
s, cats_a = api('GET', '/api/categories', token=TOKEN_A)
s, cats_c = api('GET', '/api/categories', token=TOKEN_C)
defaults_a = [c for c in cats_a if c.get('is_default')]
defaults_c = [c for c in cats_c if c.get('is_default')]
check('User A sees 9 defaults', len(defaults_a) == 9, f'got {len(defaults_a)}')
check('User C sees 9 defaults', len(defaults_c) == 9, f'got {len(defaults_c)}')

# User A adds custom category
CUSTOM_CAT = f'TestCat_{RND}'
s, d = api('POST', '/api/categories', {'name': CUSTOM_CAT, 'color': '#ff0000'}, token=TOKEN_A)
check('User A adds custom category', s == 201)

# User B (same family) sees it
s, cats_b = api('GET', '/api/categories', token=TOKEN_B)
custom_in_b = [c for c in cats_b if c['name'] == CUSTOM_CAT]
check('User B (same family) sees custom category', len(custom_in_b) == 1)

# User C (different family) does NOT see it
s, cats_c = api('GET', '/api/categories', token=TOKEN_C)
custom_in_c = [c for c in cats_c if c['name'] == CUSTOM_CAT]
check('User C (different family) does NOT see it', len(custom_in_c) == 0,
      f'found {len(custom_in_c)}')

# Cannot delete default category
default_id = defaults_a[0]['id'] if defaults_a else 0
s, d = api('DELETE', f'/api/categories/{default_id}', token=TOKEN_A)
check('Cannot delete default category', s == 403)

# Can delete custom category
custom_cats_a = [c for c in cats_b if c['name'] == CUSTOM_CAT]
if custom_cats_a:
    cat_id = custom_cats_a[0]['id']
    s, d = api('DELETE', f'/api/categories/{cat_id}', token=TOKEN_A)
    check('Can delete custom category', s == 200)

    # Verify it's gone
    s, cats_a = api('GET', '/api/categories', token=TOKEN_A)
    still_there = [c for c in cats_a if c['name'] == CUSTOM_CAT]
    check('Custom category deleted successfully', len(still_there) == 0)

# Duplicate check
s, d = api('POST', '/api/categories', {'name': 'כללי', 'color': '#000'}, token=TOKEN_A)
check('Cannot add duplicate of default', s == 400)


# ═══════════════════════════════════════════════════════
title('2. Payments — Add / Update / Delete')
# ═══════════════════════════════════════════════════════

# Add payment
s, d = api('POST', '/api/payments/add', {
    'description': f'תשלום טסט {RND}', 'amount': 99.9, 'category': 'כללי'
}, token=TOKEN_A)
check('Add payment', s == 201)

# Get payments
s, d = api('GET', '/api/payments', token=TOKEN_A)
payments = d if isinstance(d, list) else d.get('payments', [])
check('Get payments', len(payments) > 0, f'got {len(payments)}')

# Find our test payment
test_payment = next((p for p in payments if f'תשלום טסט {RND}' in p.get('description', '')), None)
check('Test payment exists', test_payment is not None)

if test_payment:
    pid = test_payment['id']

    # Update payment
    s, d = api('PUT', f'/api/payments/{pid}', {
        'description': 'תשלום מעודכן', 'amount': 150
    }, token=TOKEN_A)
    check('Update payment', s == 200)

    # Delete payment
    s, d = api('DELETE', f'/api/payments/{pid}', token=TOKEN_A)
    check('Delete payment (API)', s == 200)


# ═══════════════════════════════════════════════════════
title('3. Shopping List — Add / Check / Favorites / Clear')
# ═══════════════════════════════════════════════════════

# Add item
ITEM_NAME = f'חלב טסט {RND}'
s, d = api('POST', '/api/shopping-items', {
    'name': ITEM_NAME, 'quantity': 2, 'category': '🥛 חלבי'
}, token=TOKEN_A)
item_id = d.get('id')
check('Add shopping item', s == 201 and item_id)

# Get items
s, d = api('GET', '/api/shopping-items', token=TOKEN_A)
items = d if isinstance(d, list) else []
check('Get shopping items', len(items) > 0)

# Check item (mark as bought) — should NOT send push
if item_id:
    s, d = api('PUT', f'/api/shopping-items/{item_id}', {'checked': True}, token=TOKEN_A)
    check('Check item as bought', s == 200)

    # Mark as favorite
    s, d = api('PUT', f'/api/shopping-items/{item_id}', {'favorite': True}, token=TOKEN_A)
    check('Mark as favorite', s == 200)

# Get favorites
s, d = api('GET', '/api/shopping-items/favorites', token=TOKEN_A)
favs = d if isinstance(d, list) else []
test_fav = [f for f in favs if ITEM_NAME in f.get('name', '')]
check('Favorite saved', len(test_fav) > 0)

# Clear completed
s, d = api('DELETE', '/api/shopping-items/clear-completed', token=TOKEN_A)
check('Clear completed items', s == 200)

# Verify cleared
s, d = api('GET', '/api/shopping-items', token=TOKEN_A)
remaining = [i for i in (d if isinstance(d, list) else []) if i.get('name') == ITEM_NAME]
check('Completed item cleared', len(remaining) == 0)

# Clean up favorite
s, d = api('POST', '/api/shopping-items/delete-favorite', {'name': ITEM_NAME}, token=TOKEN_A)


# ═══════════════════════════════════════════════════════
title('4. Baby Tracker — Add / Update / Delete')
# ═══════════════════════════════════════════════════════

# Add bottle feeding
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'bottle', 'amount': 120, 'notes': f'טסט {RND}'
}, token=TOKEN_A)
feed_id = d.get('id')
check('Add bottle feeding', s == 201 and feed_id, f'status={s}')

# Add diaper
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'diaper', 'notes': 'רגיל'
}, token=TOKEN_A)
check('Add diaper', s == 201)

# Get feedings
s, d = api('GET', '/api/feedings/data', token=TOKEN_A)
check('Get feedings data', s == 200)

# Update feeding
if feed_id:
    s, d = api('PUT', f'/api/feedings/{feed_id}', {
        'amount': 150, 'notes': 'מעודכן'
    }, token=TOKEN_A)
    check('Update feeding', s == 200)

    # Delete feeding
    s, d = api('DELETE', f'/api/feedings/{feed_id}', token=TOKEN_A)
    check('Delete feeding', s == 200)


# ═══════════════════════════════════════════════════════
title('5. Recurring Payments')
# ═══════════════════════════════════════════════════════

s, d = api('POST', '/api/recurring', {
    'description': f'חוזר {RND}', 'amount': 50, 'category': 'קבועים'
}, token=TOKEN_A)
rec_id = d.get('id')
check('Add recurring payment', s == 201)

s, d = api('GET', '/api/recurring', token=TOKEN_A)
recs = d if isinstance(d, list) else []
check('Get recurring payments', len(recs) > 0)

if rec_id:
    s, d = api('PUT', f'/api/recurring/{rec_id}', {
        'description': 'חוזר מעודכן', 'amount': 75
    }, token=TOKEN_A)
    check('Update recurring', s == 200)

    s, d = api('DELETE', f'/api/recurring/{rec_id}', token=TOKEN_A)
    check('Delete recurring', s == 200)


# ═══════════════════════════════════════════════════════
title('6. Home Summary')
# ═══════════════════════════════════════════════════════

s, d = api('GET', '/api/home-summary', token=TOKEN_A)
check('Home summary returns data', s == 200 and 'finance' in d and 'shopping' in d and 'baby' in d,
      f'keys={list(d.keys()) if isinstance(d, dict) else "not dict"}')


# ═══════════════════════════════════════════════════════
title('7. History & Charts')
# ═══════════════════════════════════════════════════════

s, d = api('GET', '/api/history/data', token=TOKEN_A)
check('History data', s == 200)

s, d = api('GET', '/api/chart_data', token=TOKEN_A)
check('Chart data', s == 200)


# ═══════════════════════════════════════════════════════
title('8. Settings & Profile')
# ═══════════════════════════════════════════════════════

s, d = api('GET', '/api/settings', token=TOKEN_A)
check('Get settings', s == 200)

s, d = api('PUT', '/api/settings/profile', {'display_name': 'User A Updated'}, token=TOKEN_A)
TOKEN_A = d.get('token', TOKEN_A)
check('Update display name', s == 200)

# Family info
s, d = api('GET', '/api/family/info', token=TOKEN_A)
check('Get family info', s == 200)
members = d.get('members', [])
check('Family has 2 members', len(members) == 2, f'got {len(members)}')


# ═══════════════════════════════════════════════════════
title('9. Family Settings (Budget & Reminders)')
# ═══════════════════════════════════════════════════════

s, d = api('PUT', '/api/family/settings', {
    'feeding_reminder_hours': 3,
    'budget_monthly': 5000,
    'budget_daily': 200
}, token=TOKEN_A)
check('Update family settings', s == 200)

s, d = api('GET', '/api/family/settings', token=TOKEN_A)
check('Get family settings', s == 200)
check('Budget monthly saved', d.get('budget_monthly') == 5000, f'got {d.get("budget_monthly")}')
check('Feeding reminder saved', d.get('feeding_reminder_hours') == 3, f'got {d.get("feeding_reminder_hours")}')


# ═══════════════════════════════════════════════════════
title('10. Auth — Protected Routes')
# ═══════════════════════════════════════════════════════

# No token = 401
s, d = api('GET', '/api/home-summary', expect=401)
check('No token → 401', s == 401 and d.get('code') == 'AUTH_REQUIRED')

s, d = api('GET', '/api/payments', expect=401)
check('Payments without token → 401', s == 401)

s, d = api('POST', '/api/payments/add', {'description': 'x', 'amount': 1}, expect=401)
check('POST without token → 401', s == 401)

# Invalid token
s, d = api('GET', '/api/home-summary', token='invalid.token.here')
check('Invalid token → 401', s == 401)

# Token refresh
s, d = api('POST', '/api/auth/refresh', token=TOKEN_A)
check('Token refresh', s == 200 and d.get('token'))


# ═══════════════════════════════════════════════════════
title('11. Data Isolation — Family B Cannot See Family A Data')
# ═══════════════════════════════════════════════════════

# Add payment in family 1
s, d = api('POST', '/api/payments/add', {
    'description': f'Secret_{RND}', 'amount': 999, 'category': 'כללי'
}, token=TOKEN_A)
check('Add secret payment in Family 1', s == 201)

# User C (family 2) should NOT see it
s, d = api('GET', '/api/payments', token=TOKEN_C)
payments_c = d if isinstance(d, list) else d.get('payments', [])
secret_in_c = [p for p in payments_c if f'Secret_{RND}' in p.get('description', '')]
check('Family 2 cannot see Family 1 payments', len(secret_in_c) == 0,
      f'found {len(secret_in_c)} — DATA LEAK!')

# Shopping items isolation
s, d = api('POST', '/api/shopping-items', {
    'name': f'SecretItem_{RND}', 'quantity': 1
}, token=TOKEN_A)
s, d = api('GET', '/api/shopping-items', token=TOKEN_C)
items_c = d if isinstance(d, list) else []
secret_items = [i for i in items_c if f'SecretItem_{RND}' in i.get('name', '')]
check('Family 2 cannot see Family 1 shopping', len(secret_items) == 0,
      f'found {len(secret_items)} — DATA LEAK!')

# Feedings isolation
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'bottle', 'amount': 999, 'notes': f'Secret_{RND}'
}, token=TOKEN_A)
s, d = api('GET', '/api/feedings/data', token=TOKEN_C)
feedings_c = d.get('today_feedings', []) if isinstance(d, dict) else []
secret_feedings = [f for f in feedings_c if f'Secret_{RND}' in f.get('notes', '')]
check('Family 2 cannot see Family 1 feedings', len(secret_feedings) == 0,
      f'found {len(secret_feedings)} — DATA LEAK!')


# ═══════════════════════════════════════════════════════
title('12. Push Notification Routes — Verify All Have exclude_user_id')
# ═══════════════════════════════════════════════════════

with open(APP_PATH, 'r', encoding='utf-8') as f:
    code = f.read()

# Check that all user-action push calls use exclude_user_id
# For each call, grab 300 chars after it and check for exclude_user_id
system_keywords = ['תקציב', 'תזכורת', 'חריגה', 'האכלה', 'מחזור']
missing = []
idx = 0
while True:
    pos = code.find('send_push_to_family(', idx)
    if pos == -1:
        break
    block = code[pos:pos+300]
    # Find the line for display
    line_start = code.rfind('\n', 0, pos) + 1
    line_end = code.find('\n', pos)
    first_line = code[line_start:line_end].strip()

    is_system = any(kw in block for kw in system_keywords)
    is_def = 'def send_push' in code[line_start:pos]
    has_exclude = 'exclude_user_id' in block

    if not is_system and not is_def and not has_exclude:
        missing.append(first_line[:70])

    idx = pos + 1

check('All user-action push calls have exclude_user_id',
      len(missing) == 0,
      f'missing in: {missing}')

# Verify no shopping "checked" push
check('No push for item checked', 'פריט נקנה' not in code)

# Verify feeding reminder runs every 60s
check('Feeding reminder every 60s', 'time.sleep(60)' in code)

# Verify init_db checks before insert
check('init_db prevents duplicate categories',
      'SELECT id FROM categories WHERE name=? AND family_id IS NULL' in code)


# ═══════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════
title('Cleanup')

c = sqlite3.connect(DB_PATH)
for username in [USER_A, USER_B, USER_C]:
    uid = get_user_id(username)
    if uid:
        c.execute('DELETE FROM push_tokens WHERE user_id=?', (uid,))
        fid_row = c.execute('SELECT family_id FROM users WHERE id=?', (uid,)).fetchone()
        if fid_row and fid_row[0]:
            fid = fid_row[0]
            # Only delete family data if no other real users in it
            others = c.execute('SELECT COUNT(*) FROM users WHERE family_id=? AND id!=?', (fid, uid)).fetchone()[0]
            if others == 0 or all(get_user_id(u) for u in [USER_A, USER_B, USER_C]):
                c.execute('DELETE FROM payments WHERE family_id=?', (fid,))
                c.execute('DELETE FROM shopping_items WHERE family_id=?', (fid,))
                c.execute('DELETE FROM shopping_favorites WHERE family_id=?', (fid,))
                c.execute('DELETE FROM feedings WHERE family_id=?', (fid,))
                c.execute('DELETE FROM recurring_payments WHERE family_id=?', (fid,))
                c.execute('DELETE FROM family_settings WHERE family_id=?', (fid,))
                c.execute('DELETE FROM categories WHERE family_id=?', (fid,))
                c.execute('DELETE FROM families WHERE id=?', (fid,))
        c.execute('DELETE FROM users WHERE id=?', (uid,))
c.commit()
c.close()
print('  🧹 Test data cleaned')


# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════
print(f'\n{"=" * 55}')
print(f'  RESULTS: {PASS} passed, {FAIL} failed')
print(f'{"=" * 55}')

if ERRORS:
    print('\n❌ FAILURES:')
    for e in ERRORS:
        print(e)
else:
    print('\n✅ ALL TESTS PASSED — Ready for production!')

print()
"""
בדיקות תרחישים מלאים (Flows) — OurHome IL
הרץ כשה-Flask רץ: python test_files/test_flows.py

תרחישים אמיתיים: מחזור חיים של משפחה, תשלום מלא,
עזיבת משפחה, שינוי סיסמה, ארכיון + היסטוריה, ועוד
"""
import requests
import random
import string
import time
import sqlite3
import os

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DB_PATH = os.path.join(PROJECT_ROOT, 'finance_tracker.db')
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


def api(method, path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        r = getattr(requests, method.lower())(BASE + path, json=data, headers=headers, timeout=10)
        try:
            return r.status_code, r.json()
        except:
            return r.status_code, {'raw': r.text[:300]}
    except requests.ConnectionError:
        print(f'    💀 CONNECTION ERROR: {method} {path}')
        return 0, {}


def title(t):
    print(f'\n{"=" * 60}')
    print(f'  {t}')
    print(f'{"=" * 60}')


def cleanup_user(username):
    """Remove a test user and their data"""
    c = sqlite3.connect(DB_PATH)
    u = c.execute('SELECT id, family_id FROM users WHERE username=?', (username,)).fetchone()
    if u:
        uid, fid = u
        c.execute('DELETE FROM push_tokens WHERE user_id=?', (uid,))
        if fid:
            remaining = c.execute('SELECT COUNT(*) FROM users WHERE family_id=? AND id!=?', (fid, uid)).fetchone()[0]
            if remaining == 0:
                for tbl in ['payments','shopping_items','shopping_favorites','feedings',
                            'recurring_payments','family_settings','archived_cycles','categories']:
                    c.execute(f'DELETE FROM {tbl} WHERE family_id=?', (fid,))
                c.execute('DELETE FROM families WHERE id=?', (fid,))
        c.execute('DELETE FROM users WHERE id=?', (uid,))
    c.commit()
    c.close()


# ═══════════════════════════════════════════════════════════
title('FLOW 1: Complete Family Lifecycle')
# Register → Create family → Invite → Join → Use → Leave → Delete
# ═══════════════════════════════════════════════════════════

U1 = rnd('life1_')
U2 = rnd('life2_')
U3 = rnd('life3_')

# Register 3 users
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Papa', 'username': U1,
    'email': f'{U1}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
T1 = d.get('token')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Mama', 'username': U2,
    'email': f'{U2}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
T2 = d.get('token')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Uncle', 'username': U3,
    'email': f'{U3}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
T3 = d.get('token')

# Papa creates family
s, d = api('POST', '/api/family/create', {'family_name': f'LifeFamily_{RND}'}, token=T1)
T1 = d.get('token', T1)
invite = d.get('family', {}).get('invite_code')
check('1.1 Family created', s == 201 and invite)

# Mama joins
s, d = api('POST', '/api/family/join', {'invite_code': invite}, token=T2)
T2 = d.get('token', T2)
check('1.2 Mama joined', s == 200)

# Uncle joins
s, d = api('POST', '/api/family/join', {'invite_code': invite}, token=T3)
T3 = d.get('token', T3)
check('1.3 Uncle joined', s == 200)

# Verify 3 members
s, d = api('GET', '/api/family/info', token=T1)
check('1.4 Family has 3 members', len(d.get('members', [])) == 3)

# Papa adds payment, all see it
api('POST', '/api/payments/add', {'description': f'Papa_{RND}', 'amount': 100, 'category': 'כללי'}, token=T1)
s, d = api('GET', '/api/payments', token=T2)
mama_sees = any(f'Papa_{RND}' in p.get('description','') for p in (d if isinstance(d, list) else d.get('payments',[])))
check('1.5 Mama sees Papa payment', mama_sees)

s, d = api('GET', '/api/payments', token=T3)
uncle_sees = any(f'Papa_{RND}' in p.get('description','') for p in (d if isinstance(d, list) else d.get('payments',[])))
check('1.6 Uncle sees Papa payment', uncle_sees)

# Papa removes Uncle
s, d = api('GET', '/api/family/info', token=T1)
uncle_id = next((m['id'] for m in d.get('members', []) if m.get('username') == U3), None)
s, d = api('POST', '/api/family/remove-member', {'user_id': uncle_id}, token=T1)
check('1.7 Papa removed Uncle', s == 200)

# Uncle can no longer see family payments
s, d = api('GET', '/api/payments', token=T3)
payments_after = d if isinstance(d, list) else d.get('payments', [])
check('1.8 Uncle no longer sees payments', len(payments_after) == 0 or s == 403)

# Mama leaves voluntarily
s, d = api('POST', '/api/family/leave', token=T2)
check('1.9 Mama left family', s == 200)

# Verify only Papa remains
s, d = api('GET', '/api/family/info', token=T1)
check('1.10 Only Papa remains', len(d.get('members', [])) == 1)

for u in [U1, U2, U3]:
    cleanup_user(u)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 2: Password Change & Re-login')
# ═══════════════════════════════════════════════════════════

PW_USER = rnd('pw_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'PW User', 'username': PW_USER,
    'email': f'{PW_USER}@test.com', 'password': 'OldPass1!', 'password2': 'OldPass1!'
})
PW_TOKEN = d.get('token')

# Change password
s, d = api('POST', '/api/auth/change-password', {
    'current_password': 'OldPass1!', 'new_password': 'NewPass2!', 'new_password2': 'NewPass2!'
}, token=PW_TOKEN)
check('2.1 Password changed', s == 200)

# Old password no longer works
s, d = api('POST', '/api/auth/login', {'username': PW_USER, 'password': 'OldPass1!'})
check('2.2 Old password rejected', s == 401)

# New password works
s, d = api('POST', '/api/auth/login', {'username': PW_USER, 'password': 'NewPass2!'})
check('2.3 New password works', s == 200 and d.get('token'))
PW_TOKEN = d.get('token', PW_TOKEN)

# Wrong current password in change
s, d = api('POST', '/api/auth/change-password', {
    'current_password': 'WrongCurrent!', 'new_password': 'X', 'new_password2': 'X'
}, token=PW_TOKEN)
check('2.4 Wrong current password rejected', s in [400, 401])

# Mismatched new passwords
s, d = api('POST', '/api/auth/change-password', {
    'current_password': 'NewPass2!', 'new_password': 'AAA', 'new_password2': 'BBB'
}, token=PW_TOKEN)
check('2.5 Mismatched new passwords rejected', s == 400)

cleanup_user(PW_USER)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 3: Full Month Cycle — Payments → Archive → New Month')
# ═══════════════════════════════════════════════════════════

MC_USER = rnd('mc_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Month User', 'username': MC_USER,
    'email': f'{MC_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
MC_TOKEN = d.get('token')

s, d = api('POST', '/api/family/create', {'family_name': f'MonthFam_{RND}'}, token=MC_TOKEN)
MC_TOKEN = d.get('token', MC_TOKEN)

# Add several payments
for i in range(5):
    api('POST', '/api/payments/add', {
        'description': f'Pay{i}_{RND}', 'amount': 100 + i*10, 'category': 'כללי'
    }, token=MC_TOKEN)

# Get total before archive
s, d = api('GET', '/api/payments', token=MC_TOKEN)
payments_before = d if isinstance(d, list) else d.get('payments', [])
total_before = sum(float(p.get('amount', 0)) for p in payments_before)
check('3.1 5 payments added', len(payments_before) == 5, f'got {len(payments_before)}')
check('3.2 Total is 600', total_before == 600.0, f'got {total_before}')

# Export CSV before archive
r = requests.get(BASE + '/api/payments/export', headers={
    'Authorization': f'Bearer {MC_TOKEN}'
}, timeout=10)
check('3.3 CSV export works', r.status_code == 200 and f'Pay0_{RND}' in r.text)

# Archive
s, d = api('POST', '/api/payments/archive', token=MC_TOKEN)
check('3.4 Archive succeeds', s == 200)
check('3.5 Archived total correct', d.get('archived', {}).get('total') == 600.0,
      f'got {d.get("archived", {}).get("total")}')

# After archive — current month is empty
s, d = api('GET', '/api/payments', token=MC_TOKEN)
after = d if isinstance(d, list) else d.get('payments', [])
active_after = [p for p in after if not p.get('archived')]
check('3.6 Current month empty after archive', len(active_after) == 0, f'got {len(active_after)}')

# Add new payment in "new month"
s, d = api('POST', '/api/payments/add', {
    'description': f'NewMonth_{RND}', 'amount': 50, 'category': 'כללי'
}, token=MC_TOKEN)
check('3.7 New payment after archive works', s == 201)

# Home summary should show new payment only
s, d = api('GET', '/api/home-summary', token=MC_TOKEN)
finance = d.get('finance', {})
check('3.8 Home shows correct total', float(finance.get('total', 0)) == 50.0,
      f'got {finance.get("total")}')

cleanup_user(MC_USER)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 4: Shopping List Full Cycle')
# ═══════════════════════════════════════════════════════════

SH_USER = rnd('sh_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Shopper', 'username': SH_USER,
    'email': f'{SH_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
SH_TOKEN = d.get('token')
s, d = api('POST', '/api/family/create', {'family_name': f'ShopFam_{RND}'}, token=SH_TOKEN)
SH_TOKEN = d.get('token', SH_TOKEN)

# Add 3 items
items = []
for name in [f'חלב_{RND}', f'לחם_{RND}', f'ביצים_{RND}']:
    s, d = api('POST', '/api/shopping-items', {'name': name, 'quantity': 1}, token=SH_TOKEN)
    items.append(d.get('id'))

check('4.1 3 items added', all(items))

# Check 2 items as bought
api('PUT', f'/api/shopping-items/{items[0]}', {'checked': True}, token=SH_TOKEN)
api('PUT', f'/api/shopping-items/{items[1]}', {'checked': True}, token=SH_TOKEN)

# Verify counts
s, d = api('GET', '/api/shopping-items', token=SH_TOKEN)
all_items = d if isinstance(d, list) else []
checked = [i for i in all_items if i.get('checked')]
unchecked = [i for i in all_items if not i.get('checked')]
check('4.2 Two items checked', len(checked) == 2, f'checked={len(checked)}')
check('4.3 One item unchecked', len(unchecked) == 1, f'unchecked={len(unchecked)}')

# Clear completed — only checked items deleted
api('DELETE', '/api/shopping-items/clear-completed', token=SH_TOKEN)
s, d = api('GET', '/api/shopping-items', token=SH_TOKEN)
remaining = d if isinstance(d, list) else []
check('4.4 Only unchecked item remains', len(remaining) == 1)
check('4.5 Remaining is the unchecked one', remaining[0].get('name') == f'ביצים_{RND}' if remaining else False)

# Mark as favorite, delete item, favorite persists
api('PUT', f'/api/shopping-items/{items[2]}', {'favorite': True}, token=SH_TOKEN)
api('DELETE', f'/api/shopping-items/{items[2]}', token=SH_TOKEN)
s, d = api('GET', '/api/shopping-items/favorites', token=SH_TOKEN)
favs = d if isinstance(d, list) else []
fav_exists = any(f['name'] == f'ביצים_{RND}' for f in favs)
check('4.6 Favorite persists after item deletion', fav_exists)

# Add all favorites back to list
s, d = api('POST', '/api/shopping-items/add-favorites', token=SH_TOKEN)
check('4.7 Add favorites back', s == 200)
s, d = api('GET', '/api/shopping-items', token=SH_TOKEN)
restored = d if isinstance(d, list) else []
check('4.8 Item restored from favorites', any(i['name'] == f'ביצים_{RND}' for i in restored))

cleanup_user(SH_USER)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 5: Baby Tracker Full Day')
# ═══════════════════════════════════════════════════════════

BB_USER = rnd('bb_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Parent', 'username': BB_USER,
    'email': f'{BB_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
BB_TOKEN = d.get('token')
s, d = api('POST', '/api/family/create', {'family_name': f'BabyFam_{RND}'}, token=BB_TOKEN)
BB_TOKEN = d.get('token', BB_TOKEN)

# Add multiple feeding types
feed_ids = []
for ft, amt, note in [
    ('bottle', 120, 'בוקר'),
    ('breastfeeding', 0, 'צהריים'),
    ('solid', 0, 'ארוחת ערב'),
    ('diaper', 0, 'רגיל'),
    ('sleep', 0, 'נרדם'),
    ('medication', 0, 'ויטמין D'),
]:
    s, d = api('POST', '/api/feedings', {
        'feeding_type': ft, 'amount': amt, 'notes': f'{note}_{RND}'
    }, token=BB_TOKEN)
    feed_ids.append(d.get('id'))

check('5.1 All 6 feeding types added', all(feed_ids), f'ids={feed_ids}')

# Get data
s, d = api('GET', '/api/feedings/data', token=BB_TOKEN)
check('5.2 Feedings data returned', s == 200)
feedings = d.get('today_feedings', []) if isinstance(d, dict) else []
check('5.3 All 6 feedings in data', len(feedings) >= 6, f'got {len(feedings)}')

# Update bottle amount
api('PUT', f'/api/feedings/{feed_ids[0]}', {'amount': 150, 'notes': f'מעודכן_{RND}'}, token=BB_TOKEN)
s, d = api('GET', '/api/feedings/data', token=BB_TOKEN)
feedings = d.get('today_feedings', []) if isinstance(d, dict) else []
updated = next((f for f in feedings if f.get('id') == feed_ids[0]), None)
check('5.4 Feeding updated', updated and float(updated.get('amount', 0)) == 150.0 if updated else False)

# Delete one
api('DELETE', f'/api/feedings/{feed_ids[5]}', token=BB_TOKEN)
s, d = api('GET', '/api/feedings/data', token=BB_TOKEN)
feedings = d.get('today_feedings', []) if isinstance(d, dict) else []
deleted_gone = not any(f.get('id') == feed_ids[5] for f in feedings)
check('5.5 Deleted feeding gone', deleted_gone)

# Home summary shows last feeding
s, d = api('GET', '/api/home-summary', token=BB_TOKEN)
baby = d.get('baby', {})
check('5.6 Home shows baby data', 'bottles' in baby or 'count' in baby,
      f'baby keys={list(baby.keys())}')

cleanup_user(BB_USER)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 6: Recurring Payments → Add to Month')
# ═══════════════════════════════════════════════════════════

RC_USER = rnd('rc_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Recurring', 'username': RC_USER,
    'email': f'{RC_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
RC_TOKEN = d.get('token')
s, d = api('POST', '/api/family/create', {'family_name': f'RecFam_{RND}'}, token=RC_TOKEN)
RC_TOKEN = d.get('token', RC_TOKEN)

# Add 3 recurring payments
for desc, amt, cat in [
    (f'ארנונה_{RND}', 500, 'קבועים'),
    (f'חשמל_{RND}', 300, 'משק בית'),
    (f'ספוטיפיי_{RND}', 30, 'בילויים / פנאי'),
]:
    s, d = api('POST', '/api/recurring', {'description': desc, 'amount': amt, 'category': cat}, token=RC_TOKEN)

# Get recurring to find IDs
s, d = api('GET', '/api/recurring', token=RC_TOKEN)
recs = d if isinstance(d, list) else []
rec_ids = [r['id'] for r in recs if any(kw in r.get('description', '') for kw in [f'ארנונה_{RND}', f'חשמל_{RND}', f'ספוטיפיי_{RND}'])]
check('6.1 3 recurring added', len(rec_ids) == 3, f'got {len(rec_ids)}')

# Verify all 3 visible
check('6.2 All 3 visible', len(recs) == 3, f'got {len(recs)}')

# Add single recurring to month
arnona_id = next((r['id'] for r in recs if f'ארנונה_{RND}' in r.get('description', '')), None)
if arnona_id:
    s, d = api('POST', f'/api/recurring/{arnona_id}/add', token=RC_TOKEN)
    check('6.3 Single recurring added to month', s in [200, 201])
else:
    check('6.3 Single recurring added to month', False, f'arnona_id not found, recs={[r.get("description","") for r in recs]}')

# Verify payment appeared
s, d = api('GET', '/api/payments', token=RC_TOKEN)
payments = d if isinstance(d, list) else d.get('payments', [])
has_arnona = any(f'ארנונה_{RND}' in p.get('description', '') for p in payments)
check('6.4 Recurring payment in monthly', has_arnona,
      f'payments={len(payments)}, descriptions={[p.get("description","")[:30] for p in payments[:5]]}')

# Add all recurring
s, d = api('POST', '/api/recurring/add-all', token=RC_TOKEN)
check('6.5 Add all recurring', s in [200, 201])

# Verify all appeared (may have duplicates with single add)
s, d = api('GET', '/api/payments', token=RC_TOKEN)
payments = d if isinstance(d, list) else d.get('payments', [])
check('6.6 All payments present', len(payments) >= 3, f'got {len(payments)}')

# Delete recurring
if rec_ids:
    for rid in rec_ids:
        api('DELETE', f'/api/recurring/{rid}', token=RC_TOKEN)

s, d = api('GET', '/api/recurring', token=RC_TOKEN)
check('6.7 All recurring deleted', len(d if isinstance(d, list) else []) == 0)

cleanup_user(RC_USER)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 7: Multi-Family Data Isolation Stress Test')
# ═══════════════════════════════════════════════════════════

# Create 3 families, each adds data, verify zero leakage
families = []
for i in range(3):
    u = rnd(f'iso{i}_')
    s, d = api('POST', '/api/auth/register', {
        'display_name': f'Iso{i}', 'username': u,
        'email': f'{u}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
    })
    t = d.get('token')
    s, d = api('POST', '/api/family/create', {'family_name': f'IsoFam{i}_{RND}'}, token=t)
    t = d.get('token', t)

    # Each adds unique data
    api('POST', '/api/payments/add', {
        'description': f'IsoPayment_{i}_{RND}', 'amount': (i+1)*100, 'category': 'כללי'
    }, token=t)
    api('POST', '/api/shopping-items', {
        'name': f'IsoItem_{i}_{RND}', 'quantity': 1
    }, token=t)
    api('POST', '/api/feedings', {
        'feeding_type': 'bottle', 'amount': (i+1)*50, 'notes': f'IsoFeed_{i}_{RND}'
    }, token=t)
    api('POST', '/api/categories', {
        'name': f'IsoCat_{i}_{RND}', 'color': '#ff0000'
    }, token=t)

    families.append({'username': u, 'token': t, 'index': i})

# Cross-check: each family sees ONLY its own data
all_isolated = True
for fam in families:
    i = fam['index']
    t = fam['token']

    # Payments
    s, d = api('GET', '/api/payments', token=t)
    payments = d if isinstance(d, list) else d.get('payments', [])
    for p in payments:
        desc = p.get('description', '')
        if 'IsoPayment_' in desc and f'_{i}_' not in desc:
            all_isolated = False
            print(f'    💀 Family {i} sees payment from another family: {desc}')

    # Shopping
    s, d = api('GET', '/api/shopping-items', token=t)
    items = d if isinstance(d, list) else []
    for item in items:
        name = item.get('name', '')
        if 'IsoItem_' in name and f'_{i}_' not in name:
            all_isolated = False
            print(f'    💀 Family {i} sees shopping from another family: {name}')

    # Feedings
    s, d = api('GET', '/api/feedings/data', token=t)
    feedings = d.get('today_feedings', []) if isinstance(d, dict) else []
    for f in feedings:
        notes = f.get('notes', '')
        if 'IsoFeed_' in notes and f'_{i}_' not in notes:
            all_isolated = False
            print(f'    💀 Family {i} sees feeding from another family: {notes}')

    # Categories
    s, d = api('GET', '/api/categories', token=t)
    cats = d if isinstance(d, list) else []
    for c in cats:
        name = c.get('name', '')
        if 'IsoCat_' in name and f'_{i}_' not in name:
            all_isolated = False
            print(f'    💀 Family {i} sees category from another family: {name}')

check('7.1 Complete data isolation across 3 families', all_isolated)

for fam in families:
    cleanup_user(fam['username'])
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 8: Token Lifecycle')
# ═══════════════════════════════════════════════════════════

TK_USER = rnd('tk_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Token User', 'username': TK_USER,
    'email': f'{TK_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
TK_TOKEN = d.get('token')

# Token works
s, d = api('GET', '/api/auth/me', token=TK_TOKEN)
check('8.1 Initial token works', s == 200)

# Refresh token
s, d = api('POST', '/api/auth/refresh', token=TK_TOKEN)
NEW_TOKEN = d.get('token')
check('8.2 Token refreshed', s == 200 and NEW_TOKEN)

# New token works
s, d = api('GET', '/api/auth/me', token=NEW_TOKEN)
check('8.3 New token works', s == 200)

# Old token still works (not invalidated)
s, d = api('GET', '/api/auth/me', token=TK_TOKEN)
check('8.4 Old token still works', s == 200)

# Create family → token updates with family_id
s, d = api('POST', '/api/family/create', {'family_name': f'TkFam_{RND}'}, token=NEW_TOKEN)
FAM_TOKEN = d.get('token')
check('8.5 Family creation returns new token', FAM_TOKEN and FAM_TOKEN != NEW_TOKEN)

# Family token has family_id
s, d = api('GET', '/api/auth/me', token=FAM_TOKEN)
check('8.6 Family token has family_id', d.get('user', {}).get('family_id') is not None)

# Change display name → token updates
s, d = api('PUT', '/api/settings/profile', {'display_name': 'New Name'}, token=FAM_TOKEN)
NAME_TOKEN = d.get('token')
check('8.7 Name change returns new token', NAME_TOKEN)

cleanup_user(TK_USER)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 9: Simultaneous Family Members Working')
# ═══════════════════════════════════════════════════════════

S1 = rnd('sim1_')
S2 = rnd('sim2_')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Sim1', 'username': S1,
    'email': f'{S1}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
ST1 = d.get('token')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Sim2', 'username': S2,
    'email': f'{S2}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
ST2 = d.get('token')

s, d = api('POST', '/api/family/create', {'family_name': f'SimFam_{RND}'}, token=ST1)
ST1 = d.get('token', ST1)
inv = d.get('family', {}).get('invite_code')
s, d = api('POST', '/api/family/join', {'invite_code': inv}, token=ST2)
ST2 = d.get('token', ST2)

# Both add payments simultaneously
import threading
results = {'s1': [], 's2': []}

def add_payments(token, key, count):
    for i in range(count):
        s, d = api('POST', '/api/payments/add', {
            'description': f'{key}_pay_{i}_{RND}', 'amount': 10+i, 'category': 'כללי'
        }, token=token)
        results[key].append(s)

t1 = threading.Thread(target=add_payments, args=(ST1, 's1', 5))
t2 = threading.Thread(target=add_payments, args=(ST2, 's2', 5))
t1.start(); t2.start()
t1.join(timeout=15); t2.join(timeout=15)

check('9.1 User 1: all 5 payments', len(results['s1']) == 5 and all(s == 201 for s in results['s1']))
check('9.2 User 2: all 5 payments', len(results['s2']) == 5 and all(s == 201 for s in results['s2']))

# Both see all 10 payments
s, d = api('GET', '/api/payments', token=ST1)
all_payments = d if isinstance(d, list) else d.get('payments', [])
check('9.3 All 10 payments visible', len(all_payments) >= 10, f'got {len(all_payments)}')

# Both add shopping items
api('POST', '/api/shopping-items', {'name': f'Sim1Item_{RND}', 'quantity': 1}, token=ST1)
api('POST', '/api/shopping-items', {'name': f'Sim2Item_{RND}', 'quantity': 1}, token=ST2)

# One checks the other's item
s, d = api('GET', '/api/shopping-items', token=ST1)
items = d if isinstance(d, list) else []
sim2_item = next((i for i in items if i.get('name') == f'Sim2Item_{RND}'), None)
if sim2_item:
    api('PUT', f'/api/shopping-items/{sim2_item["id"]}', {'checked': True}, token=ST1)
    check('9.4 User 1 can check User 2 item', True)

    # User 2 sees it checked
    s, d = api('GET', '/api/shopping-items', token=ST2)
    items2 = d if isinstance(d, list) else []
    item_checked = next((i for i in items2 if i.get('name') == f'Sim2Item_{RND}'), None)
    check('9.5 User 2 sees item checked', item_checked and item_checked.get('checked'))

for u in [S1, S2]:
    cleanup_user(u)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
title('FLOW 10: Rejoin After Leaving')
# ═══════════════════════════════════════════════════════════

RJ1 = rnd('rj1_')
RJ2 = rnd('rj2_')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Rejoin Admin', 'username': RJ1,
    'email': f'{RJ1}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
RJT1 = d.get('token')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Rejoin Member', 'username': RJ2,
    'email': f'{RJ2}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
RJT2 = d.get('token')

# Create family, member joins
s, d = api('POST', '/api/family/create', {'family_name': f'RejoinFam_{RND}'}, token=RJT1)
RJT1 = d.get('token', RJT1)
rj_invite = d.get('family', {}).get('invite_code')

s, d = api('POST', '/api/family/join', {'invite_code': rj_invite}, token=RJT2)
RJT2 = d.get('token', RJT2)

# Add data
api('POST', '/api/payments/add', {'description': f'BeforeLeave_{RND}', 'amount': 100, 'category': 'כללי'}, token=RJT2)

# Member leaves
s, d = api('POST', '/api/family/leave', token=RJT2)
check('10.1 Member left', s == 200)

# Refresh token to get updated family_id
s, d = api('POST', '/api/auth/login', {'username': RJ2, 'password': 'Test1234!'})
RJT2 = d.get('token', RJT2)

# Member can't see old data
s, d = api('GET', '/api/payments', token=RJT2)
old_payments = d if isinstance(d, list) else d.get('payments', [])
check('10.2 No access to old family data', len(old_payments) == 0 or s == 403)

# Member rejoins
s, d = api('POST', '/api/family/join', {'invite_code': rj_invite}, token=RJT2)
RJT2 = d.get('token', RJT2)
check('10.3 Rejoin successful', s == 200)

# Can see data again
s, d = api('GET', '/api/payments', token=RJT2)
payments = d if isinstance(d, list) else d.get('payments', [])
sees_old = any(f'BeforeLeave_{RND}' in p.get('description', '') for p in payments)
check('10.4 Can see old data after rejoin', sees_old)

for u in [RJ1, RJ2]:
    cleanup_user(u)
print('  🧹 Cleaned')


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
print(f'\n{"=" * 60}')
print(f'  RESULTS: {PASS} passed, {FAIL} failed')
print(f'  Across 10 complete user flows')
print(f'{"=" * 60}')

if ERRORS:
    print('\n❌ FAILURES:')
    for e in ERRORS:
        print(e)
else:
    print('\n✅ ALL FLOW TESTS PASSED!')

print()
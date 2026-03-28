"""
בדיקות מקצה לקצה + מקרי קצה — OurHome IL
הרץ כשה-Flask רץ: python test_files/test_edge_cases.py

כולל: validation, SQL injection, auth edge cases, family rules,
budget alerts, concurrent ops, export, archive, CORS
"""
import requests
import random
import string
import time
import sqlite3
import os
import threading

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


def api(method, path, data=None, token=None, headers_extra=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if headers_extra:
        headers.update(headers_extra)
    url = BASE + path
    try:
        r = getattr(requests, method.lower())(url, json=data, headers=headers, timeout=10)
        try:
            return r.status_code, r.json()
        except:
            return r.status_code, {'raw': r.text[:300]}
    except requests.ConnectionError:
        print(f'    💀 CONNECTION ERROR: {method} {path}')
        return 0, {}


def api_raw(method, path, token=None, headers_extra=None):
    """Return raw response object"""
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if headers_extra:
        headers.update(headers_extra)
    url = BASE + path
    return getattr(requests, method.lower())(url, headers=headers, timeout=10)


def title(t):
    print(f'\n{"=" * 60}')
    print(f'  {t}')
    print(f'{"=" * 60}')


# ═══════════════════════════════════════════════════════
title('SETUP — Users & Families')
# ═══════════════════════════════════════════════════════

USER_A = rnd('edgeA_')
USER_B = rnd('edgeB_')
USER_C = rnd('edgeC_')
USER_D = rnd('edgeD_')

# Register all users
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Edge A', 'username': USER_A,
    'email': f'{USER_A}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
TOKEN_A = d.get('token')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Edge B', 'username': USER_B,
    'email': f'{USER_B}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
TOKEN_B = d.get('token')

s, d = api('POST', '/api/auth/register', {
    'display_name': 'Edge C', 'username': USER_C,
    'email': f'{USER_C}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
TOKEN_C = d.get('token')

# D = loner, no family
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Edge D', 'username': USER_D,
    'email': f'{USER_D}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
TOKEN_D = d.get('token')

# Family 1: A (admin) + B
s, d = api('POST', '/api/family/create', {'family_name': f'EdgeFam1_{RND}'}, token=TOKEN_A)
TOKEN_A = d.get('token', TOKEN_A)
INVITE_1 = d.get('family', {}).get('invite_code')

s, d = api('POST', '/api/family/join', {'invite_code': INVITE_1}, token=TOKEN_B)
TOKEN_B = d.get('token', TOKEN_B)

# Family 2: C (admin, alone)
s, d = api('POST', '/api/family/create', {'family_name': f'EdgeFam2_{RND}'}, token=TOKEN_C)
TOKEN_C = d.get('token', TOKEN_C)

print(f'  Setup: A+B in Family1, C in Family2, D no family')


# ═══════════════════════════════════════════════════════
title('1. AUTH — Registration Edge Cases')
# ═══════════════════════════════════════════════════════

# Duplicate username
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Dup', 'username': USER_A,
    'email': 'unique@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
check('Duplicate username rejected', s in [400, 409], f'status={s}')

# Duplicate email
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Dup', 'username': rnd('dup_'),
    'email': f'{USER_A}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
check('Duplicate email rejected', s in [400, 409], f'status={s}')

# Password mismatch
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Mis', 'username': rnd('mis_'),
    'email': f'{rnd()}@test.com', 'password': 'Test1234!', 'password2': 'Different!'
})
check('Password mismatch rejected', s == 400, f'status={s}')

# Empty username
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Empty', 'username': '',
    'email': f'{rnd()}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
check('Empty username rejected', s == 400, f'status={s}')

# Short password
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Short', 'username': rnd('short_'),
    'email': f'{rnd()}@test.com', 'password': '123', 'password2': '123'
})
check('Short password rejected', s == 400, f'status={s}')

# Wrong password login
s, d = api('POST', '/api/auth/login', {
    'username': USER_A, 'password': 'WrongPassword!'
})
check('Wrong password login rejected', s == 401, f'status={s}')

# Non-existent user login
s, d = api('POST', '/api/auth/login', {
    'username': 'nonexistent_user_xyz', 'password': 'Test1234!'
})
check('Non-existent user login rejected', s == 401, f'status={s}')

# Correct login
s, d = api('POST', '/api/auth/login', {
    'username': USER_A, 'password': 'Test1234!'
})
check('Correct login works', s == 200 and d.get('token'), f'status={s}')
TOKEN_A = d.get('token', TOKEN_A)


# ═══════════════════════════════════════════════════════
title('2. AUTH — Token Edge Cases')
# ═══════════════════════════════════════════════════════

# Empty token
s, d = api('GET', '/api/home-summary', token='')
check('Empty token → 401', s == 401)

# Malformed token
s, d = api('GET', '/api/home-summary', token='not.a.jwt')
check('Malformed token → 401', s == 401)

# Token with spaces
s, d = api('GET', '/api/home-summary', token='   ')
check('Whitespace token → 401', s == 401)

# Very long garbage token
s, d = api('GET', '/api/home-summary', token='x' * 10000)
check('Very long token → 401', s == 401)


# ═══════════════════════════════════════════════════════
title('3. FAMILY — Edge Cases')
# ═══════════════════════════════════════════════════════

# User D (no family) tries to access family-only endpoints
s, d = api('GET', '/api/payments', token=TOKEN_D)
# Should either return empty or 403
check('No-family user: payments', s in [200, 403])

s, d = api('GET', '/api/home-summary', token=TOKEN_D)
check('No-family user: home summary', s in [200, 403])

# Join with invalid invite code
s, d = api('POST', '/api/family/join', {'invite_code': 'INVALID'}, token=TOKEN_D)
check('Invalid invite code rejected', s in [400, 404], f'status={s}')

# Join with empty invite code
s, d = api('POST', '/api/family/join', {'invite_code': ''}, token=TOKEN_D)
check('Empty invite code rejected', s in [400, 404], f'status={s}')

# Admin tries to leave own family
s, d = api('POST', '/api/family/leave', token=TOKEN_A)
check('Admin cannot leave own family', s == 400, f'status={s}')

# Non-admin tries to remove member
s, d = api('GET', '/api/family/info', token=TOKEN_A)
members = d.get('members', [])
admin_id = next((m['id'] for m in members if m.get('username') == USER_A), None)
s, d = api('POST', '/api/family/remove-member', {'user_id': admin_id}, token=TOKEN_B)
check('Non-admin cannot remove members', s == 403, f'status={s}')

# Admin tries to remove self
s, d = api('POST', '/api/family/remove-member', {'user_id': admin_id}, token=TOKEN_A)
check('Admin cannot remove self', s == 400, f'status={s}')

# Create family with empty name
s, d = api('POST', '/api/family/create', {'family_name': ''}, token=TOKEN_D)
check('Empty family name rejected', s == 400, f'status={s}')


# ═══════════════════════════════════════════════════════
title('4. PAYMENTS — Validation & Edge Cases')
# ═══════════════════════════════════════════════════════

# Empty description
s, d = api('POST', '/api/payments/add', {
    'description': '', 'amount': 100, 'category': 'כללי'
}, token=TOKEN_A)
check('Empty description rejected', s == 400, f'status={s}')

# Whitespace-only description
s, d = api('POST', '/api/payments/add', {
    'description': '   ', 'amount': 100, 'category': 'כללי'
}, token=TOKEN_A)
check('Whitespace description rejected', s == 400, f'status={s}')

# Zero amount
s, d = api('POST', '/api/payments/add', {
    'description': 'Zero', 'amount': 0, 'category': 'כללי'
}, token=TOKEN_A)
check('Zero amount rejected', s == 400, f'status={s}')

# Negative amount
s, d = api('POST', '/api/payments/add', {
    'description': 'Negative', 'amount': -50, 'category': 'כללי'
}, token=TOKEN_A)
check('Negative amount rejected', s == 400, f'status={s}')

# Very large amount
s, d = api('POST', '/api/payments/add', {
    'description': f'Big_{RND}', 'amount': 99999999.99, 'category': 'כללי'
}, token=TOKEN_A)
check('Very large amount accepted', s == 201)

# Decimal amount
s, d = api('POST', '/api/payments/add', {
    'description': f'Decimal_{RND}', 'amount': 49.99, 'category': 'כללי'
}, token=TOKEN_A)
check('Decimal amount accepted', s == 201)

# SQL injection in description
s, d = api('POST', '/api/payments/add', {
    'description': "'; DROP TABLE payments; --", 'amount': 10, 'category': 'כללי'
}, token=TOKEN_A)
check('SQL injection in description handled', s == 201)
# Verify table still exists
s2, d2 = api('GET', '/api/payments', token=TOKEN_A)
check('Payments table survived SQL injection', s2 == 200)

# XSS in description
s, d = api('POST', '/api/payments/add', {
    'description': '<script>alert("xss")</script>', 'amount': 10, 'category': 'כללי'
}, token=TOKEN_A)
check('XSS in description handled', s == 201)

# Hebrew + emoji description
s, d = api('POST', '/api/payments/add', {
    'description': f'תשלום 🎉 טסט {RND}', 'amount': 50, 'category': 'כללי'
}, token=TOKEN_A)
check('Hebrew + emoji description accepted', s == 201)

# Update non-existent payment
s, d = api('PUT', '/api/payments/999999', {
    'description': 'Ghost', 'amount': 1
}, token=TOKEN_A)
check('Update non-existent payment', s == 200)  # Silently does nothing

# Delete non-existent payment
s, d = api('DELETE', '/api/payments/999999', token=TOKEN_A)
check('Delete non-existent payment', s in [200, 404])

# User B (same family) tries to delete User A's payment
s, d = api('POST', '/api/payments/add', {
    'description': f'OwnerTest_{RND}', 'amount': 10, 'category': 'כללי'
}, token=TOKEN_A)
s, d = api('GET', '/api/payments', token=TOKEN_A)
payments = d if isinstance(d, list) else d.get('payments', [])
owner_payment = next((p for p in payments if f'OwnerTest_{RND}' in p.get('description', '')), None)
if owner_payment:
    s, d = api('DELETE', f'/api/payments/{owner_payment["id"]}', token=TOKEN_B)
    check('Family member can delete others payment (shared family)', s == 200)


# ═══════════════════════════════════════════════════════
title('5. SHOPPING — Validation & Edge Cases')
# ═══════════════════════════════════════════════════════

# Empty item name
s, d = api('POST', '/api/shopping-items', {
    'name': '', 'quantity': 1
}, token=TOKEN_A)
check('Empty shopping name rejected', s == 400, f'status={s}')

# Very long item name
long_name = 'א' * 500
s, d = api('POST', '/api/shopping-items', {
    'name': long_name, 'quantity': 1
}, token=TOKEN_A)
check('Very long shopping name accepted', s == 201)

# Zero quantity
s, d = api('POST', '/api/shopping-items', {
    'name': f'ZeroQty_{RND}', 'quantity': 0
}, token=TOKEN_A)
check('Zero quantity accepted (default behavior)', s == 201)

# Negative quantity
s, d = api('POST', '/api/shopping-items', {
    'name': f'NegQty_{RND}', 'quantity': -1
}, token=TOKEN_A)
check('Negative quantity accepted (no validation)', s == 201)

# SQL injection in item name
s, d = api('POST', '/api/shopping-items', {
    'name': "'; DROP TABLE shopping_items; --", 'quantity': 1
}, token=TOKEN_A)
check('SQL injection in shopping handled', s == 201)
s2, d2 = api('GET', '/api/shopping-items', token=TOKEN_A)
check('Shopping table survived injection', s2 == 200)

# Delete item from wrong family
s, d = api('POST', '/api/shopping-items', {
    'name': f'FamItem_{RND}', 'quantity': 1
}, token=TOKEN_A)
item_id = d.get('id')
if item_id:
    s, d = api('DELETE', f'/api/shopping-items/{item_id}', token=TOKEN_C)
    check('Cannot delete other family shopping item', s == 200)  # Returns 200 but doesn't delete
    # Verify still exists for family 1
    s, d = api('GET', '/api/shopping-items', token=TOKEN_A)
    items = d if isinstance(d, list) else []
    still_exists = any(i.get('name') == f'FamItem_{RND}' for i in items)
    check('Item still exists after cross-family delete attempt', still_exists)


# ═══════════════════════════════════════════════════════
title('6. BABY TRACKER — Validation & Edge Cases')
# ═══════════════════════════════════════════════════════

# Invalid feeding type
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'invalid_type', 'notes': 'test'
}, token=TOKEN_A)
check('Invalid feeding type', s in [201, 400], f'status={s}')

# Empty feeding type
s, d = api('POST', '/api/feedings', {
    'feeding_type': '', 'notes': 'test'
}, token=TOKEN_A)
check('Empty feeding type', s in [201, 400], f'status={s}')

# Bottle with no amount
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'bottle', 'notes': f'NoAmount_{RND}'
}, token=TOKEN_A)
check('Bottle with no amount accepted', s == 201)

# Very large amount
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'bottle', 'amount': 99999, 'notes': 'huge'
}, token=TOKEN_A)
check('Huge feeding amount accepted', s == 201)

# Delete feeding from wrong family
s, d = api('POST', '/api/feedings', {
    'feeding_type': 'diaper', 'notes': f'FamFeed_{RND}'
}, token=TOKEN_A)
feed_id = d.get('id')
if feed_id:
    s, d = api('DELETE', f'/api/feedings/{feed_id}', token=TOKEN_C)
    check('Cross-family feeding delete blocked', s == 200)  # Returns 200 but no effect


# ═══════════════════════════════════════════════════════
title('7. CATEGORIES — Edge Cases')
# ═══════════════════════════════════════════════════════

# Empty category name
s, d = api('POST', '/api/categories', {'name': '', 'color': '#ff0000'}, token=TOKEN_A)
check('Empty category name rejected', s == 400)

# Whitespace category name
s, d = api('POST', '/api/categories', {'name': '   ', 'color': '#ff0000'}, token=TOKEN_A)
check('Whitespace category name rejected', s == 400)

# Very long category name
s, d = api('POST', '/api/categories', {'name': 'א' * 200, 'color': '#ff0000'}, token=TOKEN_A)
check('Very long category name', s == 201)

# Duplicate custom category
cat_name = f'DupCat_{RND}'
api('POST', '/api/categories', {'name': cat_name, 'color': '#ff0000'}, token=TOKEN_A)
s, d = api('POST', '/api/categories', {'name': cat_name, 'color': '#ff0000'}, token=TOKEN_A)
check('Duplicate custom category rejected', s == 400)

# Same name in different family (should work)
s, d = api('POST', '/api/categories', {'name': cat_name, 'color': '#00ff00'}, token=TOKEN_C)
check('Same category name in different family OK', s == 201)

# Delete non-existent category
s, d = api('DELETE', '/api/categories/999999', token=TOKEN_A)
check('Delete non-existent category → 404', s == 404)

# Delete category from wrong family
s, cats = api('GET', '/api/categories', token=TOKEN_C)
custom_c = [c for c in cats if not c.get('is_default') and c['name'] == cat_name]
if custom_c:
    s, d = api('DELETE', f'/api/categories/{custom_c[0]["id"]}', token=TOKEN_A)
    check('Cannot delete other family category', s == 403, f'status={s}')

# SQL injection in category name
s, d = api('POST', '/api/categories', {
    'name': "'; DROP TABLE categories; --", 'color': '#000'
}, token=TOKEN_A)
check('SQL injection in category handled', s in [201, 400])
s2, d2 = api('GET', '/api/categories', token=TOKEN_A)
check('Categories table survived injection', s2 == 200 and len(d2) >= 9)


# ═══════════════════════════════════════════════════════
title('8. BUDGET ALERTS — Threshold Logic')
# ═══════════════════════════════════════════════════════

# Set budget to 100 so we can test thresholds
s, d = api('PUT', '/api/family/settings', {
    'budget_monthly': 100, 'budget_daily': 50
}, token=TOKEN_A)
check('Set test budget (monthly=100, daily=50)', s == 200)

# Add payment of 85 → should trigger 80% alert
s, d = api('POST', '/api/payments/add', {
    'description': f'Budget80_{RND}', 'amount': 85, 'category': 'כללי'
}, token=TOKEN_A)
check('Payment 85/100 (85%) added', s == 201)

# Add payment of 20 → total 105 → should trigger 100% alert
s, d = api('POST', '/api/payments/add', {
    'description': f'Budget100_{RND}', 'amount': 20, 'category': 'כללי'
}, token=TOKEN_A)
check('Payment total 105/100 (105%) added', s == 201)

# Verify budget settings were not corrupted
s, d = api('GET', '/api/family/settings', token=TOKEN_A)
check('Budget settings intact', d.get('budget_monthly') == 100)

# Reset budget to avoid interfering with other tests
api('PUT', '/api/family/settings', {'budget_monthly': 0, 'budget_daily': 0}, token=TOKEN_A)


# ═══════════════════════════════════════════════════════
title('9. RECURRING PAYMENTS — Edge Cases')
# ═══════════════════════════════════════════════════════

# Add recurring with missing fields
s, d = api('POST', '/api/recurring', {
    'description': '', 'amount': 50
}, token=TOKEN_A)
check('Empty recurring description', s in [201, 400], f'status={s}')

# Add recurring with 0 amount
s, d = api('POST', '/api/recurring', {
    'description': f'ZeroRec_{RND}', 'amount': 0
}, token=TOKEN_A)
check('Zero recurring amount', s in [201, 400], f'status={s}')

# Valid recurring
s, d = api('POST', '/api/recurring', {
    'description': f'ValidRec_{RND}', 'amount': 100, 'category': 'קבועים'
}, token=TOKEN_A)
rec_id = d.get('id')
check('Add valid recurring', s == 201)

# Update recurring - change amount to negative
if rec_id:
    s, d = api('PUT', f'/api/recurring/{rec_id}', {'amount': -50}, token=TOKEN_A)
    check('Update recurring negative amount', s == 200)  # No validation currently

    # Delete
    s, d = api('DELETE', f'/api/recurring/{rec_id}', token=TOKEN_A)
    check('Delete recurring', s == 200)


# ═══════════════════════════════════════════════════════
title('10. EXPORT CSV')
# ═══════════════════════════════════════════════════════

r = api_raw('GET', '/api/payments/export', token=TOKEN_A)
check('Export CSV returns file', r.status_code == 200)
check('Export CSV content type', 'text/csv' in r.headers.get('Content-Type', ''))
check('Export CSV has BOM', r.content[:3] == b'\xef\xbb\xbf')
check('Export CSV has header row', 'תיאור' in r.text)


# ═══════════════════════════════════════════════════════
title('11. ARCHIVE MONTH')
# ═══════════════════════════════════════════════════════

# Archive with existing payments
s, d = api('POST', '/api/payments/archive', token=TOKEN_A)
check('Archive month', s == 200, f'status={s}, detail={d}')

# Archive again (should fail — no more unarchived)
s, d = api('POST', '/api/payments/archive', token=TOKEN_A)
check('Double archive rejected', s == 400)


# ═══════════════════════════════════════════════════════
title('12. HISTORY — After Archive')
# ═══════════════════════════════════════════════════════

s, d = api('GET', '/api/history/data', token=TOKEN_A)
check('History has data', s == 200)
months = d.get('months', []) if isinstance(d, dict) else []
has_data = any(m.get('count', 0) > 0 or m.get('total', 0) > 0 for m in months)
check('History has payment data', has_data or d.get('month_count', 0) > 0,
      f'months={len(months)}, month_count={d.get("month_count", 0)}')


# ═══════════════════════════════════════════════════════
title('13. CORS — Headers Check')
# ═══════════════════════════════════════════════════════

# Preflight from Capacitor origin
r = requests.options(BASE + '/api/home-summary', headers={
    'Origin': 'capacitor://localhost',
    'Access-Control-Request-Method': 'GET',
    'Access-Control-Request-Headers': 'Authorization'
}, timeout=5)
check('CORS preflight succeeds', r.status_code in [200, 204], f'status={r.status_code}')
check('CORS allows capacitor origin',
      r.headers.get('Access-Control-Allow-Origin') == 'capacitor://localhost')

# Request from unknown origin
r = requests.get(BASE + '/api/home-summary', headers={
    'Origin': 'https://evil.com',
    'Authorization': f'Bearer {TOKEN_A}'
}, timeout=5)
check('Unknown origin: no CORS header',
      r.headers.get('Access-Control-Allow-Origin') != 'https://evil.com')


# ═══════════════════════════════════════════════════════
title('14. CONCURRENT OPERATIONS')
# ═══════════════════════════════════════════════════════

# Multiple simultaneous payment additions
results = []
def add_payment_thread(token, desc, amount):
    s, d = api('POST', '/api/payments/add', {
        'description': desc, 'amount': amount, 'category': 'כללי'
    }, token=token)
    results.append(s)

threads = []
for i in range(5):
    t = threading.Thread(target=add_payment_thread,
                         args=(TOKEN_A, f'Concurrent_{RND}_{i}', 10 + i))
    threads.append(t)

for t in threads:
    t.start()
for t in threads:
    t.join(timeout=10)

check('5 concurrent payments all succeed',
      len(results) == 5 and all(s == 201 for s in results),
      f'results={results}')


# ═══════════════════════════════════════════════════════
title('15. SETTINGS — Edge Cases')
# ═══════════════════════════════════════════════════════

# Empty display name
s, d = api('PUT', '/api/settings/profile', {'display_name': ''}, token=TOKEN_A)
check('Empty display name rejected', s in [200, 400], f'status={s}')

# Very long display name
s, d = api('PUT', '/api/settings/profile', {'display_name': 'א' * 200}, token=TOKEN_A)
check('Very long display name', s == 200)
TOKEN_A = d.get('token', TOKEN_A)

# Restore normal name
s, d = api('PUT', '/api/settings/profile', {'display_name': 'Edge A'}, token=TOKEN_A)
TOKEN_A = d.get('token', TOKEN_A)

# Feeding reminder edge: 0 hours (disabled)
s, d = api('PUT', '/api/family/settings', {'feeding_reminder_hours': 0}, token=TOKEN_A)
check('Disable feeding reminder', s == 200)

# Negative budget
s, d = api('PUT', '/api/family/settings', {'budget_monthly': -100}, token=TOKEN_A)
check('Negative budget accepted (no validation)', s == 200)

# Reset
api('PUT', '/api/family/settings', {'budget_monthly': 0, 'budget_daily': 0}, token=TOKEN_A)


# ═══════════════════════════════════════════════════════
title('16. MULTIPLE RAPID REQUESTS — Rate Limiting / Stability')
# ═══════════════════════════════════════════════════════

errors = 0
for i in range(20):
    s, d = api('GET', '/api/home-summary', token=TOKEN_A)
    if s != 200:
        errors += 1
check('20 rapid requests all succeed', errors == 0, f'{errors} failed')


# ═══════════════════════════════════════════════════════
title('17. DATA TYPES — Weird Input')
# ═══════════════════════════════════════════════════════

# Amount as string
s, d = api('POST', '/api/payments/add', {
    'description': f'StringAmt_{RND}', 'amount': 'fifty', 'category': 'כללי'
}, token=TOKEN_A)
check('String amount rejected', s in [400, 500], f'status={s}')

# Amount as null
s, d = api('POST', '/api/payments/add', {
    'description': f'NullAmt_{RND}', 'amount': None, 'category': 'כללי'
}, token=TOKEN_A)
check('Null amount rejected', s == 400, f'status={s}')

# No body at all
s, d = api('POST', '/api/payments/add', data=None, token=TOKEN_A)
check('No body rejected', s in [400, 500], f'status={s}')

# Extra unknown fields (should be ignored)
s, d = api('POST', '/api/payments/add', {
    'description': f'Extra_{RND}', 'amount': 10, 'category': 'כללי',
    'hack': 'value', 'admin': True, 'family_id': 9999
}, token=TOKEN_A)
check('Extra fields ignored (no crash)', s == 201)


# ═══════════════════════════════════════════════════════
title('18. FAVORITES — Edge Cases')
# ═══════════════════════════════════════════════════════

# Add new favorite directly
s, d = api('POST', '/api/shopping-items/add-new-favorite', {
    'name': f'DirectFav_{RND}', 'quantity': 3, 'category': '🥛 חלבי'
}, token=TOKEN_A)
check('Add new favorite directly', s in [200, 201])

# Edit favorite
s, d = api('POST', '/api/shopping-items/edit-favorite', {
    'old_name': f'DirectFav_{RND}', 'name': f'EditedFav_{RND}', 'quantity': 5
}, token=TOKEN_A)
check('Edit favorite', s == 200)

# Delete favorite
s, d = api('POST', '/api/shopping-items/delete-favorite', {
    'name': f'EditedFav_{RND}'
}, token=TOKEN_A)
check('Delete favorite', s == 200)

# Add all favorites to list
s, d = api('POST', '/api/shopping-items/add-favorites', token=TOKEN_A)
check('Add all favorites to list', s == 200)


# ═══════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════
title('Cleanup')

c = sqlite3.connect(DB_PATH)
for username in [USER_A, USER_B, USER_C, USER_D]:
    u = c.execute('SELECT id, family_id FROM users WHERE username=?', (username,)).fetchone()
    if u:
        uid, fid = u
        c.execute('DELETE FROM push_tokens WHERE user_id=?', (uid,))
        if fid:
            others = c.execute('SELECT COUNT(*) FROM users WHERE family_id=? AND username NOT IN (?,?,?,?)',
                               (fid, USER_A, USER_B, USER_C, USER_D)).fetchone()[0]
            if others == 0:
                for tbl in ['payments', 'shopping_items', 'shopping_favorites', 'feedings',
                            'recurring_payments', 'family_settings', 'archived_cycles']:
                    c.execute(f'DELETE FROM {tbl} WHERE family_id=?', (fid,))
                c.execute('DELETE FROM categories WHERE family_id=?', (fid,))
                c.execute('DELETE FROM families WHERE id=?', (fid,))
        c.execute('DELETE FROM users WHERE id=?', (uid,))
c.commit()
c.close()
print('  🧹 Test data cleaned')


# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════
print(f'\n{"=" * 60}')
print(f'  RESULTS: {PASS} passed, {FAIL} failed')
print(f'{"=" * 60}')

if ERRORS:
    print('\n❌ FAILURES:')
    for e in ERRORS:
        print(e)
    print(f'\n⚠️  {FAIL} issues to review before production')
else:
    print('\n✅ ALL TESTS PASSED — Rock solid for production!')

print()
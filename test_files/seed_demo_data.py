"""
Seed demo data — creates a test user with 6 months of realistic payment data.
Run with Flask running: python test_files/seed_demo_data.py

Login: username=demo_user, password=Demo1234!
"""
import requests
import sqlite3
import os
import random
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DB_PATH = os.path.join(PROJECT_ROOT, 'finance_tracker.db')
BASE = 'http://127.0.0.1:5000'

USERNAME = 'demo_user'
PASSWORD = 'Demo1234!'
EMAIL = 'demo@test.com'
FAMILY_NAME = 'משפחת דמו'

# ── Realistic Israeli expense patterns ──
EXPENSES = {
    'מזון': [
        ('סופר', 200, 400),
        ('מכולת', 30, 80),
        ('ירקות ופירות', 40, 120),
        ('בשר ודגים', 80, 200),
        ('לחם ומאפים', 15, 45),
    ],
    'תחבורה': [
        ('דלק', 200, 350),
        ('חניה', 15, 40),
        ('רב-קו', 50, 150),
    ],
    'בילויים': [
        ('מסעדה', 100, 350),
        ('קפה', 15, 35),
        ('סרט', 40, 80),
        ('קניון', 50, 200),
    ],
    'חשבונות': [
        ('חשמל', 150, 400),
        ('מים', 60, 150),
        ('גז', 50, 120),
        ('אינטרנט', 100, 130),
        ('סלולר', 50, 100),
    ],
    'בריאות': [
        ('מרקחת', 30, 150),
        ('רופא', 50, 200),
    ],
    'ביגוד': [
        ('בגדים', 80, 300),
        ('נעליים', 100, 400),
    ],
    'כללי': [
        ('אמזון', 50, 300),
        ('מתנה', 50, 200),
        ('ציוד בית', 30, 150),
    ],
}


def api(method, path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if method == 'POST':
        r = requests.post(BASE + path, json=data, headers=headers, timeout=10)
    elif method == 'GET':
        r = requests.get(BASE + path, headers=headers, timeout=10)
    elif method == 'PUT':
        r = requests.put(BASE + path, json=data, headers=headers, timeout=10)
    else:
        return None, {}
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {}


def cleanup_existing():
    """Remove existing demo user if exists"""
    c = sqlite3.connect(DB_PATH)
    u = c.execute('SELECT id, family_id FROM users WHERE username=?', (USERNAME,)).fetchone()
    if u:
        uid, fid = u
        c.execute('DELETE FROM push_tokens WHERE user_id=?', (uid,))
        if fid:
            for tbl in ['payments', 'shopping_items', 'shopping_favorites', 'feedings',
                        'recurring_payments', 'family_settings', 'archived_cycles', 'categories']:
                c.execute(f'DELETE FROM {tbl} WHERE family_id=?', (fid,))
            c.execute('DELETE FROM families WHERE id=?', (fid,))
        c.execute('DELETE FROM users WHERE id=?', (uid,))
        c.commit()
        print('  Cleaned up existing demo user')
    c.close()


def generate_month_expenses(family_id, year, month, num_expenses=15):
    """Generate realistic expenses for a given month"""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    month_str = f'{year}-{month:02d}'

    c = sqlite3.connect(DB_PATH)
    total = 0
    for _ in range(num_expenses):
        category = random.choice(list(EXPENSES.keys()))
        desc, min_amt, max_amt = random.choice(EXPENSES[category])
        amount = round(random.uniform(min_amt, max_amt), 0)
        day = random.randint(1, last_day)
        hour = random.randint(7, 23)
        minute = random.randint(0, 59)
        pay_date = datetime(year, month, day, hour, minute, 0)

        c.execute(
            'INSERT INTO payments (family_id, description, amount, category, date, month, year, archived) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (family_id, desc, amount, category,
             pay_date.strftime('%Y-%m-%d %H:%M:%S'), month_str, year, False))
        total += amount

    c.commit()
    c.close()
    return total


def archive_month(family_id, year, month, total, count):
    """Archive a month's payments"""
    hebrew = {1: 'ינואר', 2: 'פברואר', 3: 'מרץ', 4: 'אפריל', 5: 'מאי', 6: 'יוני',
              7: 'יולי', 8: 'אוגוסט', 9: 'ספטמבר', 10: 'אוקטובר', 11: 'נובמבר', 12: 'דצמבר'}
    month_str = f'{year}-{month:02d}'
    label = f'{hebrew[month]} {year}'

    c = sqlite3.connect(DB_PATH)
    # Mark payments as archived
    c.execute('UPDATE payments SET archived=TRUE WHERE family_id=? AND month=? AND archived=FALSE',
              (family_id, month_str))
    # Create archive record
    c.execute('INSERT INTO archived_cycles (family_id, label, total, count, month) VALUES (?,?,?,?,?)',
              (family_id, label, total, count, month_str))
    c.commit()
    c.close()


# ═══════════════════════════════════════════════════════════
print('\n' + '=' * 55)
print('  SEED DEMO DATA')
print('=' * 55)

# Cleanup
cleanup_existing()

# Register
s, d = api('POST', '/api/auth/register', {
    'display_name': 'יוזר דמו',
    'username': USERNAME,
    'email': EMAIL,
    'password': PASSWORD,
    'password2': PASSWORD
})
token = d.get('token')
print(f'  Register: {s}')

# Create family
s, d = api('POST', '/api/family/create', {'family_name': FAMILY_NAME}, token=token)
token = d.get('token', token)
print(f'  Family: {s}')

# Get family_id
c = sqlite3.connect(DB_PATH)
fid = c.execute('SELECT family_id FROM users WHERE username=?', (USERNAME,)).fetchone()[0]
c.close()
print(f'  Family ID: {fid}')

# ── Generate 6 months of data ──
now = datetime.now()
cur_year = now.year
cur_month = now.month

print(f'\n  Generating 6 months of data...\n')

months_data = []

for i in range(6, 0, -1):
    # Calculate month (going back from current)
    m = cur_month - i
    y = cur_year
    while m <= 0:
        m += 12
        y -= 1

    # More expenses in some months for variety
    num = random.randint(12, 22)
    total = generate_month_expenses(fid, y, m, num)

    hebrew = {1: 'ינואר', 2: 'פברואר', 3: 'מרץ', 4: 'אפריל', 5: 'מאי', 6: 'יוני',
              7: 'יולי', 8: 'אוגוסט', 9: 'ספטמבר', 10: 'אוקטובר', 11: 'נובמבר', 12: 'דצמבר'}

    is_current = (y == cur_year and m == cur_month)
    if not is_current:
        archive_month(fid, y, m, total, num)
        status = 'archived'
    else:
        status = 'ACTIVE'

    print(f'    {hebrew[m]} {y}: {num} payments, total ₪{total:,.0f} [{status}]')
    months_data.append((y, m, num, total, status))

# Also add some payments for current month
num_current = random.randint(5, 12)
total_current = generate_month_expenses(fid, cur_year, cur_month, num_current)
print(f'    {hebrew.get(cur_month, cur_month)} {cur_year}: +{num_current} payments, total ₪{total_current:,.0f} [ACTIVE - additional]')

# ── Summary ──
c = sqlite3.connect(DB_PATH)
total_payments = c.execute('SELECT COUNT(*) FROM payments WHERE family_id=?', (fid,)).fetchone()[0]
active_payments = c.execute('SELECT COUNT(*) FROM payments WHERE family_id=? AND archived=FALSE', (fid,)).fetchone()[0]
archived_payments = c.execute('SELECT COUNT(*) FROM payments WHERE family_id=? AND archived=TRUE', (fid,)).fetchone()[0]
archives = c.execute('SELECT COUNT(*) FROM archived_cycles WHERE family_id=?', (fid,)).fetchone()[0]
c.close()

print(f'\n' + '=' * 55)
print(f'  DONE!')
print(f'  Total payments: {total_payments} ({active_payments} active, {archived_payments} archived)')
print(f'  Archive records: {archives}')
print(f'')
print(f'  LOGIN:')
print(f'    Username: {USERNAME}')
print(f'    Password: {PASSWORD}')
print(f'')
print(f'  Check:')
print(f'    Dashboard: http://127.0.0.1:5000/dashboard')
print(f'    History:   http://127.0.0.1:5000/history')
print(f'=' * 55 + '\n')

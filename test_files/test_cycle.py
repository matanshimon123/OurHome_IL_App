"""
בדיקות מקיפות לפיצ'ר מחזורי חיוב (cycle_day) — OurHome IL
הרץ כשה-Flask רץ: python test_files/test_cycle.py

בודק:
 - תשלומים מוקצים לחודש מחזור נכון
 - שינוי cycle_day מעדכן תשלומים פעילים
 - שינוי cycle_day לא משפיע על תשלומים מאורכבים
 - גרף יומי מציג ימים נכונים
 - היסטוריה מציגה labels נכונים
 - הרשאות: רק admin יכול לשנות cycle_day
"""
import requests
import random
import string
import sqlite3
import os
from datetime import datetime, timedelta

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
        print(f'  \u2705 {name}')
    else:
        FAIL += 1
        msg = f'  \u274c {name}' + (f' \u2014 {detail}' if detail else '')
        ERRORS.append(msg)
        print(msg)


def api(method, path, data=None, token=None):
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
        return r.status_code, result
    except requests.ConnectionError:
        print(f'    \u274c CONNECTION ERROR: Flask running?')
        return 0, {}


def cleanup_user(username):
    c = sqlite3.connect(DB_PATH)
    u = c.execute('SELECT id, family_id FROM users WHERE username=?', (username,)).fetchone()
    if u:
        uid, fid = u
        c.execute('DELETE FROM push_tokens WHERE user_id=?', (uid,))
        if fid:
            remaining = c.execute('SELECT COUNT(*) FROM users WHERE family_id=? AND id!=?', (fid, uid)).fetchone()[0]
            if remaining == 0:
                for tbl in ['payments', 'shopping_items', 'shopping_favorites', 'feedings',
                            'recurring_payments', 'family_settings', 'archived_cycles', 'categories']:
                    c.execute(f'DELETE FROM {tbl} WHERE family_id=?', (fid,))
                c.execute('DELETE FROM families WHERE id=?', (fid,))
        c.execute('DELETE FROM users WHERE id=?', (uid,))
    c.commit()
    c.close()


def inject_payment(family_id, description, amount, pay_date, month_str):
    """Insert a payment directly into DB with a specific date and month"""
    c = sqlite3.connect(DB_PATH)
    year = int(month_str.split('-')[0])
    c.execute(
        'INSERT INTO payments (family_id, description, amount, category, date, month, year, archived) '
        'VALUES (?,?,?,?,?,?,?,FALSE)',
        (family_id, description, amount, '\u05db\u05dc\u05dc\u05d9',
         pay_date.strftime('%Y-%m-%d %H:%M:%S'), month_str, year))
    c.commit()
    c.close()


def inject_archived_payment(family_id, description, amount, pay_date, month_str):
    """Insert an archived payment directly into DB"""
    c = sqlite3.connect(DB_PATH)
    year = int(month_str.split('-')[0])
    c.execute(
        'INSERT INTO payments (family_id, description, amount, category, date, month, year, archived) '
        'VALUES (?,?,?,?,?,?,?,TRUE)',
        (family_id, description, amount, '\u05db\u05dc\u05dc\u05d9',
         pay_date.strftime('%Y-%m-%d %H:%M:%S'), month_str, year))
    c.commit()
    c.close()


def get_family_id(username):
    c = sqlite3.connect(DB_PATH)
    r = c.execute('SELECT family_id FROM users WHERE username=?', (username,)).fetchone()
    c.close()
    return r[0] if r else None


def get_payments(family_id, archived=False):
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        'SELECT * FROM payments WHERE family_id=? AND archived=?',
        (family_id, archived)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def title(txt):
    print(f'\n{"=" * 60}')
    print(f'  {txt}')
    print(f'{"=" * 60}')


# ═══════════════════════════════════════════════════════════
#  SETUP: Create admin user + family
# ═══════════════════════════════════════════════════════════
print(f'\n\U0001f9ea CYCLE DAY TESTS (run={RND})\n')
title('SETUP')

ADMIN_USER = rnd('cadm_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Cycle Admin', 'username': ADMIN_USER,
    'email': f'{ADMIN_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
ADMIN_TOKEN = d.get('token')
check('Admin registered', s == 201 and ADMIN_TOKEN)

s, d = api('POST', '/api/family/create', {'family_name': f'CycleFam_{RND}'}, token=ADMIN_TOKEN)
ADMIN_TOKEN = d.get('token', ADMIN_TOKEN)
INVITE_CODE = d.get('family', {}).get('invite_code')
FID = get_family_id(ADMIN_USER)
check('Family created', FID is not None and INVITE_CODE, f'fid={FID}')

# Create a non-admin member
MEMBER_USER = rnd('cmem_')
s, d = api('POST', '/api/auth/register', {
    'display_name': 'Cycle Member', 'username': MEMBER_USER,
    'email': f'{MEMBER_USER}@test.com', 'password': 'Test1234!', 'password2': 'Test1234!'
})
MEMBER_TOKEN = d.get('token')
check('Member registered', s == 201 and MEMBER_TOKEN, f'status={s}, resp={d}')

# Join family
s, d = api('POST', '/api/family/join', {'invite_code': INVITE_CODE}, token=MEMBER_TOKEN)
MEMBER_TOKEN = d.get('token', MEMBER_TOKEN)
check('Member joined family', s == 200, f'status={s}, invite={INVITE_CODE}, resp={d}')


# ═══════════════════════════════════════════════════════════
title('TEST 1: Default cycle_day=1 (calendar month)')
# ═══════════════════════════════════════════════════════════

s, d = api('GET', '/api/family/settings', token=ADMIN_TOKEN)
check('1.1 Default cycle_day is 1', d.get('cycle_day') == 1)

s, d = api('GET', '/api/family/cycle', token=ADMIN_TOKEN)
now = datetime.now()
check('1.2 Cycle month matches calendar', d.get('cycle_month') == now.strftime('%Y-%m'))
check('1.3 Cycle start is 1st of month',
      d.get('start_date') == now.replace(day=1).strftime('%Y-%m-%d'))


# ═══════════════════════════════════════════════════════════
title('TEST 2: Inject payments at various dates, verify month assignment')
# ═══════════════════════════════════════════════════════════

# Inject payments at specific dates (with cycle_day=1, month = calendar month)
today = datetime.now()
year = today.year
month = today.month

# Payment on the 3rd of this month
inject_payment(FID, f'pay3_{RND}', 100, datetime(year, month, 3, 10, 0), f'{year}-{month:02d}')
# Payment on the 15th
inject_payment(FID, f'pay15_{RND}', 200, datetime(year, month, 15, 10, 0), f'{year}-{month:02d}')
# Payment on the 25th
inject_payment(FID, f'pay25_{RND}', 300, datetime(year, month, 25, 10, 0), f'{year}-{month:02d}')

payments = get_payments(FID, archived=False)
test_payments = [p for p in payments if RND in p['description']]
check('2.1 Three payments injected', len(test_payments) == 3, f'got {len(test_payments)}')

all_current_month = all(p['month'] == f'{year}-{month:02d}' for p in test_payments)
check('2.2 All assigned to current calendar month', all_current_month)


# ═══════════════════════════════════════════════════════════
title('TEST 3: Change cycle_day to 10 — payments re-categorize')
# ═══════════════════════════════════════════════════════════

s, d = api('PUT', '/api/family/settings', {'cycle_day': 10}, token=ADMIN_TOKEN)
check('3.1 cycle_day changed to 10', s == 200)

s, d = api('GET', '/api/family/settings', token=ADMIN_TOKEN)
check('3.2 Settings confirm cycle_day=10', d.get('cycle_day') == 10)

# Now check: pay3 (day 3) should be in PREVIOUS month's cycle (day < 10)
# pay15 and pay25 (day >= 10) should stay in current month's cycle
payments = get_payments(FID, archived=False)
test_payments = {p['description']: p for p in payments if RND in p['description']}

pay3 = test_payments.get(f'pay3_{RND}')
pay15 = test_payments.get(f'pay15_{RND}')
pay25 = test_payments.get(f'pay25_{RND}')

# With cycle_day=10, day 3 → previous month's cycle
prev_month = (datetime(year, month, 1) - timedelta(days=1))
expected_prev = prev_month.strftime('%Y-%m')

check('3.3 pay3 (day 3) moved to previous cycle',
      pay3 and pay3['month'] == expected_prev,
      f"got month={pay3['month'] if pay3 else 'N/A'}, expected={expected_prev}")
check('3.4 pay15 (day 15) stays in current cycle',
      pay15 and pay15['month'] == f'{year}-{month:02d}',
      f"got month={pay15['month'] if pay15 else 'N/A'}")
check('3.5 pay25 (day 25) stays in current cycle',
      pay25 and pay25['month'] == f'{year}-{month:02d}',
      f"got month={pay25['month'] if pay25 else 'N/A'}")

# Verify cycle info API
s, d = api('GET', '/api/family/cycle', token=ADMIN_TOKEN)
check('3.6 Cycle label includes date range',
      '(' in d.get('label', '') and '\u2013' in d.get('label', ''),
      f"label={d.get('label')}")
check('3.7 Cycle start is 10th',
      d.get('start_date', '').endswith(f'-10'),
      f"start={d.get('start_date')}")


# ═══════════════════════════════════════════════════════════
title('TEST 4: Change cycle_day to 20 — re-categorize again')
# ═══════════════════════════════════════════════════════════

s, d = api('PUT', '/api/family/settings', {'cycle_day': 20}, token=ADMIN_TOKEN)
check('4.1 cycle_day changed to 20', s == 200)

payments = get_payments(FID, archived=False)
test_payments = {p['description']: p for p in payments if RND in p['description']}

pay3 = test_payments.get(f'pay3_{RND}')
pay15 = test_payments.get(f'pay15_{RND}')
pay25 = test_payments.get(f'pay25_{RND}')

# With cycle_day=20: day 3 and day 15 → previous cycle, day 25 → current
check('4.2 pay3 (day 3) in previous cycle',
      pay3 and pay3['month'] == expected_prev,
      f"got {pay3['month'] if pay3 else 'N/A'}")
check('4.3 pay15 (day 15) in previous cycle',
      pay15 and pay15['month'] == expected_prev,
      f"got {pay15['month'] if pay15 else 'N/A'}")
check('4.4 pay25 (day 25) stays in current cycle',
      pay25 and pay25['month'] == f'{year}-{month:02d}',
      f"got {pay25['month'] if pay25 else 'N/A'}")


# ═══════════════════════════════════════════════════════════
title('TEST 5: Archived payments NOT affected by cycle_day change')
# ═══════════════════════════════════════════════════════════

# Reset to cycle_day=1 first
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)

# Inject an archived payment (simulating history)
inject_archived_payment(FID, f'archived_{RND}', 500,
                        datetime(year, month, 5, 10, 0), f'{year}-{month:02d}')

archived_before = get_payments(FID, archived=True)
arch_payment = next((p for p in archived_before if f'archived_{RND}' in p['description']), None)
check('5.1 Archived payment exists', arch_payment is not None)
month_before = arch_payment['month'] if arch_payment else None

# Now change cycle_day to 15
s, d = api('PUT', '/api/family/settings', {'cycle_day': 15}, token=ADMIN_TOKEN)
check('5.2 cycle_day changed to 15', s == 200)

# Check archived payment was NOT changed
archived_after = get_payments(FID, archived=True)
arch_payment_after = next((p for p in archived_after if f'archived_{RND}' in p['description']), None)
check('5.3 Archived payment month unchanged',
      arch_payment_after and arch_payment_after['month'] == month_before,
      f"before={month_before}, after={arch_payment_after['month'] if arch_payment_after else 'N/A'}")

# But active payments WERE re-categorized
active = get_payments(FID, archived=False)
pay3_after = next((p for p in active if f'pay3_{RND}' in p['description']), None)
check('5.4 Active pay3 WAS re-categorized (day 3 < 15 → prev cycle)',
      pay3_after and pay3_after['month'] == expected_prev,
      f"got {pay3_after['month'] if pay3_after else 'N/A'}")


# ═══════════════════════════════════════════════════════════
title('TEST 6: Change back to cycle_day=1 — all active go to calendar month')
# ═══════════════════════════════════════════════════════════

s, d = api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)
check('6.1 cycle_day reset to 1', s == 200)

payments = get_payments(FID, archived=False)
test_payments = [p for p in payments if RND in p['description']]
all_calendar = all(p['month'] == f'{year}-{month:02d}' for p in test_payments)
check('6.2 All active payments back in calendar month', all_calendar,
      f"months: {[p['month'] for p in test_payments]}")


# ═══════════════════════════════════════════════════════════
title('TEST 7: Permissions — only admin can change cycle_day')
# ═══════════════════════════════════════════════════════════

s, d = api('PUT', '/api/family/settings', {'cycle_day': 5}, token=MEMBER_TOKEN)
check('7.1 Member cannot change cycle_day', s == 403,
      f'got status={s}')

s, d = api('GET', '/api/family/settings', token=MEMBER_TOKEN)
check('7.2 cycle_day still 1 after member attempt', d.get('cycle_day') == 1,
      f"got {d.get('cycle_day')}")


# ═══════════════════════════════════════════════════════════
title('TEST 8: Validation — cycle_day boundaries')
# ═══════════════════════════════════════════════════════════

s, d = api('PUT', '/api/family/settings', {'cycle_day': 0}, token=ADMIN_TOKEN)
check('8.1 cycle_day=0 rejected', s == 400)

s, d = api('PUT', '/api/family/settings', {'cycle_day': 29}, token=ADMIN_TOKEN)
check('8.2 cycle_day=29 rejected', s == 400)

s, d = api('PUT', '/api/family/settings', {'cycle_day': -1}, token=ADMIN_TOKEN)
check('8.3 cycle_day=-1 rejected', s == 400)

s, d = api('PUT', '/api/family/settings', {'cycle_day': 28}, token=ADMIN_TOKEN)
check('8.4 cycle_day=28 accepted', s == 200)

s, d = api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)
check('8.5 cycle_day=1 accepted', s == 200)


# ═══════════════════════════════════════════════════════════
title('TEST 9: Chart data respects cycle range')
# ═══════════════════════════════════════════════════════════

# Set cycle_day=10
api('PUT', '/api/family/settings', {'cycle_day': 10}, token=ADMIN_TOKEN)

s, d = api('GET', '/api/chart_data', token=ADMIN_TOKEN)
check('9.1 Chart data returned', s == 200 and 'daily' in d)

labels = d.get('daily', {}).get('labels', [])
today_index = d.get('daily', {}).get('today_index', -1)

# Labels should start at 10 (cycle start day)
check('9.2 Chart labels start at cycle_day=10',
      len(labels) > 0 and labels[0] == 10,
      f'first label={labels[0] if labels else "empty"}')

# Labels should wrap: ...28,29,30,1,2,...,9
if len(labels) > 1:
    # Find where the wrap happens (a day that is < its predecessor)
    wrap_idx = None
    for i in range(1, len(labels)):
        if labels[i] < labels[i - 1]:
            wrap_idx = i
            break
    check('9.3 Labels wrap from end-of-month to 1',
          wrap_idx is not None,
          f'labels sample: {labels[:5]}...{labels[-5:]}')
    if wrap_idx:
        check('9.4 After wrap, labels continue from 1',
              labels[wrap_idx] == 1,
              f'wrap at index {wrap_idx}, value={labels[wrap_idx]}')

# Last label should be 9 (cycle_day - 1)
check('9.5 Chart labels end at cycle_day-1=9',
      len(labels) > 0 and labels[-1] == 9,
      f'last label={labels[-1] if labels else "empty"}')

check('9.6 today_index is valid',
      today_index >= 0 and today_index < len(labels),
      f'today_index={today_index}, len={len(labels)}')

# Reset
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)


# ═══════════════════════════════════════════════════════════
title('TEST 10: History data includes cycle labels')
# ═══════════════════════════════════════════════════════════

# With cycle_day=1, labels should be plain month names
s, d = api('GET', f'/api/history/data?year={year}', token=ADMIN_TOKEN)
check('10.1 History data returned', s == 200 and 'months' in d)

months_data = d.get('months', [])
first_month = months_data[0] if months_data else {}
check('10.2 cycle_day=1: label is plain month name',
      first_month.get('label') and '(' not in first_month.get('label', ''),
      f"label={first_month.get('label')}")

# Change to cycle_day=10
api('PUT', '/api/family/settings', {'cycle_day': 10}, token=ADMIN_TOKEN)

s, d = api('GET', f'/api/history/data?year={year}', token=ADMIN_TOKEN)
months_data = d.get('months', [])
first_month = months_data[0] if months_data else {}
check('10.3 cycle_day=10: label includes date range',
      first_month.get('label') and '(' in first_month.get('label', ''),
      f"label={first_month.get('label')}")
check('10.4 Response includes cycle_day', d.get('cycle_day') == 10)

# Reset
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)


# ═══════════════════════════════════════════════════════════
title('TEST 11: History month popup includes cycle info')
# ═══════════════════════════════════════════════════════════

# With cycle_day=1
s, d = api('GET', f'/api/history/month?year={year}&month={month}', token=ADMIN_TOKEN)
check('11.1 Month popup data returned', s == 200)
check('11.2 cycle_day=1: cycle_label is plain',
      d.get('cycle_label') and '(' not in d.get('cycle_label', ''),
      f"cycle_label={d.get('cycle_label')}")
check('11.3 cycle_dates present',
      d.get('cycle_dates') is not None,
      f"cycle_dates={d.get('cycle_dates')}")

# With cycle_day=10
api('PUT', '/api/family/settings', {'cycle_day': 10}, token=ADMIN_TOKEN)
s, d = api('GET', f'/api/history/month?year={year}&month={month}', token=ADMIN_TOKEN)
check('11.4 cycle_day=10: cycle_label has date range',
      '(' in d.get('cycle_label', ''),
      f"cycle_label={d.get('cycle_label')}")
check('11.5 cycle_dates shows range',
      '\u2013' in d.get('cycle_dates', '') or '-' in d.get('cycle_dates', ''),
      f"cycle_dates={d.get('cycle_dates')}")

# Reset
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)


# ═══════════════════════════════════════════════════════════
title('TEST 12: Adding payment via API uses correct cycle month')
# ═══════════════════════════════════════════════════════════

# Set cycle_day=20
api('PUT', '/api/family/settings', {'cycle_day': 20}, token=ADMIN_TOKEN)

# Add payment via API (should use get_cycle_month internally)
s, d = api('POST', '/api/payments/add', {
    'description': f'api_pay_{RND}', 'amount': 77, 'category': '\u05db\u05dc\u05dc\u05d9'
}, token=ADMIN_TOKEN)
check('12.1 Payment added via API', s == 201)

# Check which month it was assigned to
payments = get_payments(FID, archived=False)
api_pay = next((p for p in payments if f'api_pay_{RND}' in p['description']), None)
check('12.2 API payment exists', api_pay is not None)

# Today's day determines expected month
today = datetime.now()
if today.day >= 20:
    expected_month = f'{today.year}-{today.month:02d}'
else:
    prev = today.replace(day=1) - timedelta(days=1)
    expected_month = f'{prev.year}-{prev.month:02d}'

check('12.3 API payment assigned to correct cycle month',
      api_pay and api_pay['month'] == expected_month,
      f"got {api_pay['month'] if api_pay else 'N/A'}, expected {expected_month}")

# Reset
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)


# ═══════════════════════════════════════════════════════════
title('TEST 13: Multiple cycle_day changes — payments track correctly')
# ═══════════════════════════════════════════════════════════

# Start fresh: inject a payment on day 12
inject_payment(FID, f'day12_{RND}', 150,
               datetime(year, month, 12, 14, 0), f'{year}-{month:02d}')

# cycle_day=5 → day 12 >= 5 → current month
api('PUT', '/api/family/settings', {'cycle_day': 5}, token=ADMIN_TOKEN)
p = next((p for p in get_payments(FID, False) if f'day12_{RND}' in p['description']), None)
check('13.1 cycle_day=5: day 12 in current month',
      p and p['month'] == f'{year}-{month:02d}')

# cycle_day=15 → day 12 < 15 → previous month
api('PUT', '/api/family/settings', {'cycle_day': 15}, token=ADMIN_TOKEN)
p = next((p for p in get_payments(FID, False) if f'day12_{RND}' in p['description']), None)
check('13.2 cycle_day=15: day 12 in previous cycle',
      p and p['month'] == expected_prev,
      f"got {p['month'] if p else 'N/A'}")

# cycle_day=12 → day 12 >= 12 → current month
api('PUT', '/api/family/settings', {'cycle_day': 12}, token=ADMIN_TOKEN)
p = next((p for p in get_payments(FID, False) if f'day12_{RND}' in p['description']), None)
check('13.3 cycle_day=12: day 12 in current month (edge: day == cycle_day)',
      p and p['month'] == f'{year}-{month:02d}')

# cycle_day=13 → day 12 < 13 → previous month
api('PUT', '/api/family/settings', {'cycle_day': 13}, token=ADMIN_TOKEN)
p = next((p for p in get_payments(FID, False) if f'day12_{RND}' in p['description']), None)
check('13.4 cycle_day=13: day 12 in previous cycle (edge: day == cycle_day-1)',
      p and p['month'] == expected_prev,
      f"got {p['month'] if p else 'N/A'}")

# Reset
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)


# ═══════════════════════════════════════════════════════════
title('TEST 14: Dashboard daily average uses cycle days elapsed')
# ═══════════════════════════════════════════════════════════

# Set cycle_day=1 and check /api/home-summary or dashboard data
s, d = api('GET', '/api/home-summary', token=ADMIN_TOKEN)
check('14.1 Home summary returned', s == 200 and 'finance' in d)

# With cycle_day=1, days_elapsed = today's day of month
today = datetime.now()
finance = d.get('finance', {})
total = float(finance.get('total', 0))
daily_avg = float(finance.get('daily_average', 0))

if total > 0 and daily_avg > 0:
    # days_elapsed should be today's day
    implied_days = round(total / daily_avg)
    check('14.2 Daily avg implies correct days elapsed (cycle_day=1)',
          abs(implied_days - today.day) <= 1,
          f'implied_days={implied_days}, today.day={today.day}')
else:
    check('14.2 Daily avg (skipped - no data for calculation)', True)


# ═══════════════════════════════════════════════════════════
title('TEST 15: Cross-month payment injection')
# ═══════════════════════════════════════════════════════════

# Inject a payment from PREVIOUS month (day 28)
prev_dt = datetime(year, month, 1) - timedelta(days=3)  # ~day 28 of prev month
prev_month_str = prev_dt.strftime('%Y-%m')
inject_payment(FID, f'prev_month_{RND}', 400, prev_dt, prev_month_str)

# With cycle_day=1, it should stay in previous month
payments = get_payments(FID, archived=False)
prev_pay = next((p for p in payments if f'prev_month_{RND}' in p['description']), None)
check('15.1 Previous month payment injected', prev_pay is not None)
check('15.2 cycle_day=1: stays in previous calendar month',
      prev_pay and prev_pay['month'] == prev_month_str)

# Change to cycle_day=25: day 28 >= 25, so it should be in prev_month's cycle
api('PUT', '/api/family/settings', {'cycle_day': 25}, token=ADMIN_TOKEN)
prev_pay = next((p for p in get_payments(FID, False) if f'prev_month_{RND}' in p['description']), None)
check('15.3 cycle_day=25: day ~28 stays in that month cycle (>= 25)',
      prev_pay and prev_pay['month'] == prev_month_str,
      f"got {prev_pay['month'] if prev_pay else 'N/A'}")

# Reset
api('PUT', '/api/family/settings', {'cycle_day': 1}, token=ADMIN_TOKEN)


# ═══════════════════════════════════════════════════════════
title('TEST 16: Payment date uses Israel timezone (not UTC)')
# ═══════════════════════════════════════════════════════════

# Add a payment via API and check the date is in Israel time
s, d = api('POST', '/api/payments/add', {
    'description': f'tz_test_{RND}', 'amount': 42, 'category': '\u05db\u05dc\u05dc\u05d9'
}, token=ADMIN_TOKEN)
check('16.1 Payment added', s == 201)

# Read the payment from DB and check date
from zoneinfo import ZoneInfo
israel_now = datetime.now(ZoneInfo('Asia/Jerusalem'))
tz_payments = get_payments(FID, archived=False)
tz_pay = next((p for p in tz_payments if f'tz_test_{RND}' in p['description']), None)
check('16.2 Payment found in DB', tz_pay is not None)

if tz_pay:
    pay_date_str = tz_pay['date'].split('.')[0] if '.' in tz_pay['date'] else tz_pay['date']
    pay_date = datetime.strptime(pay_date_str, '%Y-%m-%d %H:%M:%S')
    # The payment date should match Israel date (not UTC)
    check('16.3 Payment date matches Israel date',
          pay_date.date() == israel_now.date(),
          f'payment date={pay_date.date()}, israel today={israel_now.date()}')
    # The hour should be close to Israel time (within 1 hour due to test execution time)
    hour_diff = abs(pay_date.hour - israel_now.hour)
    check('16.4 Payment hour is Israel time (not UTC)',
          hour_diff <= 1,
          f'payment hour={pay_date.hour}, israel hour={israel_now.hour}')


# ═══════════════════════════════════════════════════════════
title('CLEANUP')
# ═══════════════════════════════════════════════════════════

cleanup_user(MEMBER_USER)
cleanup_user(ADMIN_USER)
print('  \U0001f9f9 Test data cleaned')


# ═══════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════
print(f'\n{"=" * 60}')
print(f'  RESULTS: {PASS} passed, {FAIL} failed')
print(f'  Across 16 test groups')
print(f'{"=" * 60}\n')

if ERRORS:
    print('\u274c FAILURES:')
    for e in ERRORS:
        print(e)
    print()
else:
    print('\u2705 ALL CYCLE TESTS PASSED!\n')

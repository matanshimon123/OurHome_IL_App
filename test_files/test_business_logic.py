"""
Business-logic regression tests - OurHome IL  (Issue #22)

Three state machines that the existing suites never assert on:

  A. Budget-alert dedup - budget_alert_80_sent / budget_alert_100_sent and the
     daily marker budget_alert_daily_sent added by Issue #15. test_edge_cases.py
     crosses the thresholds but only asserts 201 on the add-payment calls, so a
     dedup regression (re-alerting on every payment) passes silently.
  B. Feeding-reminder dedup - check_feeding_reminders()'s
     (last_alert_feeding_id, last_alert_hours) state machine. Nothing anywhere
     exercises it.
  C. Cross-family WRITE authorization - read isolation is tested; nobody ever has
     a user of family C try to PUT/DELETE a row owned by family A.

Like test_security.py (Issue #21) this suite needs NO running Flask server and
NEVER touches the real database:
  * DATABASE_PATH points at a throwaway file in a tempfile.mkdtemp() directory
    BEFORE "import app" (init_db() runs at import and builds a fresh schema
    there); the run aborts if app.DATABASE ends up anywhere else;
  * everything is driven through Flask's in-process test client (no port, no
    network);
  * firebase_config is stubbed pre-import and send_push_to_family is replaced by
    a RECORDING stub - push counts are the primary assertion of parts A and B.

Three test-only patches, all documented where they are applied:
  1. now_israel() is replaced by a controllable clock, so "the next day" and "the
     next cycle month" are deterministic instead of wall-clock dependent.
  2. _acquire_scheduler_lease() is replaced by "main thread only", which keeps the
     two daemon scheduler loops started at import inert while the main thread
     drives the job body itself. (The lease is Issue #20's subject, not this
     file's.)
  3. For one tick of check_feeding_reminders(), time.sleep is replaced by a
     function that raises a BaseException subclass. The loop body is not factored
     out of "while True:", and its final time.sleep(60) sits OUTSIDE the inner
     "except Exception", so this runs the real body exactly once and returns.
     No copy of the logic is re-implemented here.

Run it from anywhere - it is cwd-independent:
    python test_files/test_business_logic.py

Exit code is 0 only when every test passes.
"""
import datetime as _dt
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import types
from datetime import datetime, timedelta

# Importing app prints emoji; reconfigure stdout so a piped/cp1255 console cannot
# crash the run. Everything this file prints itself is plain ASCII.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
REAL_DB = os.path.join(PROJECT_ROOT, 'finance_tracker.db')

# ═══════════════════════════════════════════════════════
# ISOLATED DATABASE - must be set up before "import app"
# ═══════════════════════════════════════════════════════
TEMP_DIR = tempfile.mkdtemp(prefix='ourhome_bizlogic_')
TEMP_DB = os.path.join(TEMP_DIR, 'test_business_logic.db')

os.environ['DATABASE_PATH'] = TEMP_DB
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
os.environ.pop('APP_ENV', None)
os.environ['SECRET_KEY'] = 'ourhome-business-logic-test-session-key-0123456789abcdef'
os.environ['JWT_SECRET'] = 'ourhome-business-logic-test-jwt-key-fedcba9876543210'

# Stub Firebase before app imports it - no network is possible from this file.
_fb = types.ModuleType('firebase_config')
_fb.firebase_create_user = lambda *a, **k: (None, 'stubbed')
_fb.firebase_verify_login = lambda *a, **k: (None, 'stubbed')
_fb.firebase_send_reset_email = lambda *a, **k: (False, 'stubbed')
_fb.firebase_update_password = lambda *a, **k: (False, 'stubbed')
sys.modules['firebase_config'] = _fb

sys.path.insert(0, PROJECT_ROOT)
import app as A  # noqa: E402  (must follow the env setup above)

# ── Hard safety gate: refuse to continue unless the app is on the temp DB ──
_resolved = os.path.abspath(A.DATABASE)
if _resolved != os.path.abspath(TEMP_DB) or not _resolved.startswith(os.path.abspath(TEMP_DIR)):
    print('ABORT: app.DATABASE is %r, expected %r' % (_resolved, TEMP_DB))
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    sys.exit(2)
if os.path.normcase(_resolved) == os.path.normcase(REAL_DB):
    print('ABORT: app.DATABASE points at the real database')
    sys.exit(2)

# ═══════════════════════════════════════════════════════
# RECORDING PUSH STUB  (no outbound push, ever)
# ═══════════════════════════════════════════════════════
# Every alert this app sends starts with a distinct emoji, so the recorder can
# classify pushes without embedding Hebrew in an otherwise-ASCII file. The
# codepoints are taken from the send_push_to_family() call sites in app.py.
KIND_BY_LEAD = {
    u'\U0001F6A8': 'budget_100',        # monthly over-budget
    u'⚠':     'budget_80',         # monthly 80%
    u'\U0001F4B8': 'budget_daily',      # daily over-budget (Issue #15)
    u'\U0001F37C': 'feeding_reminder',  # check_feeding_reminders
    u'\U0001F4B0': 'payment_add',
    u'✏':     'payment_update',
    u'\U0001F5D1': 'payment_delete',
    u'\U0001F6D2': 'shopping_add',
    u'\U0001F9F9': 'shopping_clear',
    u'\U0001F476': 'feeding_add',
    u'\U0001F4E6': 'recurring_add',
    u'\U0001F4CA': 'archive',
}

PUSHES = []


def _record_push(family_id, title, body, exclude_user_id=None, module=None):
    PUSHES.append({
        'thread': threading.current_thread().name,
        'fid': family_id,
        'kind': KIND_BY_LEAD.get((title or u' ')[0], 'UNKNOWN'),
        'title': title,
        'body': body,
        'module': module,
    })
    return 'recorded'


A.send_push_to_family = _record_push


def mark():
    return len(PUSHES)


def since(m, kind=None, fid=None, main_only=True):
    rows = PUSHES[m:]
    if main_only:
        rows = [p for p in rows if p['thread'] == threading.main_thread().name]
    if fid is not None:
        rows = [p for p in rows if p['fid'] == fid]
    if kind is not None:
        rows = [p for p in rows if p['kind'] == kind]
    return rows


def n(m, kind=None, fid=None):
    return len(since(m, kind, fid))


# ═══════════════════════════════════════════════════════
# TEST-ONLY PATCHES  (see the module docstring)
# ═══════════════════════════════════════════════════════
CLOCK = {'now': datetime(2026, 5, 14, 10, 30, 0)}
A.now_israel = lambda: CLOCK['now']


def set_clock(dt_):
    CLOCK['now'] = dt_
    return dt_


def advance(**kw):
    return set_clock(CLOCK['now'] + timedelta(**kw))


# Keep the two daemon scheduler loops (started at import) inert: they can never
# take the lease, so they cannot race the main thread's own job ticks.
A._acquire_scheduler_lease = lambda job_name, ttl_seconds: (
    threading.current_thread() is threading.main_thread())


class _StopTick(BaseException):
    """Not an Exception: the job body's inner 'except Exception' cannot swallow it."""


_real_sleep = time.sleep


def _sleep_raises(_seconds=0):
    raise _StopTick()


def feeding_tick():
    """Run the REAL body of check_feeding_reminders() exactly once."""
    time.sleep = _sleep_raises
    try:
        A.check_feeding_reminders()
    except _StopTick:
        pass
    finally:
        time.sleep = _real_sleep


# ═══════════════════════════════════════════════════════
# RESULT BOOKKEEPING
# ═══════════════════════════════════════════════════════
PASS = 0
FAIL = 0
ERRORS = []
NOTES = []


def check(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print('  [OK]   %s' % name + (' -- %s' % detail if detail else ''))
    else:
        FAIL += 1
        msg = '  [FAIL] %s' % name + (' -- %s' % detail if detail else '')
        ERRORS.append(msg)
        print(msg)


def note(text):
    NOTES.append(text)
    print('  [NOTE] %s' % text)


def title(t):
    print('\n%s' % ('=' * 66))
    print('  %s' % t)
    print('%s' % ('=' * 66))


# ═══════════════════════════════════════════════════════
# THROWAWAY-DB HELPERS
# ═══════════════════════════════════════════════════════
def db():
    """Connection to the THROWAWAY database only."""
    assert os.path.abspath(A.DATABASE).startswith(os.path.abspath(TEMP_DIR)), 'temp DB only'
    conn = sqlite3.connect(TEMP_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def seed_family(fam_name, code, username, **settings):
    c = db()
    fid = c.execute('INSERT INTO families (name, invite_code, created_by) VALUES (?,?,NULL)',
                    (fam_name, code)).lastrowid
    uid = c.execute(
        'INSERT INTO users (username,email,display_name,password_hash,firebase_uid,family_id,is_admin) '
        'VALUES (?,?,?,?,?,?,0)',
        (username, '%s@example.invalid' % username, username.title(), 'x', '', fid)).lastrowid
    c.execute('UPDATE families SET created_by=? WHERE id=?', (uid, fid))
    c.execute('INSERT INTO family_settings (family_id) VALUES (?)', (fid,))
    for k, v in settings.items():
        c.execute('UPDATE family_settings SET %s=? WHERE family_id=?' % k, (v, fid))
    c.commit()
    c.close()
    tok = A.create_jwt_token(uid, username, username.title(), fid, False)
    if isinstance(tok, bytes):
        tok = tok.decode()
    return fid, uid, tok


def fs(fid):
    """family_settings row as a plain dict."""
    c = db()
    row = c.execute('SELECT * FROM family_settings WHERE family_id=?', (fid,)).fetchone()
    c.close()
    return dict(row) if row else None


def set_fs(fid, **cols):
    c = db()
    for k, v in cols.items():
        c.execute('UPDATE family_settings SET %s=? WHERE family_id=?' % k, (v, fid))
    c.commit()
    c.close()


def row(table, rid):
    c = db()
    r = c.execute('SELECT * FROM %s WHERE id=?' % table, (rid,)).fetchone()
    c.close()
    return dict(r) if r else None


def insert_feeding(fid, when, ftype='bottle', amount=120):
    c = db()
    rid = c.execute(
        'INSERT INTO feedings (family_id,feeding_type,amount,duration,notes,date) VALUES (?,?,?,0,?,?)',
        (fid, ftype, amount, '', when.strftime('%Y-%m-%d %H:%M:%S'))).lastrowid
    c.commit()
    c.close()
    return rid


def api(token, method, path, body=None):
    """One request on a FRESH client.

    A fresh client every time is essential: auto_jwt_auth() populates the Flask
    session on success, so a reused client could authenticate a later request by
    cookie and mask a rejected token.
    """
    cl = A.app.test_client()
    headers = {'Content-Type': 'application/json'}
    if token is not None:
        headers['Authorization'] = 'Bearer %s' % token
    kw = {'headers': headers}
    if body is not None:
        kw['data'] = json.dumps(body)
    return getattr(cl, method.lower())(path, **kw)


def add_payment(token, desc, amount):
    return api(token, 'POST', '/api/payments/add', {'description': desc, 'amount': amount})


print('=' * 66)
print('  OurHome IL - BUSINESS LOGIC REGRESSION TESTS (Issue #22)')
print('=' * 66)
print('  temp dir : %s' % TEMP_DIR)
print('  temp DB  : %s' % TEMP_DB)
print('  app.DATABASE resolves to: %s' % _resolved)
print('  real DB  : %s  (never opened by this file)' % REAL_DB)
print('  clock    : pinned to %s (now_israel is patched)' % CLOCK['now'])
print('  archive thread alive: %s | reminder thread alive: %s'
      % (getattr(A, '_archive_thread', None) and A._archive_thread.is_alive(),
         getattr(A, '_reminder_thread', None) and A._reminder_thread.is_alive()))

try:
    check('app.DATABASE is inside the temp dir (real DB untouched)',
          _resolved.startswith(os.path.abspath(TEMP_DIR)), _resolved)

    # ═══════════════════════════════════════════════════════
    title('A1. MONTHLY BUDGET ALERTS - 80% / 100% dedup markers')
    # ═══════════════════════════════════════════════════════
    # budget_daily stays 0 here so only the monthly branch can fire.
    MFID, MUID, MTOK = seed_family('BudgetMonthly', 'BGM001', 'budmonth',
                                   budget_monthly=1000, budget_daily=0)
    CM1 = A.get_cycle_month(MFID)
    print('  family_id=%d  cycle_month=%s  budget_monthly=1000' % (MFID, CM1))

    s = fs(MFID)
    check('Fresh family: both monthly markers start empty',
          (s['budget_alert_80_sent'] or '') == '' and (s['budget_alert_100_sent'] or '') == '',
          '80=%r 100=%r' % (s['budget_alert_80_sent'], s['budget_alert_100_sent']))

    # --- 70%: below both thresholds ---
    m = mark()
    r = add_payment(MTOK, 'below-threshold', 700)
    s = fs(MFID)
    check('700/1000 (70%) -> 201, no budget push, markers still empty',
          r.status_code == 201 and n(m, 'budget_80') == 0 and n(m, 'budget_100') == 0
          and (s['budget_alert_80_sent'] or '') == '' and (s['budget_alert_100_sent'] or '') == '',
          'status=%s pushes80=%d pushes100=%d' % (r.status_code, n(m, 'budget_80'), n(m, 'budget_100')))
    check('CONTROL: the add-payment push itself was recorded (classifier works)',
          n(m, 'payment_add') == 1, 'payment_add pushes=%d' % n(m, 'payment_add'))

    # --- crossing 80% ---
    m = mark()
    r = add_payment(MTOK, 'crosses-80', 150)   # total 850 = 85%
    s = fs(MFID)
    check('850/1000 (85%) -> EXACTLY ONE 80% push',
          n(m, 'budget_80') == 1, 'pushes=%d' % n(m, 'budget_80'))
    check('850/1000 (85%) -> budget_alert_80_sent == cycle month',
          s['budget_alert_80_sent'] == CM1, 'marker=%r want %r' % (s['budget_alert_80_sent'], CM1))
    check('850/1000 (85%) -> no 100% push and the 100% marker stays empty',
          n(m, 'budget_100') == 0 and (s['budget_alert_100_sent'] or '') == '',
          'pushes=%d marker=%r' % (n(m, 'budget_100'), s['budget_alert_100_sent']))

    # --- THE DEDUP CASE: still >=80%, still <100% ---
    m = mark()
    r = add_payment(MTOK, 'still-over-80', 50)    # total 900 = 90%
    r2 = add_payment(MTOK, 'still-over-80-again', 20)   # total 920 = 92%
    s2 = fs(MFID)
    check('DEDUP: two more payments at 90%/92% fire NO second 80% push',
          n(m, 'budget_80') == 0, 'extra 80%% pushes=%d' % n(m, 'budget_80'))
    check('DEDUP: budget_alert_80_sent is unchanged by those payments',
          s2['budget_alert_80_sent'] == s['budget_alert_80_sent'],
          'before=%r after=%r' % (s['budget_alert_80_sent'], s2['budget_alert_80_sent']))
    check('DEDUP: still no 100% push below 100%',
          n(m, 'budget_100') == 0, 'pushes=%d' % n(m, 'budget_100'))

    # --- crossing 100% ---
    m = mark()
    r = add_payment(MTOK, 'crosses-100', 130)   # total 1050 = 105%
    s = fs(MFID)
    check('1050/1000 (105%) -> EXACTLY ONE 100% push',
          n(m, 'budget_100') == 1, 'pushes=%d' % n(m, 'budget_100'))
    check('1050/1000 (105%) -> budget_alert_100_sent == cycle month',
          s['budget_alert_100_sent'] == CM1, 'marker=%r want %r' % (s['budget_alert_100_sent'], CM1))
    check('1050/1000 (105%) -> no extra 80% push (the branches are exclusive)',
          n(m, 'budget_80') == 0, 'pushes=%d' % n(m, 'budget_80'))

    # --- THE DEDUP CASE: still over 100% ---
    m = mark()
    add_payment(MTOK, 'way-over-1', 100)   # 1150
    add_payment(MTOK, 'way-over-2', 100)   # 1250
    add_payment(MTOK, 'way-over-3', 100)   # 1350
    s2 = fs(MFID)
    check('DEDUP: three more payments over budget fire NO further budget push',
          n(m, 'budget_100') == 0 and n(m, 'budget_80') == 0,
          '100%%=%d 80%%=%d' % (n(m, 'budget_100'), n(m, 'budget_80')))
    check('DEDUP: both monthly markers unchanged while over budget',
          s2['budget_alert_80_sent'] == s['budget_alert_80_sent']
          and s2['budget_alert_100_sent'] == s['budget_alert_100_sent'],
          '80=%r 100=%r' % (s2['budget_alert_80_sent'], s2['budget_alert_100_sent']))

    # --- a PUT that keeps the family over budget also must not re-alert ---
    c = db()
    _pid = c.execute('SELECT id FROM payments WHERE family_id=? ORDER BY id DESC LIMIT 1',
                     (MFID,)).fetchone()[0]
    c.close()
    m = mark()
    r = api(MTOK, 'PUT', '/api/payments/%d' % _pid, {'amount': 120})
    check('DEDUP: PUT /api/payments/<id> while over budget fires no budget push',
          n(m, 'budget_100') == 0 and n(m, 'budget_80') == 0,
          'status=%s 100%%=%d 80%%=%d' % (r.status_code, n(m, 'budget_100'), n(m, 'budget_80')))

    # ═══════════════════════════════════════════════════════
    title('A2. MONTHLY BUDGET ALERTS - a new cycle month re-arms both alerts')
    # ═══════════════════════════════════════════════════════
    set_clock(datetime(2026, 6, 12, 9, 0, 0))
    CM2 = A.get_cycle_month(MFID)
    check('Clock moved to the next cycle month', CM2 != CM1, '%s -> %s' % (CM1, CM2))
    s = fs(MFID)
    check('Markers still hold the OLD cycle month (nothing reset them)',
          s['budget_alert_80_sent'] == CM1 and s['budget_alert_100_sent'] == CM1,
          '80=%r 100=%r' % (s['budget_alert_80_sent'], s['budget_alert_100_sent']))

    m = mark()
    add_payment(MTOK, 'new-cycle-85pct', 850)
    s = fs(MFID)
    check('New cycle, 850/1000 -> the 80% alert fires again (exactly once)',
          n(m, 'budget_80') == 1, 'pushes=%d' % n(m, 'budget_80'))
    check('New cycle -> budget_alert_80_sent advanced to the new cycle month',
          s['budget_alert_80_sent'] == CM2, 'marker=%r want %r' % (s['budget_alert_80_sent'], CM2))
    check('New cycle -> budget_alert_100_sent still holds the old month',
          s['budget_alert_100_sent'] == CM1, 'marker=%r' % s['budget_alert_100_sent'])

    m = mark()
    add_payment(MTOK, 'new-cycle-120pct', 350)   # 1200
    s = fs(MFID)
    check('New cycle, 1200/1000 -> the 100% alert fires again (exactly once)',
          n(m, 'budget_100') == 1, 'pushes=%d' % n(m, 'budget_100'))
    check('New cycle -> budget_alert_100_sent advanced to the new cycle month',
          s['budget_alert_100_sent'] == CM2, 'marker=%r want %r' % (s['budget_alert_100_sent'], CM2))

    m = mark()
    add_payment(MTOK, 'new-cycle-still-over', 100)
    check('DEDUP holds in the new cycle too: no further budget push',
          n(m, 'budget_100') == 0 and n(m, 'budget_80') == 0,
          '100%%=%d 80%%=%d' % (n(m, 'budget_100'), n(m, 'budget_80')))

    # ═══════════════════════════════════════════════════════
    title('A3. DAILY BUDGET ALERT DEDUP (Issue #15) - budget_alert_daily_sent')
    # ═══════════════════════════════════════════════════════
    # budget_monthly stays 0 here so only the daily branch can fire.
    DFID, DUID, DTOK = seed_family('BudgetDaily', 'BGD001', 'budday',
                                   budget_monthly=0, budget_daily=100)
    set_clock(datetime(2026, 5, 20, 8, 0, 0))
    DAY1 = CLOCK['now'].strftime('%Y-%m-%d')
    print('  family_id=%d  day=%s  budget_daily=100' % (DFID, DAY1))

    m = mark()
    add_payment(DTOK, 'daily-under', 60)
    s = fs(DFID)
    check('60/100 for the day -> no daily push, marker empty',
          n(m, 'budget_daily') == 0 and (s['budget_alert_daily_sent'] or '') == '',
          'pushes=%d marker=%r' % (n(m, 'budget_daily'), s['budget_alert_daily_sent']))

    m = mark()
    add_payment(DTOK, 'daily-crosses', 60)   # 120 > 100
    s = fs(DFID)
    check('120/100 for the day -> EXACTLY ONE daily push',
          n(m, 'budget_daily') == 1, 'pushes=%d' % n(m, 'budget_daily'))
    check('120/100 -> budget_alert_daily_sent == today (Issue #15 marker)',
          s['budget_alert_daily_sent'] == DAY1,
          'marker=%r want %r' % (s['budget_alert_daily_sent'], DAY1))

    m = mark()
    add_payment(DTOK, 'daily-more-1', 30)
    add_payment(DTOK, 'daily-more-2', 30)
    s2 = fs(DFID)
    check('DEDUP (Issue #15): two more payments the same day fire NO daily push',
          n(m, 'budget_daily') == 0, 'pushes=%d' % n(m, 'budget_daily'))
    check('DEDUP (Issue #15): budget_alert_daily_sent unchanged',
          s2['budget_alert_daily_sent'] == DAY1, 'marker=%r' % s2['budget_alert_daily_sent'])

    # Method 1 - backdate the marker, clock unchanged. Only the marker gates it.
    set_fs(DFID, budget_alert_daily_sent='2026-05-19')
    m = mark()
    A.check_budget_alerts(DFID)
    s = fs(DFID)
    m1_pushes = n(m, 'budget_daily')
    check('Day rollover, method 1 (stale marker) -> EXACTLY ONE daily push',
          m1_pushes == 1, 'pushes=%d' % m1_pushes)
    check('Day rollover, method 1 -> marker rewritten to today',
          s['budget_alert_daily_sent'] == DAY1, 'marker=%r' % s['budget_alert_daily_sent'])
    m = mark()
    A.check_budget_alerts(DFID)
    check('Day rollover, method 1 -> a second run right after fires nothing',
          n(m, 'budget_daily') == 0, 'pushes=%d' % n(m, 'budget_daily'))

    # Method 2 - advance the clock a real day. The marker is left at DAY1.
    set_clock(datetime(2026, 5, 21, 9, 0, 0))
    DAY2 = CLOCK['now'].strftime('%Y-%m-%d')
    m = mark()
    A.check_budget_alerts(DFID)
    check('Day rollover, method 2: new day with no spending yet -> no push',
          n(m, 'budget_daily') == 0, 'pushes=%d' % n(m, 'budget_daily'))
    m = mark()
    add_payment(DTOK, 'day2-crosses', 150)
    s = fs(DFID)
    m2_pushes = n(m, 'budget_daily')
    check('Day rollover, method 2 (clock advanced) -> EXACTLY ONE daily push',
          m2_pushes == 1, 'pushes=%d' % m2_pushes)
    check('Day rollover, method 2 -> marker == the NEW day',
          s['budget_alert_daily_sent'] == DAY2,
          'marker=%r want %r' % (s['budget_alert_daily_sent'], DAY2))
    m = mark()
    add_payment(DTOK, 'day2-more', 40)
    check('DEDUP on day 2: a further payment the same day fires nothing',
          n(m, 'budget_daily') == 0, 'pushes=%d' % n(m, 'budget_daily'))
    check('The two day-rollover methods agree: exactly one alert each',
          m1_pushes == m2_pushes == 1, 'method1=%d method2=%d' % (m1_pushes, m2_pushes))

    # The daily branch is strictly ">" - pin that, a regression to ">=" would alert
    # every family that lands exactly on its budget.
    EFID, EUID, ETOK = seed_family('BudgetEqual', 'BGE001', 'budequal',
                                   budget_monthly=0, budget_daily=100)
    m = mark()
    add_payment(ETOK, 'exactly-budget', 100)
    check('Daily total EXACTLY equal to the budget -> no daily push (strict >)',
          n(m, 'budget_daily') == 0, 'pushes=%d' % n(m, 'budget_daily'))

    # ═══════════════════════════════════════════════════════
    title('B. FEEDING-REMINDER DEDUP - last_alert_feeding_id / last_alert_hours')
    # ═══════════════════════════════════════════════════════
    T0 = set_clock(datetime(2026, 5, 20, 8, 0, 0))
    FFID, FUID, FTOK = seed_family('FeedFam', 'FED001', 'feeder', feeding_reminder_hours=3.0)
    print('  family_id=%d  feeding_reminder_hours=3.0  clock=%s' % (FFID, T0))

    F1 = insert_feeding(FFID, T0 - timedelta(hours=4))
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('Latest feeding 4h old, threshold 3h -> EXACTLY ONE reminder push',
          n(m, 'feeding_reminder') == 1, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('Alert state recorded: last_alert_feeding_id == the feeding id',
          s['last_alert_feeding_id'] == F1, 'stored=%r want %r' % (s['last_alert_feeding_id'], F1))
    check('Alert state recorded: last_alert_hours == the threshold',
          float(s['last_alert_hours']) == 3.0, 'stored=%r' % s['last_alert_hours'])
    check('last_feeding_alert timestamp written',
          bool(s['last_feeding_alert']), 'value=%r' % s['last_feeding_alert'])

    # --- THE DEDUP CASE: tick again, nothing changed ---
    m = mark()
    feeding_tick()
    s2 = fs(FFID)
    check('DEDUP: an immediate second tick with no new feeding fires NOTHING',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('DEDUP: the alert state is unchanged by the second tick',
          s2['last_alert_feeding_id'] == F1 and float(s2['last_alert_hours']) == 3.0,
          'fid=%r hours=%r' % (s2['last_alert_feeding_id'], s2['last_alert_hours']))

    # --- ANTI-SPAM: the job really runs every 60s. 20 idle ticks over 20 minutes. ---
    m = mark()
    for _ in range(20):
        advance(minutes=1)
        feeding_tick()
    check('ANTI-SPAM: 20 consecutive idle ticks (20 simulated minutes) fire NOTHING',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    # --- a NEWER feeding, still inside the threshold ---
    set_clock(T0 + timedelta(hours=1))
    F2 = insert_feeding(FFID, T0 + timedelta(minutes=30))
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('A new feeding 30min ago (threshold 3h) -> no push yet',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('...and the alert state still points at the OLD feeding',
          s['last_alert_feeding_id'] == F1, 'stored=%r' % s['last_alert_feeding_id'])

    # --- wait past the interval: exactly one more push, state moves to F2 ---
    set_clock(T0 + timedelta(hours=4))    # F2 is now 3.5h old
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('Once the new feeding is 3.5h old -> EXACTLY ONE more reminder',
          n(m, 'feeding_reminder') == 1, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('last_alert_feeding_id moved to the NEW feeding',
          s['last_alert_feeding_id'] == F2, 'stored=%r want %r' % (s['last_alert_feeding_id'], F2))
    m = mark()
    feeding_tick()
    check('DEDUP: the very next tick fires nothing again',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    # --- changing the threshold re-arms the SAME feeding (that is what last_alert_hours is for) ---
    set_clock(T0 + timedelta(hours=5))
    m = mark()
    feeding_tick()
    check('Still the same (feeding, hours) state one hour later -> nothing',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    set_fs(FFID, feeding_reminder_hours=2.0)
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('Changing feeding_reminder_hours 3.0 -> 2.0 RE-ARMS the same feeding: one push',
          n(m, 'feeding_reminder') == 1, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('last_alert_hours updated to the new threshold, feeding id unchanged',
          float(s['last_alert_hours']) == 2.0 and s['last_alert_feeding_id'] == F2,
          'hours=%r fid=%r' % (s['last_alert_hours'], s['last_alert_feeding_id']))
    m = mark()
    feeding_tick()
    check('DEDUP on the new (feeding, hours) state: the next tick fires nothing',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    # --- reminder disabled ---
    set_fs(FFID, feeding_reminder_hours=0)
    m = mark()
    advance(hours=6)
    feeding_tick()
    check('feeding_reminder_hours = 0 -> nothing fires, however long it has been',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    set_fs(FFID, feeding_reminder_hours=None)
    m = mark()
    feeding_tick()
    check('feeding_reminder_hours = NULL -> nothing fires',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    set_fs(FFID, feeding_reminder_hours=2.0)
    m = mark()
    feeding_tick()
    check('Re-enabling the same threshold does NOT re-spam (state is still (F2, 2.0))',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))

    # --- retroactive entry OLDER than the latest feeding: must not spam ---
    T_NOW = CLOCK['now']
    F_OLD = insert_feeding(FFID, T0 - timedelta(hours=6))
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('RETROACTIVE: logging a forgotten feeding OLDER than the latest -> no push',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('RETROACTIVE: the alert state is untouched by the older entry',
          s['last_alert_feeding_id'] == F2, 'stored=%r' % s['last_alert_feeding_id'])

    # --- a newer NON-feeding entry (diaper) must not count as a feeding ---
    F_DIAPER = insert_feeding(FFID, T_NOW - timedelta(minutes=5), ftype='diaper', amount=0)
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('A diaper logged 5min ago is not a feeding -> no state change, no push',
          n(m, 'feeding_reminder') == 0 and s['last_alert_feeding_id'] == F2,
          'pushes=%d fid=%r' % (n(m, 'feeding_reminder'), s['last_alert_feeding_id']))

    # --- retroactive entry that is NEWER than the latest but already past the threshold ---
    F3 = insert_feeding(FFID, T_NOW - timedelta(hours=3))
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('RETROACTIVE past the threshold -> fires exactly once (actual behaviour)',
          n(m, 'feeding_reminder') == 1, 'pushes=%d' % n(m, 'feeding_reminder'))
    check('...and it is a NEW state, so it is capped at one alert',
          s['last_alert_feeding_id'] == F3, 'stored=%r want %r' % (s['last_alert_feeding_id'], F3))
    m = mark()
    for _ in range(5):
        advance(minutes=1)
        feeding_tick()
    check('RETROACTIVE: five further ticks after it fire NOTHING (no spam)',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))
    note('check_feeding_reminders docstring says "Retroactive feeding past threshold -> does NOT '
         'alert (parent forgot to log)". The code DOES alert once in that case (asserted above). '
         'The docstring and the behaviour disagree; the anti-spam guarantee itself holds.')

    # --- EDITING a feeding's time recalculates, and never spams ---
    r = api(FTOK, 'PUT', '/api/feedings/%d' % F3,
            {'time': (CLOCK['now'] - timedelta(minutes=15)).strftime('%H:%M')})
    m = mark()
    feeding_tick()
    check('EDIT: moving a feeding forward to 15min ago -> no push (recalculated, not due)',
          r.status_code == 200 and n(m, 'feeding_reminder') == 0,
          'status=%s pushes=%d' % (r.status_code, n(m, 'feeding_reminder')))
    m = mark()
    advance(hours=3)
    feeding_tick()
    s = fs(FFID)
    check('EDIT: 3h after the edited time the SAME feeding id does not re-alert',
          n(m, 'feeding_reminder') == 0 and s['last_alert_feeding_id'] == F3,
          'pushes=%d fid=%r' % (n(m, 'feeding_reminder'), s['last_alert_feeding_id']))
    note('Consequence of the state being (feeding_id, hours): once a feeding has alerted, '
         'editing its time forward cannot re-arm it, so that one reminder is silently lost. '
         'Bounded (the next logged feeding re-arms normally - proved by the control below).')

    # --- CONTROL: the machine still alerts for a genuinely new feeding ---
    F4 = insert_feeding(FFID, CLOCK['now'] - timedelta(minutes=10))
    m = mark()
    feeding_tick()
    check('CONTROL: a brand-new feeding 10min ago -> not due yet, no push',
          n(m, 'feeding_reminder') == 0, 'pushes=%d' % n(m, 'feeding_reminder'))
    advance(hours=3)
    m = mark()
    feeding_tick()
    s = fs(FFID)
    check('CONTROL: 3h later the new feeding alerts exactly once',
          n(m, 'feeding_reminder') == 1 and s['last_alert_feeding_id'] == F4,
          'pushes=%d fid=%r' % (n(m, 'feeding_reminder'), s['last_alert_feeding_id']))

    # --- a family with the reminder on but no feedings at all ---
    NFID, NUID, NTOK = seed_family('NoFeedFam', 'NOF001', 'nofeed', feeding_reminder_hours=1.0)
    m = mark()
    feeding_tick()
    check('A family with the reminder on but zero feedings -> no push, no state',
          n(m, 'feeding_reminder', fid=NFID) == 0 and fs(NFID)['last_alert_feeding_id'] is None,
          'pushes=%d' % n(m, 'feeding_reminder', fid=NFID))

    # ═══════════════════════════════════════════════════════
    title('C. CROSS-FAMILY WRITE AUTHORIZATION - family C vs family A rows')
    # ═══════════════════════════════════════════════════════
    set_clock(datetime(2026, 5, 22, 12, 0, 0))
    AFID, AUID, ATOK = seed_family('FamilyA', 'FAMA01', 'alice')
    CFID, CUID, CTOK = seed_family('FamilyC', 'FAMC01', 'carol')
    print('  victim family_id=%d (alice)   attacker family_id=%d (carol)' % (AFID, CFID))

    # Seed one row of each kind, owned by family A, through A's own API.
    add_payment(ATOK, 'A-rent', 42.5)
    c = db()
    A_PAY = c.execute('SELECT id FROM payments WHERE family_id=? ORDER BY id DESC LIMIT 1',
                      (AFID,)).fetchone()[0]
    c.close()
    api(ATOK, 'POST', '/api/recurring', {'description': 'A-netflix', 'amount': 55, 'category': 'A-cat'})
    c = db()
    A_REC = c.execute('SELECT id FROM recurring_payments WHERE family_id=? ORDER BY id DESC LIMIT 1',
                      (AFID,)).fetchone()[0]
    c.close()
    A_FEED = api(ATOK, 'POST', '/api/feedings',
                 {'feeding_type': 'bottle', 'amount': 90, 'duration': 0}).get_json()['id']
    A_ITEM = api(ATOK, 'POST', '/api/shopping-items',
                 {'name': 'A-milk', 'quantity': 2, 'category': 'A-dairy'}).get_json()['id']
    print('  family A rows: payment=%d recurring=%d feeding=%d shopping_item=%d'
          % (A_PAY, A_REC, A_FEED, A_ITEM))

    ATTACKS = [
        ('payments', A_PAY, '/api/payments/%d' % A_PAY,
         {'description': 'HACKED', 'amount': 99999, 'category': 'HACKED'}),
        ('recurring_payments', A_REC, '/api/recurring/%d' % A_REC,
         {'description': 'HACKED', 'amount': 99999, 'category': 'HACKED'}),
        ('feedings', A_FEED, '/api/feedings/%d' % A_FEED,
         {'amount': 99999, 'notes': 'HACKED', 'time': '23:59'}),
        ('shopping_items', A_ITEM, '/api/shopping-items/%d' % A_ITEM,
         {'name': 'HACKED', 'quantity': 99, 'checked': True, 'category': 'HACKED'}),
    ]

    for table, rid, path, payload in ATTACKS:
        before = row(table, rid)
        check('SETUP: %s row %d exists and belongs to family A' % (table, rid),
              before is not None and before['family_id'] == AFID,
              'family_id=%r' % (before and before['family_id']))

        r = api(CTOK, 'PUT', path, payload)
        after = row(table, rid)
        check('Family C PUT %s -> A\'s row is byte-identical' % path,
              after == before, 'status=%s (informational) | row changed=%s'
              % (r.status_code, after != before))

        r = api(CTOK, 'DELETE', path)
        after = row(table, rid)
        check('Family C DELETE %s -> A\'s row still present and unchanged' % path,
              after is not None and after == before,
              'status=%s (informational) | present=%s unchanged=%s'
              % (r.status_code, after is not None, after == before))

    # Nothing of C's own was created or destroyed by any of that.
    c = db()
    c_counts = {t: c.execute('SELECT COUNT(*) FROM %s WHERE family_id=?' % t, (CFID,)).fetchone()[0]
                for t in ('payments', 'recurring_payments', 'feedings', 'shopping_items')}
    c.close()
    check('Family C still owns nothing (the attacks did not create rows for C either)',
          all(v == 0 for v in c_counts.values()), '%s' % c_counts)

    # A cross-family write must not even reach the push layer for the victim family.
    m = mark()
    api(CTOK, 'PUT', '/api/payments/%d' % A_PAY, {'description': 'HACKED-AGAIN', 'amount': 1})
    check('A cross-family PUT sends no push to the victim family',
          n(m, fid=AFID) == 0, 'pushes to family A=%d' % n(m, fid=AFID))

    # ── CONTROLS: the owner CAN do exactly what family C could not ──
    before = row('payments', A_PAY)
    r = api(ATOK, 'PUT', '/api/payments/%d' % A_PAY, {'description': 'A-rent-updated', 'amount': 50})
    after = row('payments', A_PAY)
    check('CONTROL: family A CAN update its own payment (the tests above are not vacuous)',
          r.status_code == 200 and after['description'] == 'A-rent-updated' and after != before,
          'status=%s desc=%r' % (r.status_code, after['description']))

    before = row('recurring_payments', A_REC)
    r = api(ATOK, 'PUT', '/api/recurring/%d' % A_REC,
            {'description': 'A-netflix-updated', 'amount': 60, 'category': 'A-cat'})
    after = row('recurring_payments', A_REC)
    check('CONTROL: family A CAN update its own recurring payment',
          r.status_code == 200 and after['description'] == 'A-netflix-updated',
          'status=%s desc=%r' % (r.status_code, after['description']))

    r = api(ATOK, 'PUT', '/api/shopping-items/%d' % A_ITEM, {'name': 'A-milk-updated'})
    check('CONTROL: family A CAN update its own shopping item',
          r.status_code == 200 and row('shopping_items', A_ITEM)['name'] == 'A-milk-updated',
          'status=%s' % r.status_code)

    r = api(ATOK, 'PUT', '/api/feedings/%d' % A_FEED, {'amount': 111})
    check('CONTROL: family A CAN update its own feeding',
          r.status_code == 200 and float(row('feedings', A_FEED)['amount']) == 111.0,
          'status=%s' % r.status_code)

    r = api(ATOK, 'DELETE', '/api/payments/%d' % A_PAY)
    check('CONTROL: family A CAN delete its own payment',
          r.status_code == 200 and row('payments', A_PAY) is None, 'status=%s' % r.status_code)
    r = api(ATOK, 'DELETE', '/api/recurring/%d' % A_REC)
    check('CONTROL: family A CAN delete its own recurring payment',
          r.status_code == 200 and row('recurring_payments', A_REC) is None, 'status=%s' % r.status_code)
    r = api(ATOK, 'DELETE', '/api/feedings/%d' % A_FEED)
    check('CONTROL: family A CAN delete its own feeding',
          r.status_code == 200 and row('feedings', A_FEED) is None, 'status=%s' % r.status_code)
    r = api(ATOK, 'DELETE', '/api/shopping-items/%d' % A_ITEM)
    check('CONTROL: family A CAN delete its own shopping item',
          r.status_code == 200 and row('shopping_items', A_ITEM) is None, 'status=%s' % r.status_code)

    # ═══════════════════════════════════════════════════════
    title('D. HARNESS SELF-CHECKS')
    # ═══════════════════════════════════════════════════════
    unknown = [p for p in PUSHES if p['kind'] == 'UNKNOWN']
    check('Every recorded push was classified (no UNKNOWN kinds)',
          not unknown, '%d unknown: %r' % (len(unknown), [p['title'] for p in unknown[:3]]))
    bg = [p for p in PUSHES if p['thread'] != threading.main_thread().name]
    check('No push came from a background scheduler thread (no race with the assertions)',
          not bg, '%d background pushes: %r' % (len(bg), [(p['thread'], p['kind']) for p in bg[:3]]))
    check('The real database was never opened by this process',
          not os.path.exists(REAL_DB + '-wal') and not os.path.exists(REAL_DB + '-shm'),
          'no -wal/-shm beside %s' % REAL_DB)
    print('  total pushes recorded: %d' % len(PUSHES))

finally:
    # ═══════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════
    print('\n%s' % ('=' * 66))
    print('  RESULTS: %d passed, %d failed' % (PASS, FAIL))
    print('%s' % ('=' * 66))
    if ERRORS:
        print('\nFAILURES:')
        for e in ERRORS:
            print(e)
    else:
        print('\nALL TESTS PASSED - budget dedup, feeding-reminder dedup and')
        print('cross-family write authorization are covered.')
    if NOTES:
        print('\nNOTES (behaviour asserted as-is, worth a human look):')
        for i, t in enumerate(NOTES, 1):
            print('  %d. %s' % (i, t))

    # Best-effort cleanup; a daemon scheduler thread may still hold the file on Windows.
    time.sleep = _real_sleep
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    print('\n  cleaned up temp dir: %s (still present: %s)'
          % (TEMP_DIR, os.path.exists(TEMP_DIR)))
    print()

sys.exit(1 if FAIL else 0)

"""
Security regression tests — OurHome IL  (Issue #21)

Forged/expired/unsigned JWTs must be rejected, and CSRF must actually block a
token-less POST to a web (non-/api/) route.

Unlike the other suites in this folder, this one needs NO running Flask server and
NEVER touches the real database:
  * it sets DATABASE_PATH to a throwaway file in a tempfile.mkdtemp() directory
    BEFORE importing app (init_db() runs at import time and builds a fresh schema
    there), and refuses to run if app.DATABASE ends up anywhere else;
  * it drives the app through Flask's in-process test client (no port, no network);
  * firebase_config is stubbed and send_push_to_family is neutralized.

Run it from anywhere - it is cwd-independent:
    python test_files/test_security.py

Exit code is 0 only when every test passes.
"""
import base64
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone

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
# ISOLATED DATABASE — must be set up before "import app"
# ═══════════════════════════════════════════════════════
TEMP_DIR = tempfile.mkdtemp(prefix='ourhome_sectest_')
TEMP_DB = os.path.join(TEMP_DIR, 'test_security.db')

os.environ['DATABASE_PATH'] = TEMP_DB
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
# Deterministic secrets so the "wrong secret" test can never accidentally collide
# with the developer's environment. APP_ENV stays unset (development).
os.environ.pop('APP_ENV', None)
os.environ['SECRET_KEY'] = 'ourhome-security-regression-test-session-key-0123456789abcdef'
os.environ['JWT_SECRET'] = 'ourhome-security-regression-test-jwt-key-fedcba9876543210'
WRONG_SECRET = 'attacker-guessed-this-secret-instead'

# Stub Firebase before app imports it — no network is possible from this file.
_fb = types.ModuleType('firebase_config')
_fb.firebase_create_user = lambda *a, **k: (None, 'stubbed')
_fb.firebase_verify_login = lambda *a, **k: (None, 'stubbed')
_fb.firebase_send_reset_email = lambda *a, **k: (False, 'stubbed')
_fb.firebase_update_password = lambda *a, **k: (False, 'stubbed')
sys.modules['firebase_config'] = _fb

sys.path.insert(0, PROJECT_ROOT)
import app as A  # noqa: E402  (must follow the env setup above)
import jwt as pyjwt  # noqa: E402

# No outbound push, ever.
A.send_push_to_family = lambda *a, **k: 'stubbed'

# ── Hard safety gate: refuse to continue unless the app is on the temp DB ──
_resolved = os.path.abspath(A.DATABASE)
if _resolved != os.path.abspath(TEMP_DB) or not _resolved.startswith(os.path.abspath(TEMP_DIR)):
    print('ABORT: app.DATABASE is %r, expected %r' % (_resolved, TEMP_DB))
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    sys.exit(2)
if os.path.normcase(_resolved) == os.path.normcase(REAL_DB):
    print('ABORT: app.DATABASE points at the real database')
    sys.exit(2)

JWT_SECRET = A.JWT_SECRET

PASS = 0
FAIL = 0
ERRORS = []


def check(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print('  [OK]   %s' % name)
    else:
        FAIL += 1
        msg = '  [FAIL] %s' % name + (' -- %s' % detail if detail else '')
        ERRORS.append(msg)
        print(msg)


def title(t):
    print('\n%s' % ('=' * 60))
    print('  %s' % t)
    print('%s' % ('=' * 60))


# ═══════════════════════════════════════════════════════
# SEED — a family + user, written straight into the temp DB
# ═══════════════════════════════════════════════════════
def db():
    """Connection to the THROWAWAY database only."""
    assert os.path.abspath(A.DATABASE).startswith(os.path.abspath(TEMP_DIR)), 'temp DB only'
    conn = sqlite3.connect(TEMP_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


_c = db()
_cur = _c.execute("INSERT INTO families (name, invite_code, created_by) VALUES ('SecTestFam','SEC123',NULL)")
FID = _cur.lastrowid
_cur = _c.execute(
    "INSERT INTO users (username,email,display_name,password_hash,firebase_uid,family_id,is_admin) "
    "VALUES ('sectest','sectest@example.invalid','Sec Tester','x','',?,0)", (FID,))
UID = _cur.lastrowid
_c.execute('UPDATE families SET created_by=? WHERE id=?', (UID, FID))
_c.execute('INSERT INTO family_settings (family_id) VALUES (?)', (FID,))
_c.commit()
_c.close()


def payments():
    """Total payment rows for the test family (archived ones included)."""
    c = db()
    n = c.execute('SELECT COUNT(*) FROM payments WHERE family_id=?', (FID,)).fetchone()[0]
    c.close()
    return n


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════
def b64d(seg):
    return base64.urlsafe_b64decode(seg + '=' * (-len(seg) % 4))


def b64e(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def jwt_payload(**over):
    now = datetime.now(timezone.utc)
    p = {'user_id': UID, 'username': 'sectest', 'display_name': 'Sec Tester',
         'family_id': FID, 'is_admin': False,
         'exp': int((now + timedelta(days=1)).timestamp()),
         'iat': int(now.timestamp())}
    p.update(over)
    return p


def api_add(token, desc):
    """POST /api/payments/add with a Bearer token, on a FRESH client.

    A fresh client every time is essential: auto_jwt_auth() populates the Flask
    session on success, so a reused client could authenticate a later request by
    cookie and mask a rejected token.
    """
    cl = A.app.test_client()
    headers = {'Content-Type': 'application/json'}
    if token is not None:
        headers['Authorization'] = 'Bearer %s' % token
    return cl.post('/api/payments/add', headers=headers,
                   data=json.dumps({'description': desc, 'amount': 11.0}))


def jwt_case(name, token, expect_status, expect_write, desc):
    """Assert status AND side effect: a rejected call must write nothing."""
    n0 = payments()
    r = api_add(token, desc)
    n1 = payments()
    wrote = n1 - n0
    ok = (r.status_code == expect_status) and (wrote == (1 if expect_write else 0))
    check(name, ok, 'status=%s (want %s), rows +%d (want +%d)'
          % (r.status_code, expect_status, wrote, 1 if expect_write else 0))
    return r


def shim_csrf(resp):
    """Read the csrf_token cookie exactly as base.html's fetch shim does:
       document.cookie.split('; ').find(c => c.startsWith('csrf_token=')).split('=')[1]
    """
    doc_cookie = '; '.join(h.split(';')[0] for h in resp.headers.getlist('Set-Cookie'))
    for part in doc_cookie.split('; '):
        if part.startswith('csrf_token='):
            return part.split('=')[1]
    return None


def web_client():
    """A client authenticated by SESSION (the web path), not by JWT."""
    cl = A.app.test_client()
    with cl.session_transaction() as s:
        s['user_id'] = UID
        s['username'] = 'sectest'
        s['display_name'] = 'Sec Tester'
        s['family_id'] = FID
        s['is_admin'] = False
    return cl


print('=' * 60)
print('  OurHome IL - SECURITY REGRESSION TESTS (Issue #21)')
print('=' * 60)
print('  temp dir : %s' % TEMP_DIR)
print('  temp DB  : %s' % TEMP_DB)
print('  app.DATABASE resolves to: %s' % _resolved)
print('  real DB  : %s  (never opened by this file)' % REAL_DB)
print('  seeded   : user_id=%d family_id=%d' % (UID, FID))
print('  archive thread alive: %s | reminder thread alive: %s'
      % (getattr(A, '_archive_thread', None) and A._archive_thread.is_alive(),
         getattr(A, '_reminder_thread', None) and A._reminder_thread.is_alive()))

try:
    # ═══════════════════════════════════════════════════════
    title('1. JWT FORGERY - protected /api/ route must reject')
    # ═══════════════════════════════════════════════════════
    check('app.DATABASE is inside the temp dir (real DB untouched)',
          _resolved.startswith(os.path.abspath(TEMP_DIR)), _resolved)

    # No token at all - baseline.
    jwt_case('No Authorization header -> 401, no row', None, 401, False, 'sec-none')

    # Garbage (the only case the old suite had, kept as a regression anchor).
    jwt_case('Garbage token "not.a.jwt" -> 401, no row', 'not.a.jwt', 401, False, 'sec-garbage')

    # THE issue: a well-formed token signed with the WRONG secret.
    forged = pyjwt.encode(jwt_payload(is_admin=True), WRONG_SECRET, algorithm='HS256')
    check('Forged token is structurally valid (3 segments)', len(forged.split('.')) == 3)
    check('decode_jwt_token() rejects the wrong-secret token', A.decode_jwt_token(forged) is None)
    jwt_case('Wrong-secret JWT -> 401, no row', forged, 401, False, 'sec-wrong-secret')

    # Valid signature, payload swapped afterwards (signature no longer matches).
    genuine = A.create_jwt_token(UID, 'sectest', 'Sec Tester', FID, False)
    if isinstance(genuine, bytes):
        genuine = genuine.decode()
    h, p, sig = genuine.split('.')
    tampered_payload = json.loads(b64d(p))
    tampered_payload['user_id'] = UID + 99999
    tampered_payload['is_admin'] = True
    tampered = '%s.%s.%s' % (h, b64e(json.dumps(tampered_payload).encode()), sig)
    check('Tampered token differs from the genuine one', tampered != genuine)
    check('decode_jwt_token() rejects the tampered payload', A.decode_jwt_token(tampered) is None)
    jwt_case('Tampered-payload JWT -> 401, no row', tampered, 401, False, 'sec-tampered')

    # alg:none - the classic unsigned-token bypass. decode_jwt_token must pin HS256.
    unsigned = '%s.%s.' % (b64e(json.dumps({'alg': 'none', 'typ': 'JWT'}).encode()),
                           b64e(json.dumps(jwt_payload(is_admin=True)).encode()))
    check('decode_jwt_token() rejects alg:none (HS256 is pinned)',
          A.decode_jwt_token(unsigned) is None)
    jwt_case('Unsigned alg:none JWT -> 401, no row', unsigned, 401, False, 'sec-alg-none')

    # Correct secret, but expired.
    expired = pyjwt.encode(jwt_payload(exp=int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp()),
                                       iat=int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp())),
                           JWT_SECRET, algorithm='HS256')
    check('decode_jwt_token() rejects the expired token', A.decode_jwt_token(expired) is None)
    jwt_case('Expired JWT (correct secret) -> 401, no row', expired, 401, False, 'sec-expired')

    # Correct secret, valid, but the user does not exist.
    ghost = pyjwt.encode(jwt_payload(user_id=UID + 4242, is_admin=True), JWT_SECRET, algorithm='HS256')
    check('decode_jwt_token() accepts the ghost token (signature is genuine)',
          A.decode_jwt_token(ghost) is not None)
    jwt_case('Valid JWT for a non-existent user -> 401, no row', ghost, 401, False, 'sec-ghost')

    # CONTROL: a genuine token must still work, otherwise every negative above is meaningless.
    jwt_case('CONTROL: genuine JWT -> 201, row written', genuine, 201, True, 'sec-genuine')

    # ═══════════════════════════════════════════════════════
    title('2. CSRF - web (non-/api/) route must block token-less POST')
    # ═══════════════════════════════════════════════════════
    check('CSRF is active (WTF_CSRF_CHECK_DEFAULT is False, enforced in check_csrf)',
          A.app.config.get('WTF_CSRF_CHECK_DEFAULT') is False)

    # A session-authenticated page load hands out the csrf_token cookie.
    cl = web_client()
    r = cl.get('/home')
    token = shim_csrf(r)
    check('Authenticated GET /home -> 200', r.status_code == 200, 'status=%s' % r.status_code)
    check('csrf_token cookie is readable by the base.html shim',
          bool(token), 'token=%r' % token)

    # No token at all.
    n0 = payments()
    r = cl.post('/add_payment', data={'amount': '25', 'description': 'csrf-none'})
    n1 = payments()
    check('POST /add_payment with session but NO CSRF token -> 400, no row',
          r.status_code == 400 and n1 == n0, 'status=%s, rows +%d' % (r.status_code, n1 - n0))

    # Malformed / foreign token.
    n0 = payments()
    r = cl.post('/add_payment', data={'amount': '26', 'description': 'csrf-foreign'},
                headers={'X-CSRFToken': 'deadbeef.not-a-real-csrf-token.1234567890'})
    n1 = payments()
    check('POST /add_payment with a malformed/foreign CSRF token -> 400, no row',
          r.status_code == 400 and n1 == n0, 'status=%s, rows +%d' % (r.status_code, n1 - n0))

    # CONTROL: the real token, sent the way base.html sends it.
    n0 = payments()
    r = cl.post('/add_payment', data={'amount': '27', 'description': 'csrf-valid'},
                headers={'X-CSRFToken': token or ''})
    n1 = payments()
    check('CONTROL: POST /add_payment with a valid X-CSRFToken -> 302, row written',
          r.status_code == 302 and n1 == n0 + 1, 'status=%s, rows +%d' % (r.status_code, n1 - n0))

    # /api/ is deliberately CSRF-exempt: check_csrf() returns early for /api/ paths
    # because those routes are authenticated by a Bearer JWT, which (unlike a cookie)
    # a cross-site page cannot make the browser attach automatically. Losing this
    # exemption would break the Capacitor mobile app, so it is asserted, not assumed.
    n0 = payments()
    r = api_add(genuine, 'api-exempt')
    n1 = payments()
    check('/api/ route with Bearer and NO CSRF token -> 201, row written (exemption is intentional)',
          r.status_code == 201 and n1 == n0 + 1, 'status=%s, rows +%d' % (r.status_code, n1 - n0))

    # And the exemption must not leak to web routes: same client, no Bearer, no token.
    n0 = payments()
    r = A.app.test_client().post('/add_payment', data={'amount': '28', 'description': 'csrf-anon'})
    n1 = payments()
    check('Unauthenticated token-less POST /add_payment -> not 2xx, no row',
          not (200 <= r.status_code < 300) and n1 == n0,
          'status=%s, rows +%d' % (r.status_code, n1 - n0))

finally:
    # ═══════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════
    print('\n%s' % ('=' * 60))
    print('  RESULTS: %d passed, %d failed' % (PASS, FAIL))
    print('%s' % ('=' * 60))
    if ERRORS:
        print('\nFAILURES:')
        for e in ERRORS:
            print(e)
    else:
        print('\nALL TESTS PASSED - JWT forgery and CSRF enforcement are covered.')

    # Best-effort cleanup; a daemon scheduler thread may still hold the file on Windows.
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    print('  cleaned up temp dir: %s (still present: %s)'
          % (TEMP_DIR, os.path.exists(TEMP_DIR)))
    print()

sys.exit(1 if FAIL else 0)

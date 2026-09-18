# OurHome IL — Fixes Log

Sequential remediation of `ISSUES.md`, Critical → Low. Each fix is implemented by a
fixer agent and then independently verified by a separate reviewer agent with fresh
context. No issue is marked Fixed until the reviewer returns `APPROVED`.

**Safety note**: The working tree was dirty at the start of this run (uncommitted
`app.py` work — the feeding-reminder anti-spam logic, ~89 insertions / 47 deletions).
A snapshot of all dirty files was taken to the session scratchpad
(`scratchpad/backup_pre_fixes/`) before any edits were made.

---

## Issue #1 — `.gitignore` is UTF-16LE encoded, every ignore rule silently inactive

- **Severity**: Critical
- **Status**: ✅ **Fixed**
- **Files changed**: `.gitignore` (only)
- **What changed**: Re-saved the file as UTF-8 with no BOM and normalized CRLF → LF.
  Content was otherwise preserved verbatim — no patterns added, removed, or reordered.
- **Why**: Git's ignore parser reads only UTF-8/ASCII. The UTF-16LE BOM (`FF FE`) plus
  null-interleaved bytes meant all 38 patterns were dead text, leaving the live Firebase
  credential and the SQLite database unprotected from `git add`.
- **Verification**: Whole-file scan shows 0 null bytes, 0 CR bytes, no BOM of any kind.
  Independent decode-and-diff of the pre-fix backup against the new file: 65 lines → 65
  lines, 0 differing lines, 38 patterns identical and in order, all 646 non-ASCII
  characters preserved. Sampled rules now match with exit 0 (`serviceAccountKey.json`,
  `finance_tracker.db`, `__pycache__/`, `node_modules/`, `.env`, `.env.local`, `logs/`).
  `serviceAccountKey.json` has dropped out of `git status` untracked output while
  remaining intact on disk. Index, HEAD, and reflog unmodified; `app.py` never opened.
- **Reviewer verdict**: **APPROVED** — "The fix does precisely what was claimed and
  nothing more... over-ignores nothing beyond the known DB files and pre-existing
  vendored/IDE directories — no source file or template is affected."

---

## Issue #2 — Database files tracked in git (real PII/financial data)

- **Severity**: Critical
- **Status**: ✅ **Fixed** (preventive half) — ⚠️ **history scrub needs manual review**
- **Files changed**: none on disk; git **index** only
- **What changed**: `git rm --cached --` on `finance_tracker.db`, `finance_tracker.db-shm`,
  `finance_tracker.db-wal`, and `test_files/finance_tracker.db`. The four files are now
  staged deletions awaiting the user's own commit. `.gitignore` required **no edit** — the
  fixer verified it already had explicit lines 15/16/17 covering all three DB variants, and
  that the bare line-15 pattern also matches the nested `test_files/` copy, so it correctly
  made no change rather than adding redundant churn.
- **Why**: Git ignores rules never apply to already-tracked files, so fixing `.gitignore`
  in Issue #1 could not on its own stop these files from being recommitted.
- **Verification**: The critical check was data survival — a bare `git rm` instead of
  `git rm --cached` would have destroyed the live production database. Reviewer opened a
  **copy** of the DB (never the originals, to avoid mutating `-shm`/`-wal`):
  `integrity_check: ok`, `journal_mode: wal`, 13 tables, real rows present
  (`families 1 | users 1 | categories 9 | family_settings 1`). All four originals re-hashed
  byte-identical after inspection; original mtimes (Apr 7 / Jun 26) prove they were never
  written today. `test_files/finance_tracker.db` was independently confirmed as 0 bytes
  *before* the fix via git's canonical empty-blob SHA (`e69de29b…`) — a placeholder, not
  data loss. Index shows exactly four `D ` entries; `git ls-files | grep finance_tracker`
  is empty. HEAD still `e8f8310` and `.git/logs/HEAD` mtime unchanged (Jun 26) while
  `.git/index` mtime is today — decisive proof the index was rewritten but nothing was
  committed, reset, or rewritten. The `refs/original/*` present is pre-existing (April
  `filter-branch`), not from this fix.
- **Consequence checked**: a fresh clone will have no DB file; `app.py:2974` calls
  `init_db()` at import and uses `CREATE TABLE IF NOT EXISTS`, so the schema self-creates
  rather than crashing. No test depends on the tracked artifact.
- **Reviewer verdict**: **APPROVED** — "The production database is verifiably intact…
  proving `--cached` was used rather than a bare `git rm`."

### ⚠️ Needs manual review — PII remains in git history

Untracking stops *future* commits; it does not remove what is already committed. Notably
`HEAD:finance_tracker.db-wal` is a **436,752-byte** blob (versus only ~4 KB for the `.db`
blob itself), so the bulk of the committed family/financial data lives in the WAL file.
Removing it requires rewriting history (`git filter-repo`/BFG), which invalidates every
existing clone and force-pushes a shared branch — **a deliberate human decision, not one to
automate.** The repo has been through this before (April `filter-branch` for
`serviceAccountKey.json`), so the workflow is familiar to the owner.

---

---

## Issue #3 — `serviceAccountKey.json` one `git add` away from being recommitted

- **Severity**: Critical
- **Status**: ✅ **Fixed** (preventive + hardening) — ⚠️ **key rotation needs manual review**
- **Files changed**: `firebase_config.py` (+20/−0), `.env.example` (new)
- **What changed**: The accidental-commit risk was already closed by Issue #1 (the file is
  genuinely ignored now), so this fix was scoped to defense-in-depth only:
  1. `_warn_if_credential_in_repo()` in `firebase_config.py` prints a nudge at startup when
     the Admin SDK credential is loaded from a path inside the repo working tree, pointing
     at `FIREBASE_CREDENTIALS_PATH` / `FIREBASE_CREDENTIALS`. Silent for inline-JSON or
     out-of-repo paths.
  2. `.env.example` — a committable, placeholder-only template for the 11 env vars the code
     actually reads (`SECRET_KEY`, `JWT_SECRET`, `PORT`, `DATABASE_PATH`, `FIREBASE_API_KEY`,
     `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_CREDENTIALS`, `FCM_SERVICE_ACCOUNT`,
     `MAIL_USERNAME`, `MAIL_PASSWORD`, plus `TZ` marked deployment-only).
- **Deliberately NOT done**: the key was not moved (would break local dev) and not rotated
  (requires Firebase console access). The hardcoded `FIREBASE_API_KEY` default on line 25 was
  left alone — that is Issue #23.
- **Verification**: No secret leakage — all 11 real values in `serviceAccountKey.json`
  (including `private_key`, `private_key_id`, `client_email`) tested as full values *and* as
  40-char head/tail fragments against `.env.example`: zero matches. Same for all 8 real values
  in `docker-compose-new.yml`. `AIzaSy` count: 0. Safety: 15 hostile inputs swept through the
  new function (`None`, `int`, `bytes`, embedded NUL, `D:` cross-drive, UNC path, 5000-char
  path, `..` traversal, sibling-prefix trap) — **zero raised**, max 4.83 ms, runs once at
  import. Mixed-drive `ValueError` from `commonpath` is caught. `_REPO_ROOT` derives from
  `__file__` and stayed correct with cwd at `C:\Windows` and `test_files/`. Existing behavior
  byte-identical: `initialize_app(cred)` and both original `print()` lines unchanged, no new
  imports. `import app` verified against a **temp DB copy** (`DATABASE_PATH` honored) — both
  daemon threads started, no crash, real DB never touched. `git check-ignore .env.example`
  exits 1 (committable). No collateral damage: `app.py` still exactly 89/47, HEAD still
  `e8f8310`, reflog unchanged, `serviceAccountKey.json` untouched at 2388 B.
- **Reviewer verdict**: **APPROVED**

### ⚠️ Needs manual review — rotate the Firebase Admin SDK key

The key was exposed in git history twice before being scrubbed (April `filter-branch`). Any
clone or fork taken before those scrubs still contains it. Since a scrub cannot recall copies
already distributed, the key should be treated as potentially compromised and **rotated in the
Firebase console**, with the new key supplied via `FIREBASE_CREDENTIALS_PATH` pointing outside
the repo. This requires console access and a redeploy — a human action.

---

---

## Issue #4 — Weak placeholder production secrets enabling JWT forgery

- **Severity**: Critical
- **Status**: ✅ **Fixed** (guard + de-secreted config) — ⚠️ **rotation/redeploy needs manual review**
- **Files changed**: `app.py` (+37/−0), `docker-compose-new.yml` (4 lines replaced, 1 added),
  `.env.example`
- **Root cause was worse than ISSUES.md recorded**: `app.py:40` falls `JWT_SECRET` back to
  `app.secret_key`, which `app.py:36` falls back to the public literal
  `'dev-key-change-in-production'`. With no env vars set, JWTs were signed with a constant
  published in the source — forgeable for any `user_id` with `is_admin: true`.
- **What changed**:
  1. `app.py` — `APP_ENV` (default `development`) plus a `WEAK_SECRETS` denylist and
     `_is_weak_secret()` catching missing values, the 4 known literals, and anything containing
     `change-me` / `change-in-production`. In production a weak or missing `SECRET_KEY` /
     `JWT_SECRET` raises `RuntimeError` and refuses to start; outside production it prints a
     non-fatal warning. Checks run on the **effective** values, so the documented
     `JWT_SECRET → SECRET_KEY` fallback is not falsely failed.
  2. `docker-compose-new.yml` — 4 plaintext secrets replaced with `${VAR:?...}` fail-fast refs,
     plus `APP_ENV=production` on the `ourhome` service. The legacy `finance-app` service got
     its **own** `FINANCE_APP_SECRET_KEY` rather than sharing `SECRET_KEY`, so rotating the main
     app does not log out legacy users.
  3. `.env.example` — added `APP_ENV` and `FINANCE_APP_SECRET_KEY`, placeholders only.
- **Verification**: 14/14 guard cases pass as fresh subprocesses against a **temp DB copy**:
  no env vars → starts + warns (local dev preserved); production + missing / weak / real
  placeholder secret → `RuntimeError`, rc=1; production + strong secrets → starts and served
  `GET /login` → 200 on a spare port. Edge cases confirmed: `Production` / `PRODUCTION` /
  `"  production  "` all engage the guard (`.strip().lower()`); strong `SECRET_KEY` with **no**
  `JWT_SECRET` correctly starts; weak `JWT_SECRET` beside a strong `SECRET_KEY` is still caught.
  Compose diff vs pre-edit backup is exactly 4 replacements + 1 addition — `traefik` and `n8n`
  services byte-identical, all Traefik labels, router rules, `Host()` rules, certresolver,
  ports, volumes, `restart` policies and ACME config verified unchanged; YAML parses clean.
  **No scope creep**: `SSL_EMAIL`, `DOMAIN_NAME`, `SUBDOMAIN`, `GENERIC_TIMEZONE` were already
  bare `${VAR}` in the original and were not given `:?` (the fixer's narrative claimed otherwise;
  the reviewer verified the code is correct). No secrets remain in the compose file. `app.py`
  diff = 126/47, i.e. the user's 89/47 baseline + exactly the 37-line guard; feeding-reminder
  work untouched. HEAD `e8f8310`, real DB hash unchanged, no `.env` created.
- **Reviewer verdict**: **APPROVED** — "The guard is correct and unbypassable in the tested
  space… The compose change is surgical."

### ⚠️ Needs manual review — rotate and redeploy

1. Generate real secrets (`python -c "import secrets; print(secrets.token_hex(32))"`) for
   `SECRET_KEY`, `JWT_SECRET`, and `FINANCE_APP_SECRET_KEY` into the server's `.env`, then
   redeploy. **Rotating `JWT_SECRET` invalidates every active web session and mobile JWT** —
   all users will be logged out and must sign in again. Schedule accordingly.
2. The server `.env` must contain all four secrets before the next `docker compose up`.
   Because `${VAR:?}` fails validation for the *whole file*, a missing var will also block
   `traefik` and `n8n` from coming up. Already-running containers are unaffected until re-up.
3. The legacy `finance-app` service still ships `DEFAULT_USER=admin` / `DEFAULT_PASS=admin` on
   a routable hostname. Left intact deliberately (changing it could lock you out) — decide
   whether to rotate those credentials or decommission the service.

### Operational note (non-blocking)

`APP_ENV=prod` (abbreviated) silently falls through to permissive mode; only the exact value
`production` engages the guard. The deployed value is correct, so this is not a live risk, but
it is a sharp edge if someone abbreviates it later.

---

## Issue #5 — Stored XSS via unescaped user text in `innerHTML`

- **Severity**: Critical
- **Status**: ✅ **Fixed**
- **Files changed**: `templates/baby_tracker.html`, `settings.html`, `dashboard.html`,
  `shopping_list.html`, `home.html`, `history.html` (6 templates; `app.py` untouched)
- **Scope grew — the issue report was wrong on two points**, both corrected by the fixer and
  independently confirmed by the reviewer:
  1. `baby_tracker.html` has **no** `esc()` helper (the report claimed it did but wasn't using
     it). The helper actually lived in `dashboard.html`, `history.html`, `shopping_list.html`.
  2. That existing `esc()` (a `textContent`→`innerHTML` round-trip) escaped only `& < >` and
     **not quotes** — so it was *already unsafe* wherever it was used inside an attribute, e.g.
     `style="…${esc(color)}"`. It was hardened in place; the same hardened helper was added to
     the three templates lacking one.
- **Final scope**: 16 sink fixes + 6 helper additions/hardenings + 7 delegated listeners,
  including **7 sinks not in the original report** (`settings.html:133` Jinja-built
  `onclick`, `dashboard.html:656/659` chart colors, `shopping_list.html:485/499` edit-preview
  `<img src>`, `home.html:341` last-payment description, and 6 pre-existing
  `style="…${esc(color)}"` breakouts in `history.html`).
- **Approach**: type (a) unescaped-text sinks routed through the hardened `esc()`; type (b)
  `onclick="fn('…')"` attribute-building replaced with `data-*` attributes plus **top-level
  event delegation**, looking records up by integer id rather than embedding user text in the
  DOM.
- **Verification**: The three highest-risk areas were each checked independently.
  **Double-fire**: all 7 `addEventListener` calls are at script top level (never inside a
  render function); driving the real `loadData()`/`loadPayments()`/`loadRecurring()`/
  `loadCategories()`/`loadItems()` 3–4× then dispatching **one** click on the nested `<i>`
  icon produced **exactly one** invocation each (e.g. exactly one `DELETE /api/feedings/11`),
  including dashboard's sorted-view branch; container node identity verified stable across
  re-renders. **Backward compatibility**: hardened `esc()` is byte-identical to the old one
  for quote-free input; `esc(null)/esc(undefined)` → `""` so `${esc(p.color)||'#94a3b8'}`
  still falls back; text nodes round-trip exactly (`Ben & Jerry's 5 < 10 שלום "hi"` verbatim,
  no double-escaping); edit forms still receive **raw** values, no entity leakage.
  **Exploitability**: across all 6 templates, payloads `<img src=x onerror=alert(1)>`,
  `x" onmouseover="alert(1)`, `</script><script>alert(1)</script>`, `"><svg onload=alert(1)>`
  and `#fff;" onload="alert(1)` produced **0** injected elements, **0** `on*` attributes, and
  never invoked `window.alert`.
- **Deliberately left alone**: 38 remaining unescaped `${}` interpolations, each verified safe
  (numerics, hardcoded constants/labels, booleans, integer ids, already-escaped fragments), and
  7 inline `onclick`s taking only integer ids — confirmed integer-only by tracing them to
  `INTEGER PRIMARY KEY AUTOINCREMENT` rowid aliases at `app.py:448-481`. No CSP added
  (architectural, separately decidable). No server-side input sanitization (escaping on output
  is the correct fix; sanitizing on write would corrupt stored data).
- **No regressions**: `node --check` clean on all 6 extracted script blocks; Hebrew string
  inventory, class names, element ids identical to pre-fix backups; zero CSS changes.
- **Reviewer verdict**: **APPROVED** — "all 16 sinks plus 7 unreported ones are inert against
  realistic breakout payloads, the delegation rewrite fires exactly once after repeated
  re-renders including clicks on nested icons."

---

## Issue #6 — `GET /delete_payment/<id>` deletes with no CSRF protection

- **Severity**: High
- **Status**: ✅ **Fixed** (reviewed across two sessions — server-side matrix in the first,
  browser path and client sweep in the second)
- **Files changed**: `app.py` (+4/−1), `templates/dashboard.html` (+1/−1)
- **What changed**:
  1. `app.py:1226` — `methods=['POST', 'GET']` → `methods=['POST']`, plus a comment warning
     against re-adding GET. Authorization, `family_id` scoping, push notification, and the
     `{'success': True}` response shape are untouched.
  2. `templates/dashboard.html:511` — `fetch('/delete_payment/'+id+'?api=1')` →
     `fetch('/delete_payment/'+id+'?api=1', {method:'POST'})`. **This change was mandatory,
     not optional**: `fetch()` with no `method` defaults to GET, so the dashboard's delete
     button was itself relying on the vulnerable GET path and would have 405'd otherwise.
     Confirm dialog, toast, and `loadPayments(); loadCharts();` refresh unchanged.
- **CSRF token path** (independently confirmed): `base.html:166-179`
  monkey-patches `window.fetch` and, for POST/PUT/DELETE/PATCH, copies the `csrf_token` cookie
  (set by `inject_csrf_token()`, `app.py:101-103`) into an `X-CSRFToken` header. `app.py` never
  sets `WTF_CSRF_HEADERS`, so Flask-WTF's default accepts it. The shim renders at
  `base.html:179`, before `{% block scripts %}` at line 180. Same pattern as
  `dashboard.html:639` and `settings.html:504/523`.
- **Verified (independently, by the reviewer before it was stopped)** — all four server-side
  cases pass, asserting on database row counts rather than status codes alone:

  | Case | Expected | Result |
  |---|---|---|
  | `GET /delete_payment/<id>` | 405, row survives | ✅ PASS |
  | `POST` with no CSRF token | 400, row survives | ✅ PASS |
  | `POST` with **invalid/garbage** token | 400, row survives | ✅ PASS |
  | `POST` with valid `X-CSRFToken` | 200, row deleted | ✅ PASS |

- **Browser path verified — the delete button genuinely still works.** This was the decisive
  check, since the fix moved the button onto a CSRF-protected method:
  - **The `csrf_token` cookie is NOT HttpOnly** — `app.py:102` calls `set_cookie` without an
    `httponly` argument and Flask defaults it to `False`. Confirmed empirically against a live
    response, with the `session` cookie as a control:
    ```
    csrf_token=IjBhY2E1…; Path=/                 <- no HttpOnly, JS can read it
    session=eyJfcGVybWFuZW50…; HttpOnly; Path=/   <- HttpOnly (control)
    ```
    Had it been HttpOnly, the shim would have silently attached nothing and every click would
    have 400'd despite the server-side tests passing.
  - `WTF_CSRF_HEADERS` defaults to `['X-CSRFToken', 'X-CSRF-Token']` and is never overridden in
    `app.py`, so the shim's header name is accepted.
  - **No token truncation**: the token contains no `=` and is unquoted, so the shim's
    `.split('=')[1]` yields the complete value — the one plausible silent-failure bug is absent.
  - **Ordering confirmed structurally** (not by line numbers): the shim is `base.html:166-179`,
    `{% block scripts %}` is `base.html:180`, and `dashboard.html:416-737` sits entirely inside
    that block, so the patched `fetch` is installed first.
  - **Strongest evidence**: the shim was extracted from `base.html` at runtime and executed
    verbatim in a Node VM against a real cookie — `fetch('/delete_payment/42?api=1',
    {method:'POST'})` attached `X-CSRFToken` exactly equal to the cookie. GET calls were left
    untouched and caller-supplied headers preserved.
- **No other client breaks**: repo-wide grep finds `delete_payment` only in
  `templates/dashboard.html:511`, `test_files/locustfile.py:344`, `app.py`, and docs — **zero**
  hits in `android/`, `.java`, `.js`, `.ts`, or `.json`. Mobile uses the CSRF-exempt
  `DELETE /api/payments/<id>` (`app.py:2406-2407`, `@csrf.exempt`), so the JWT path is
  unaffected. `locustfile.py`'s `_csrf()` helper (line 49) already reads the cookie and sends
  the header, so the load tests match the new contract.
- **Flagged, not fixed**: the `if request.is_json or request.args.get('api') or
  request.method == 'POST':` guard at `app.py:1242` is now always true, so
  `redirect(url_for('dashboard'))` at `app.py:1244` is unreachable dead code. Left deliberately
  as the minimal change.

### ⚠️ ISSUES.md correction — this was NOT the only GET-mutating route (confirmed)

The audit claimed `/delete_payment/` was the only mutating route reachable by GET. That is
**wrong, and the correction has now been independently confirmed**. `history_data`
(`/api/history/data`) and `history_month_detail` (`/api/history/month`) both declare no
`methods=`, so they are GET-only, and both run `UPDATE archived_cycles SET month=?`.

**Risk independently assessed as low, and that assessment holds**: the SELECTs are scoped by
`family_id` alone — the `year`/`month` arguments don't even filter which rows get touched — and
the written value `f'{p}-{m_num:02d}'` is parsed entirely from that row's own `label` column.
Zero request-controlled input reaches the write, and it's idempotent (skips once `month` is
non-empty). A forged `<img src>` produces no attacker-meaningful state change. Worth tracking
as its own (low-severity) issue, but not urgent.

- **Reviewer verdict**: **APPROVED** — "The fix closes the CSRF hole correctly and, critically,
  does not break the UI… verified by executing the shim itself against a real cookie and by a
  server-side roundtrip."

> **Committed** — Issues #1-6 were committed together as `bb0a195` on
> `android_firebase_integration` (not pushed). Everything below is on top of that commit.

---

## Issue #7 — No rate limiting on the local password fallback for email-less accounts

- **Severity**: High
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+33/−0)
- **Claim verified first** (ISSUES.md had been wrong three times, so it was checked before any
  fix was designed): the path is real. `api_register()` validates email only
  `if email and not re.match(...)`, so an empty email passes. `firebase_create_user('')` then
  raises inside a generic `except Exception` (`firebase_config.py:95`) that returns
  `(None, None)`, so registration completes locally with `email=''`. That account can only log
  in through the `check_password_hash` branch of `api_login()`, which had no throttling at all.
- **Design decision — no new dependency**: a small SQLite-backed failed-attempt counter instead
  of Flask-Limiter. Keeps every fix so far dependency-free, and because the state is in the DB
  it survives restarts and is shared across gunicorn workers (in-memory limits would be split per
  worker — the Issue #20 problem). Requiring an email at registration was deliberately **not**
  done: it's a product decision, and existing email-less accounts would stay exposed anyway.
- **What changed**:
  1. `LOGIN_MAX_FAILURES = 5`, `LOGIN_WINDOW_MINUTES = 15` next to the JWT config.
  2. `init_db()` creates `login_attempts (attempt_key, attempted_at)` plus
     `idx_login_attempts_key`, using the existing `CREATE ... IF NOT EXISTS` pattern.
  3. Helpers `login_locked(conn, key)` and `record_login_failure(conn, key)` after
     `decode_jwt_token`. Timestamps are `now_israel()` as fixed-width `%Y-%m-%d %H:%M:%S`, so text
     comparison is chronological.
  4. `api_login` username branch: users **with** an email still go to Firebase, untouched. For
     the rest, the lock is checked **before** `check_password_hash` → HTTP 429
     `'יותר מדי ניסיונות. נסה שוב מאוחר יותר'` (the wording Firebase's own throttling already
     uses). Every 401 in that branch records a failure — for a wrong password **and** for a
     non-existent username — keyed by the lowercased, stripped username. Success clears the key.
- **Verification** (reviewer, own copy of the DB, in-process test client):
  - Lock ordering: 5 wrong passwords then the **correct** one → `[401×5, 429]`.
  - No bypass via normalization: `RV_LOCAL`, `' rv_local'`, `'rv_local '`, `'Rv_Local\t'` all
    429, sharing a single key. Blank or whitespace `email` alongside `username` → still 429; a
    non-empty `email` is routed to Firebase and cannot log into the local account.
  - Window boundaries: 5 failures backdated 14m59s → 429; 15m01s → 200; 4 inside + 1 outside →
    200. Pruning deletes only that key's expired rows. Success clears the key.
  - **No new existence oracle**: a non-existent username and a real email-less user with wrong
    passwords both return `[401×5, 429, 429]` with **byte-identical** bodies.
  - Email users are never counted: 7×401, 0 rows, 7 Firebase calls (mocked).
  - Schema: only `login_attempts` and its index are new; every other table's `sqlite_master` SQL
    unchanged; `init_db()` idempotent.
  - All SQL parameterized. `git status` shows only ` M app.py` beyond pre-existing files; HEAD
    still `bb0a195`; Issue #4 guard and Issue #6 POST-only route still present.
- **Test-suite conflict (not fixed, by design)**: `'nonexistent_user_xyz'` is hard-coded in
  `test_files/test_edge_cases.py:175` and `test_files/test_deep_audit.py:145`, both asserting
  401. One run of either adds one failure, so a single run can never trip the lock — but **6 or
  more combined runs within 15 minutes against the same DB will start getting 429** and fail.
  All other test logins use usernames with emails (Firebase path, never counted);
  `test_flows.py` and `locustfile.py` (web `/login`) are unaffected. If you run the suites
  repeatedly, wait out the window or `DELETE FROM login_attempts` on the dev DB.
- **Known limitations, judged acceptable by the reviewer** (worth hardening later):
  - The count check and the insert aren't atomic, and `check_password_hash` is slow, so N parallel
    requests can each pass the check — roughly 4+N guesses per window, bounded by server
    concurrency. Weakens the limit without defeating it. Hardening: insert the attempt row
    first, then count.
  - Per-username lockout lets someone lock a real user out for 15 minutes. Acceptable here.
  - Expired rows for a key that never fails again are never pruned, so spraying many unique
    usernames grows the table without bound.
  - No per-IP limit, so one common password tried across many accounts isn't throttled. Needs
    trusted `X-Forwarded-For` handling behind Traefik.
  - Timestamps are naive Israel time, so the window is off by an hour across a DST change.
- **Reviewer verdict**: **APPROVED** — "The lock is checked before the password on the only
  path it protects… Unknown and real usernames get identical codes and bodies, so there's no
  new existence oracle."

### ⚠️ Process incident during Issue #7 — real database file was opened

The **fixer** broke the database rule: to copy `finance_tracker.db` it opened the real file with
`sqlite3.connect()` and called `.backup()`. It never wrote to it, but the DB is in WAL mode, so
closing that connection **checkpointed** the WAL into the main file and removed the `-wal` and
`-shm` files. The main file's bytes and mtime changed (sha256 `8fa09c23…` → `8229690d…`, mtime
2026-09-17 18:34:00).

**No data was lost.** The orchestrator checked a filesystem copy: `integrity_check: ok`, 13
tables, and every row count identical to the Issue #2 snapshot (`families 1`, `users 1`,
`categories 9`, `family_settings 1`, `payments 0`, `sqlite_sequence 4`), with no
`login_attempts` table and no test users. A checkpoint is the same thing SQLite does whenever
the app itself runs. The reviewer then confirmed the file was unchanged across its whole review
by hashing only.

**Rule tightened for all later agents** (see "How this run works" below): never open any SQLite
connection to a DB in the repo root — not even read-only, since a read-only connection to a WAL
database can still touch `-shm` — copy at the filesystem level only; never run `test_files/`
scripts, which connect to `finance_tracker.db` by relative path; and hash the real DB at start
and end.

---

## Issue #8 — FCM credential missing locally; push failures hard to see

- **Severity**: Medium
- **Status**: ✅ **Fixed** (visibility only — the credential file itself must come from the owner)
- **Files changed**: `app.py` (+22/−4)
- **ISSUES.md wording corrected**: pushes were not fully "silent". When the credential is missing
  and the family **has** registered devices, every push attempt prints
  `FCM service account not found: …`. But the token check runs **before** the credential check,
  so a family with no devices never reveals the missing credential, nothing at startup said push
  was disabled, and callers/tests could not tell "queued" from "skipped".
- **What changed**:
  1. `send_push_to_family()` now returns a status string on every exit: `'no_tokens'`,
     `'no_credentials'`, `'no_project_id'`, `'queued'`, `'error'`. The docstring lists them and
     states that `'queued'` means the background thread started, **not** that FCM delivered it.
     Check order, prints, queries, and the daemon-thread dispatch are unchanged, and no call site
     was touched (all 19 call it as a bare statement).
  2. A one-time **plain-ASCII** startup notice right after `FCM_SERVICE_ACCOUNT_PATH` when the file
     is missing, explaining that `FCM_SERVICE_ACCOUNT` enables push. Wrapped in
     `try/except Exception: pass`, prints fixed text only. ASCII on purpose, to avoid the cp1255
     startup crash.
  3. `.env.example` left alone — `FCM_SERVICE_ACCOUNT` was already documented (line 76).
- **Verification** (reviewer, own DB copy, outbound network blocked, all FCM calls mocked):
  - Every status reproduced: `no_tokens` (no tokens, **and** the extra case where the only token
    belongs to the excluded user), `no_credentials` (worker not called), `no_project_id`,
    `queued` (worker got `['tokA1','tokA3']` with a2 excluded, all three without exclusion, correct
    title/body/project args), `error`.
  - Line-by-line comparison with `HEAD`: only `return` values and the docstring differ. Token query
    still precedes `get_fcm_access_token` (0 credential calls on the no-tokens path). 5 exits, all
    return a string, none returns `None`. Thread still `daemon=True`, never joined.
  - Startup notice: one `os.path.exists` call, 330 bytes of pure ASCII, printed once when the file
    is missing and not at all with a dummy file present.
  - Diff scope: Issue #8's 4 hunks are confined to `send_push_to_family` and the lines after
    `FCM_SERVICE_ACCOUNT_PATH`; all 6 Issue #7 hunks intact. `app.py` numstat 55/4 (both issues).
    Line endings consistent: 3069 CRLF, 0 bare LF, 0 bare CR.
  - Real DB sha256 `8229690d…499d57`, 139,264 bytes, identical at start and end; HEAD `bb0a195`,
    reflog unchanged.
- **Minor, accepted**: with the credential missing, a push attempt now prints the per-call
  `FCM service account not found` line in addition to the startup notice.
- **Flagged, not fixed**: `.env.example` line 75 still describes push as silently no-oping — a
  one-line wording fix.
- **Reviewer verdict**: **APPROVED** — "only adds a string return to each of the five exits… The
  check order, prints, queries and daemon-thread dispatch are unchanged, and I found no path that
  returns `None`."

### ⚠️ Finding against Issue #4 (already approved) — its dev warning crashes startup under cp1255

Confirmed by the Issue #8 reviewer. With `PYTHONIOENCODING` unset and stdout redirected, importing
the app crashes at the pre-existing emoji print in `firebase_config.py:63`. With `firebase_config`
stubbed out, startup **then crashes at `app.py:77`** — the Issue #4 weak-secret warning
(`'⚠️ Weak/default …'`) — and the success message at `app.py:81` (`'✅ …'`) has the same problem.
So the Issue #4 guard, which was written in the project's emoji-print idiom, independently breaks
the Windows "capture server output to a file" workflow; today it's masked because
`firebase_config.py` crashes first. **Not a production risk** (Linux containers are UTF-8, and
the production *refusal* path raises a pure-ASCII `RuntimeError`). The Issue #4 reviewer's check
only tested the refusal path and the case where `firebase_config` crashed first, so it missed
this. The fix belongs with the cp1255 item under "Newly discovered" below — one fix for both.

---

## Issue #9 — Users whose Firebase account was never created can never log in

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+40/−6)
- **ISSUES.md understated the impact.** Registration (web and API) inserts a working local row with
  `firebase_uid=''` whenever `firebase_create_user` fails silently. ISSUES.md said only the web
  `/login` was affected, but `api_login` also sends every email login — and every username login
  whose row has an email — through Firebase only. Those users were locked out of the web app **and**
  the mobile app.
- **What changed**: one shared helper, `local_login_fallback(email, password, fb_error)`, called by
  both web `/login` and `api_login` **only after** `firebase_verify_login` returns an error.
  - **Gate**: falls back to `check_password_hash` only when the email is non-empty, the Firebase
    error is not `USER_DISABLED`, and the email matches **exactly one** row whose `firebase_uid` is
    empty or NULL. Every other case returns the Firebase error unchanged, records nothing and checks
    no lock — linked accounts depend on Firebase exactly as before.
  - **Throttle**: reuses the Issue #7 limiter, keyed on the row's `username.strip().lower()`, so
    email-based and username-based attempts share one counter. Lock checked **before** the hash;
    a locked account gets 429 (API) or the lock message (web) even with the correct password.
  - Wrong password → records a failure and returns the **Firebase error unchanged**. Correct
    password → clears the key, then the routes run their **original** session/JWT code (only the
    user lookup is wrapped in `if user is None:`). `firebase_uid` is left empty.
  - **Fixer's judgment calls, both endorsed by the reviewer**: `USER_DISABLED` never falls back
    (Firebase can only return it for an account that exists and was deliberately disabled, so a
    fallback would undo the disable, while a never-created account can't receive it); an empty
    email is refused (otherwise web `/login` with no email would have matched email-less rows).
- **Verification** (adversarial reviewer, own DB copies, Firebase mocked, sockets blocked, HEAD
  loaded as a separate module for comparison):
  - **No way into a linked account**: local password rejected for email variants
    (`' linked@x.com'`, `'LINKED@X.COM'`, trailing space); `firebase_uid=' '` treated as linked
    (fails closed); linked `Case@x.com` beside unlinked `case@x.com` — linked password rejected in all
    3 case variants; linked+unlinked rows sharing one email and two unlinked duplicates both refused
    (`len != 1`); `USER_DISABLED` with the correct password refused; empty `password_hash` refused;
    `username`+`email` together and username→linked-email conversion refused. No other user's
    account reachable. NULL and `''` both behave as unlinked.
  - **Throttling**: 3 failed email attempts + 2 failed username attempts share one key; the correct
    password then gets 429 on both API paths and the lock message on the web. A malformed hash or
    non-string password raises a 500 — never a success.
  - **Session safety**: `session.clear()` still runs first; a pre-seeded junk key and fake
    `user_id` were wiped after a fallback login.
  - **CSRF**: a web POST without a token returns 400 both at HEAD and now.
  - **Regression**: 45 scenarios compared against HEAD — 39 identical (all linked, unknown,
    disabled, and Firebase-success cases, including linking on Firebase success); the 6 differences
    are exactly the intended unlinked-success cases.
  - Issue #7/#8 hunks byte-identical; `app.py` 3103 CRLF, 0 bare LF; real DB sha256 `8229690d…499d57`
    unchanged at start and end; HEAD `bb0a195`.
- **Existing tests**: no expectation gets worse. Username logins in `test_flows.py` 2.2/2.3,
  `test_edge_cases.py` "Correct login works", and `test_deep_audit.py` A3/A5 previously got 401 if
  their Firebase registration had failed, and now pass. Their test usernames are random, so repeated
  runs can't trip the lock. Web logins that send `username` with no `email` (`locustfile.py:72`,
  `test_deep_audit.py:690`) exit the helper early — unchanged.
- **Known limitations, accepted by the reviewer**:
  - **Stale password**: if a Firebase account exists for the email but the row is unlinked and the
    user reset their password in Firebase, the **old local password still works**. Confirmed
    reachable (200), and the victim's first Firebase login closes it (sets `firebase_uid`, old
    password → 401). Needs `create_user` to succeed on Google's side yet raise client-side, the
    victim to reset before ever logging in, and the attacker to know the registration password —
    judged very unlikely. **Optional hardening**: allow the fallback only when the Admin SDK is
    uninitialised or `firebase_auth.get_user_by_email` raises `UserNotFoundError`, and deny on any
    other result. Don't use `firebase_get_user` for this (it returns `None` on any error), and the
    REST error codes can't distinguish "no account" from "wrong password" (both
    `INVALID_LOGIN_CREDENTIALS`).
  - **Existence oracle**: unlinked, unknown and linked emails return identical 401 bodies for 5
    attempts; only an unlinked email then gets 429. Plus a timing gap (~195 ms vs ~5 ms, from the
    password hash; real Firebase latency masks part of it). Reveals only unlinked rows, and
    registration already reveals any email (Issue #24) — not materially worse.
  - Exact-case email matching (fails closed); no Firebase linking after a fallback login; the check
    and record aren't atomic (a few extra parallel guesses, as in #7); web lock returns HTTP 200 with
    the message rather than 429 (matches how the route renders every other error).
  - Pre-existing, not caused by this fix: `change_password` updates Firebase via
    `firebase_update_password` without guaranteeing the local hash stays in sync.
- **Reviewer verdict**: **APPROVED** — "The fallback is strictly gated to exactly one exact-match
  row with a falsy `firebase_uid`, so linked accounts, case/whitespace variants, duplicate rows,
  disabled accounts and the username→email path all fail closed."

---

## Issue #10 — Local password-reset flow was dead code

- **Severity**: Medium
- **Status**: ✅ **Fixed** (removed)
- **Files changed**: `app.py` (−57/+0), `templates/reset_password.html` (deleted)
- **Decision — remove, don't finish**: a working local reset would change the local
  `password_hash` without changing Firebase, creating exactly the local/Firebase password mismatch
  behind Issue #9's stale-password case. Removing it changes nothing for users, since no token was
  ever generated. The real reset flow — Firebase's hosted one via `forgot_password()` /
  `api_forgot_password()` → `firebase_send_reset_email` → `accounts:sendOobCode` — is untouched.
- **Checked before removal — not exploitable**: nothing ever set a non-empty `reset_token` (only
  read and cleared). On a DB copy, `reset_token='' AND reset_token_exp > now` matched 0 rows
  (`NULL > ?` is NULL); `POST /api/auth/reset-password` with `""`/missing/`null` → 400 before the
  query; `" "`/`"x"` → 400; no password changed.
- **What changed**: removed the web `reset_password(token)` route and `api_reset_password()` (with
  their decorators and section header) and deleted `templates/reset_password.html`. Kept the
  `reset_token`/`reset_token_exp` migration entries and columns — dropping SQLite columns would need
  a table rebuild on existing databases, not worth it for two unused columns.
- **Verification** (reviewer, own DB copy, Firebase mocked):
  - Removal is exactly 57 deleted lines in the two blocks; adjacent functions intact
    (`forgot_password()` → `init_db()`, `api_forgot_password()` → `# --- FAMILY: GET INFO ---`);
    Issue #7/#8/#9 code byte-identical; `py_compile` passes; 3046 CRLF, 0 bare LF.
  - **Firebase's reset email never pointed at the removed route**: `firebase_send_reset_email`
    sends only `{requestType, email}` with no `continueUrl`.
  - Every `url_for` endpoint in all templates and `app.py` exists in `url_map`; every template
    renders with no `BuildError`; no argument-free GET route returns a 5xx.
  - Forgot-password identical to HEAD with a **real CSRF token**: web valid/blank/missing email →
    302 to `/login` with the same flash (mock called only for the valid email); API valid / `{}` /
    blank / non-JSON → 200/400/400/400.
  - Removed endpoints: `GET /reset-password/x` → 404; `POST /api/auth/reset-password` → 405 (only
    the OPTIONS-only catch-all `api_options` on `/api/<path:path>` matches; exposes nothing new).
  - Schema unchanged beyond Issue #7; `init_db()` idempotent; real DB sha256 `8229690d…499d57`
    unchanged; no test referenced either endpoint.
- **Flagged, not fixed**:
  - `import secrets` (`app.py:21`) is unused — only appears inside the Issue #4 guard's message
    strings. Pre-existing; one-line cleanup.
  - `PROJECT_MAP.md` lines ~40, ~206, ~208 still list `reset_password.html`,
    `/reset-password/<token>` and `/api/auth/reset-password` — now stale.
  - Unlinked (Issue #9) users still have no password-reset path at all — Firebase can't email a
    reset link for an account that doesn't exist in Firebase. Follow-up, tied to the new High
    finding below.
- **Reviewer verdict**: **APPROVED** — "Only the two dead reset routes… were removed… Firebase's
  reset email doesn't link to the removed route. No `url_for` breaks, forgot-password behaves
  identically to HEAD."

---

## Issue #11 — No way to delete a family or transfer ownership

- **Severity**: Medium
- **Status**: ✅ **Fixed** (2026-09-18, after the owner's product decision)
- **Files changed**: `app.py` (+40/−0), `templates/settings.html` (+20/−0)
- **Originally deferred** — it needed product
  decisions that a fixer would have to guess at:
  - **Deleting a family** permanently destroys every payment, archived cycle, category, shopping
    item, favorite, feeding, recurring payment and setting belonging to it. Should that be allowed?
    Hard delete or soft delete (recoverable)? Confirmation step? Only when the creator is the sole
    member, or also when others remain (and what happens to them)?
  - **Transferring ownership** needs a new settings UI, and rules: can the owner pick any member?
    Must the new owner accept? What about the system-admin vs. family-admin distinction (Issue #31)?
  - **The mobile app** would need the same flows via `/api/…` routes, so it's also an API design
    question.
- **What is known** (from ISSUES.md, not re-verified by an agent): `leave_family()` blocks the family
  creator with `'Admin cannot leave. Delete family or transfer ownership first.'`, but neither action
  exists; `remove_family_member` blocks self-removal. A creator who made a family by mistake is
  stuck without direct database intervention.
### Decision and implementation

**Owner's decision (2026-09-18): sole-member delete only.** A creator who is the only member may
delete their own family. **Ownership transfer was explicitly declined** as out of scope (it needs a
new UI and acceptance rules), so a creator with other members still cannot leave — they must remove
the other members first.

- **What was added**:
  - `FAMILY_SCOPED_TABLES` (8 tables) and `delete_family()` — `POST /api/family/delete`, decorated
    `@csrf.exempt` + `@require_auth`, matching the sibling `/api/*` routes.
  - `fid` comes **only** from `get_family_id()` (server-side state), never from the request body.
  - Refusals: non-creator member → 403; creator with another member → 400; no family → 403;
    unauthenticated → 401; `GET` → 405.
  - On success, in one `with get_db() as conn:` block: delete the family's rows from all 8 scoped
    tables, set the caller's `users.family_id = NULL`, delete the `families` row, and clear
    `session['family_id']`.
  - `templates/settings.html`: a delete button rendered only for a creator who is the sole member,
    wired through the page's existing `data-*` + `document.addEventListener` delegation (no inline
    `onclick`, per Issue #5), with a confirmation warning that the deletion is permanent.
- **Note on process**: the fixer was **interrupted** before it could self-verify (the orchestrator
  had started #11 out of order and stopped it), so this reviewer verified the change from scratch
  with no fixer claims to check against, and looked specifically for half-finished work. None was
  found.
- **Verification** (reviewer; own DB copies, Firebase and push mocked, threads neutralized):
  - **Authorization — 34 assertions, 0 failures.** Every forgery attempt ignored: a `family_id` in
    the JSON body **and** in the query string, plus `"1"`, `1.0`, `true`, `null`, `[1]`, `{}`. A
    **stale JWT** whose `family_id` claim pointed at another family still deleted only the caller's
    real family, because `auto_jwt_auth` re-reads the user from the DB. A ghost-user token → 401.
  - **Deletion scope**: `family_id` columns enumerated independently via `PRAGMA table_info` across
    all 14 tables → 9 tables have one; the constant covers all 8, and `users` is handled by the
    separate `UPDATE`. **No table missed, no orphan rows.** A second family's full dump was
    byte-identical before and after. The 9 **default** categories (`family_id IS NULL`) survive —
    `family_id=?` cannot match NULL. The caller's `users` row survives with NULL.
  - **`push_tokens` survive by design** (user-scoped) and can never receive a push for the dead
    family, because `send_push_to_family` selects `user_id IN (SELECT id FROM users WHERE
    family_id=?)`.
  - **Atomicity**: injecting a raise on `DELETE FROM feedings` and on `DELETE FROM families` produced
    a **full rollback** (family byte-identical; a retry then succeeded) — `with get_db()` rolls back
    on exception.
  - **State after delete**: `session['family_id']` cleared, `GET /home` → 302 `/family`, `/settings`
    200, a repeat delete → 403 on both session and JWT paths, `/api/payments` with the stale token →
    403. No 500 anywhere.
  - **Body handling**: no body, empty, `{}`, `null`, `[]`, `"x"`, `5`, malformed JSON, form-encoded
    and a 100 KB payload → all 200, no 500. Issue #14's guard is genuinely unnecessary here (the body
    is never read).
  - **UI**: button renders only for creator + sole member; absent for creator + 2 members and for a
    non-creator (whose leave button still renders). jsdom on the real rendered page — 26 assertions,
    0 failures: clicking the button **and** its child `<i>` each fires exactly one confirm, one POST
    and one navigation; declining the confirm fires zero fetches; a 403 shows one Hebrew alert and
    does not navigate. `node --check` clean on all 5 script blocks.
  - `py_compile` passes; `app.py` 3241 CRLF / 0 bare LF / no final newline; `settings.html` 717 CRLF /
    0 bare LF; real DB sha256 `8229690d…499d57` identical at start and end; HEAD `f67fb88`.
- **Flagged, not fixed** (pre-existing, codebase-wide): destructive `/api/` routes are CSRF-exempt via
  the blanket `check_csrf` skip — identical for `leave_family` and `remove_family_member`, mitigated
  by the browser-default `Lax` session cookie (and see Issue #18); `get_db()` connections are never
  explicitly closed.
- **Reviewer verdict**: **APPROVED** — "authorization is derived solely from server-side state and
  survived every forgery attempt I could construct… deletion is correctly limited to the caller's own
  sole-member family across all nine `family_id` tables with no orphans and no damage to another
  family or to the shared NULL-scoped default categories."

---

## Issue #12 — `/api/recurring` POST/PUT skip input validation

- **Severity**: Medium
- **Status**: ✅ **Fixed** — **approved on the second review** (first review rejected; see below)
- **Files changed**: `app.py` (+36/−4)
- **Scope was wider than ISSUES.md said**: besides `add_recurring_to_month()`'s `float(r["amount"])`,
  a stored non-numeric amount also crashed `add_all_recurring()` (`total_amount += r['amount']` →
  `TypeError`), breaking "add all recurring" for the whole family. ISSUES.md also held up
  `add_payment_api()` as the validated reference, but its `float(amount)` still 500s on `"abc"` —
  that route belongs to Issue #14 and was deliberately not touched or copied.
- **Frontend checked first**: `templates/dashboard.html` (`addRecurring` ~592, `saveER` ~627 — the
  only callers) always sends a full body `{description: trimmed string, amount: parseFloat number,
  category: dropdown string}` and never a partial PUT, so partial-update support was **not** added;
  PUT stays a full replace. The UI never reads the POST/PUT response body.
- **What changed**: `import math` and one helper, `_validate_recurring()`, used by both routes. It
  reads `get_json(silent=True)` and requires a `dict`; `description` must be a string, non-empty after
  strip (stored stripped); `amount` goes through `float()` (catching `TypeError`, `ValueError`,
  `OverflowError`), rejects `bool`, must be finite and `> 0`, stored as float; `category` is optional —
  missing, `None`, or whitespace-only defaults to `'כללי'`, a non-string is 400, anything else is
  stored exactly as sent. Failures return `{'error': 'Invalid data'}`, 400 (same shape as
  `add_payment_api`), **before** any DB access. The routes' SQL, `family_id` scoping, and
  `201`/`200` success responses are unchanged.
- **Review round 1 — REJECTED**: the reviewer found that a JSON **integer** too large for a float
  (e.g. 400 digits of 9 sent as a number, not a string) made `float()` raise `OverflowError`, which
  wasn't caught, so POST and PUT returned 500. Nothing was stored, but a 500 like that is exactly what
  this issue exists to remove. Sent back to the fixer with the required change (catch
  `OverflowError`) plus the reviewer's optional suggestion (whitespace-only category → default).
- **Round 2 fix**: exactly two lines changed — `except (TypeError, ValueError, OverflowError):` and
  the whitespace-only category check.
- **Verification** (reviewer, fresh DB copies, push mocked, real `check_budget_alerts`):
  - Rejection case fixed: 400-digit integer amount → 400 on POST (0 rows) and PUT (row unchanged);
    same for a huge negative integer; `"9"*400` and `"1e5000"` become inf → 400.
  - Break-it matrix: `"1e308"`, `1e-320`, `" 150 "`, `"1_000"`, Arabic-Indic `"١٥"` → 201, stored as
    real (all harmless). `"1e309"`, `1e400`, `"Infinity"`, `NaN`, `"0x10"`, `"1 "`, `[150]`,
    `{"v":1}`, `false`, `-0.0` → 400. Non-string description → 400. Category `"   "`/`"\t\n"`/`""`/
    `None`/missing → `'כללי'`; `" קבועים "` stored unchanged; int or list → 400.
  - **Downstream**: every accepted amount stored as `real`; `/api/recurring/<id>/add` → 200 for all
    14 rows (including `1e308`); `/api/recurring/add-all` → 200 with count 14.
  - Real UI payloads: POST `{'שכר דירה', 12.5, 'קבועים'}` → 201; PUT with `99.99` → 200.
  - Issue #7–#10 hunks byte-identical (hunk-body comparison, ignoring `@@` offsets); `py_compile`
    passes; 0 bare LF, no final newline; real DB sha256 `8229690d…499d57` unchanged; HEAD `bb0a195`.
- **Existing tests**: `test_edge_cases.py:502/508` (empty description, zero amount) now get 400,
  which those tests already accept. `test_edge_cases.py:522` sends a partial PUT `{'amount': -50}`
  expecting 200 — it would now get 400 — **but it never actually runs**: like the PUT blocks in
  `test_production.py:329` and `test_api_v2.py:215`, it's guarded by `rec_id = d.get('id')`, and
  `add_recurring` has never returned an `id`, so every recurring-PUT test block is silently skipped.
- **Flagged, not fixed**:
  - **The recurring PUT is untested**: the test suites never exercise `PUT /api/recurring/<id>`
    because POST returns no `id`. Returning the new row's `id` from `add_recurring` would activate
    those tests — and `test_edge_cases.py:522` would then need updating, since it asserts that a
    negative amount is accepted.
  - A JSON-escaped lone surrogate (`\ud800`) in `description` or `category` passes validation and then
    500s at the SQLite write (`UnicodeEncodeError`). Nothing is written, and it was already true at HEAD.
  - Cross-family PUT returns 200 without modifying anything (pre-existing; no 404 added).
  - No length limit on `description` (pre-existing).
- **Reviewer verdict**: **APPROVED** (round 2) — "No amount that passes validation can crash
  `add_recurring_to_month` or `add_all_recurring`… The one remaining 500, a lone surrogate in
  description or category, fails at the database write, writes nothing, and was already there at
  HEAD."

---

## Issue #13 — `add_feeding` could return 500 after the DB write had committed

- **Severity**: Medium
- **Status**: ✅ **Fixed** — approved, then re-approved after a follow-up change on the reviewer's
  recommendation
- **Files changed**: `app.py` (+47/−16)
- **The bug, confirmed**: `with get_db() as conn:` commits on exit, and the push text was built
  *after* that with `int(amount_val)`. A bottle feeding with amount `"abc"`, `"120.5"` (as a string),
  inf, etc. returned 500 although the row was already saved — so a client retry created a
  **duplicate feeding**. A non-dict body also 500'd (before the write).
- **Investigated first**:
  - **UI** — the only caller is `templates/baby_tracker.html:367` (`submitAdd`). Every type sends
    `{feeding_type, amount, notes, custom_time}` (never `duration`); `feeding_type` is always one of 6
    values; `amount` is a JS number from `parseFloat(...)||0` (0 for diaper/medication, can be
    fractional, can be **negative** if typed; a typed `1e400` arrives as JSON `null`); `custom_time`
    comes from `<input type="time">` as `"HH:MM"` or `""`.
  - **Schema** — `amount REAL DEFAULT 0`, `duration INTEGER DEFAULT 0`.
  - **Downstream readers** (pre-existing crashes on bad stored values, all confirmed on a copy): see
    the flagged items below.
- **What changed** (all inside `add_feeding` plus two module constants and one helper):
  - `get_json(silent=True)`; a non-dict body → 400 `{'error': 'Invalid data'}` before any DB access.
  - `_parse_feeding_number()` for `amount` and `duration`: missing/None/`''` → 0.0; `bool` rejected;
    `float()` catching `TypeError`, `ValueError`, **`OverflowError`** (the Issue #12 lesson); must be
    finite and within `±FEEDING_NUMBER_MAX` (1,000,000); stored as float.
  - `feeding_type` must be one of `FEEDING_TYPES` (the 6 UI values).
  - A truthy `custom_time` must be a string fully matching `([01][0-9]|2[0-3]):[0-5][0-9]`
    (ASCII digits, `re.fullmatch`, so `"08:30\n"` is rejected).
  - Everything after the committed write — label lookup, `int(amount)`, the `request.api_user`/
    `session` lookups and the push send — is inside `try/except Exception`, logging `ascii(e)` so the
    log line itself can't hit the cp1255 crash.
  - SQL, `family_id` scoping, the `201 {'success', 'id'}` response and the push text are unchanged.
- **Follow-up change (review round 2)**: the first version also rejected negative amounts. The
  reviewer approved it but recommended against that: `submitAdd` ignores the response and always runs
  `closeAdd(); loadData()`, the breastfeeding input has no `min`, and `min="0"` elsewhere doesn't stop
  typing a minus sign — so a negative entry that HEAD saved would now **vanish without any message**.
  It also showed that two accepted sleep entries of `1e308` sum to inf and crash `home_summary`
  (`int(inf)` → `OverflowError`). Both recommendations were taken: negatives accepted again (same as
  HEAD), plus the `±1,000,000` magnitude bound. Exactly three lines changed.
- **Verification** (reviewer, fresh DB copies, HEAD loaded as a separate module on its own copy, push
  mocked, reminder thread neutralized; 140 requests in round 1, 170 in round 2):
  - **No 500 after a committed write, for any input.** Every line after the commit is guarded except
    `return jsonify(...)` with `cur.lastrowid`, which cannot raise.
  - Real UI payloads for all 6 types (amounts 120, 0, 12.5, −5; with and without a time) → 201, with
    stored rows and push text identical to HEAD. One documented difference: `amount: null` is now
    stored as 0.0 (HEAD stored NULL, which crashed `/api/feedings/data`).
  - The original bug: bottle `"120.5"` → 201, push `— 120 מ"ל`, exactly one row. A raising push or
    raising composition → still 201 with exactly one row.
  - 400 with 0 rows: amount/duration `±1000001`, `1000000.0000001`, `±1e308`, `±1e400`, 5000-digit ints
    of either sign, `NaN`/`Infinity`/`"inf"`/`"nan"`, `"abc"`, `"0x10"`, lists, objects, `true`/`false`;
    bodies that are an array/null/string/number; `custom_time` `24:00`, `9:30`, `" 08:30"`,
    `"08:30\n"`, Arabic-Indic or fullwidth digits, non-strings; `feeding_type` `Bottle`, `" bottle"`,
    a number, null, missing.
  - Accepted (201): `±1000000`, `999999.9999`, `-0.0`, `" -50 "`, `"-1_000_000"` (normalized to
    −1000000.0 — HEAD stored the text), Arabic-Indic/fullwidth digits in the amount; `custom_time`
    `0`/`false`/`""`/`null` fall back to the current time, as at HEAD.
  - **Readers survive the bound**: 1,000 sleep + 900 bottle/breastfeeding/solid entries at 1e6 →
    `home_summary` 200 and `/api/feedings/data` 200; negative totals → both 200.
  - Issue #7–#12 hunks byte-identical; `py_compile` passes; 0 bare LF; real DB sha256
    `8229690d…499d57` unchanged; HEAD `bb0a195`.
- **Existing tests**: `test_edge_cases.py:388` (invalid type) and `:394` (empty type) now get 400;
  both already accept `[201, 400]`. All other feeding amounts in `test_files` are between 0 and 99999.
- **Flagged, not fixed** (all pre-existing, all confirmed on a DB copy):
  - **`update_feeding` is unvalidated**: it still stores a raw `amount` (text, inf) and returns 500 on
    a non-dict body. It is now the only route that can store the bad amounts the readers below choke on.
  - **Readers crash on bad stored values**: `/api/feedings/data` does `float(f['amount'])` with no
    try — a stored text or NULL amount 500s that view. `home_summary` 500s on a stored inf sleep amount.
  - **Feeding reminders can silently stop**: `check_feeding_reminders()` picks the latest feeding with
    `ORDER BY date DESC`, and a malformed date sorts above valid ones. The thread survives (per-family
    `try/except`) but that family gets no reminders, with an error printed every 60 s. A date like
    `today + " ab:cd:00"` suppresses reminders until a feeding on a later day is logged; a date like
    `"garbage"` suppresses them permanently. Neither `add_feeding` nor `update_feeding` can currently
    write such a date (both keep a valid date prefix) — but it's fragile.
  - **The baby tracker never reports save failures**: `submitAdd` ignores the HTTP response, so any 400
    closes the form and the entry silently doesn't appear. Adding `response.ok` handling with a toast
    would make every validation fix in this app visible to the user.
  - Non-string `notes` (a list or dict) still 500s at the SQL bind, with nothing written — same as HEAD.
- **Reviewer verdict**: **APPROVED** (round 2) — "Negatives are accepted again with the same stored
  values and push text as HEAD, so saves from the app no longer disappear silently. Values that aren't
  finite or fall outside ±1e6 are rejected before the write… no input I tried produced a 500 after a
  write."

---

## Issue #14 — Inconsistent JSON body parsing across API routes

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+66/−20; one helper + a guard in 20 routes)
- **ISSUES.md's framing corrected**: the installed Flask is **3.1.3** (`requirements.txt` says 3.0.3).
  A bare `get_json()` does not 500 on malformed JSON or a wrong content type — Flask returns 400/415.
  The real 500s came from bodies that are **valid JSON but not an object** (`null`, `[]`, `"x"`, `5`,
  `true`), after which routes call `data.get(...)`, `'x' in data` or `data[...]`. The
  `get_json(silent=True) or {}` pattern — used by the "newer" routes ISSUES.md held up as the safe
  example — still let truthy non-objects (`[1]`, `"x"`, `5`) through.
- **Worse than a 500 in three places**: before the fix, `update_payment` with a `[]`, `[1]` or `"x"`
  body returned **200 and sent a push** to the family; `update_feeding` with `[1]`/`"x"` returned 200;
  and `api_update_family_settings` with a `null` body returned 200 and **inserted a default settings
  row**.
- **What changed**: helper `get_json_object()` (after `get_token_from_request`) returns the body if it
  is a `dict`, else `None`. In 20 routes the body read is replaced by the helper plus a 400 return,
  placed **before any DB access or side effect**:
  - `{'error': 'Invalid data'}` — `add_category`, `add_payment_api` (guard now runs before
    `get_cycle_month`), `update_payment`, `add_shopping_item`, `update_shopping_item`,
    `delete_favorite`, `add_new_favorite`, `edit_favorite`, `update_feeding`,
    `api_update_family_settings` (after its existing session-only 403 no-family check).
  - The route's **existing** empty-body message, so null/`[]`/malformed get the same response as `{}`
    did — `remove_family_member` (`user_id נדרש`), `api_login`, `api_register`,
    `api_change_password`, `api_forgot_password`, `api_create_family`, `api_join_family`,
    `api_update_profile`, and both push-token routes.
  - Left untouched: `add_recurring`, `update_recurring`, `add_feeding` — already covered by Issues
    #12/#13. No route had a missing-key `KeyError` (every subscript was guarded).
- **Acknowledged behavior changes** (reviewer confirmed none breaks a real caller):
  - Malformed JSON / wrong content type → our JSON 400 instead of Flask's 400/415. Nothing in the
    templates, `test_files`, or Android sources expects 415.
  - `api_update_family_settings` with null/`[]`/malformed/empty body → 400 instead of 200 (and no
    longer inserts a row). Both real callers (`settings.html`, the onboarding popup in
    `dashboard.html`) always send an object.
  - `remove_family_member` with a garbage body from a non-admin → 400 instead of 403. Reveals nothing;
    the admin path and the valid-body non-admin 403 are unchanged.
- **Verification** (reviewer; HEAD and current loaded as separate modules on separate DB copies; push,
  Firebase, mail and threads mocked; network blocked; clock fixed):
  - **Inventory independently confirmed**: HEAD has 23 JSON-body reads (`request.json`,
    `request.data`, `get_data` unused); 20 use the helper, 3 keep their #12/#13 checks. No route missed.
  - **26 route variants × 10 non-object bodies** → JSON 400 every time (one no-family case keeps its
    existing 403), with no DB write and no push. HEAD gave many 500s on the same requests.
  - **Guard placement** read in all 20 routes: right after `get_family_id()`, which only reads the
    session/request. No decorator line changed.
  - **Behavior preservation**: 66 requests — `{}` on every route plus real `fetch` payload shapes from
    the templates, including the mobile JWT paths (email login, local username login,
    username→email), register, and push-token register over session and JWT. For all 20 changed
    routes, status, JSON, push/Firebase/mail calls and DB changes match HEAD (63/66, ignoring
    `created_at`; the 3 differences are `{}` on the #12/#13 routes, already documented).
  - **Odd bodies**: duplicate key (last wins), `{"__proto__":1}`, UTF-8 BOM prefix, UTF-16 with
    `charset=utf-16`, `application/vnd.api+json` — all parsed normally, none 500.
  - All 17 earlier hunks byte-identical; `py_compile` passes; 3155 CRLF, 0 bare LF; real DB sha256
    `8229690d…499d57` unchanged; HEAD `bb0a195`.
- **Existing tests**: none sends a non-object JSON body. `test_edge_cases.py:675` sends no body and
  accepts 400 or 500 — now 400. No test relies on 415.
- **Flagged, not fixed — field-level 500s** (body is an object, but a field has the wrong type; all
  confirmed or spot-checked on a copy):
  - **🟠 `update_payment` with `{"amount": "abc"}` returns 500 _after_ committing** — the row really
    holds `amount='abc'` and no push is sent. Same bug pattern as Issue #13, on the payments table. The
    bad stored amount can then break any reader that does `float(p['amount'])`. **Most important item
    on this list.**
  - `update_feeding` with `{"time": 5}` returns 200 and stores the date `2026-09-17 5:00` (malformed —
    the kind of date that can confuse the reminder ordering described under Issue #13).
  - `.strip()` on a non-string field → 500: `name` (category, shopping item, both favorite routes),
    `description`, `email`/`username` (login), `display_name` (register, profile), `family_name`,
    `invite_code`, `token` (push routes). `len()` on a non-string password (register,
    change-password).
  - Conversions → 500: `add_payment_api` `float(amount)` on `"abc"`/`[1]`; `remove_family_member`
    `int("abc")`; family settings `int(cycle_day)` on `"abc"`.
  - List/dict values reaching the SQLite bind → 500 (`category`, `color`, `quantity`, `budget_*`, the
    update routes).
  - **JSON nested ~5,000 levels deep** raises `RecursionError` during parsing (not caught by
    `silent=True`) → 500 on **every** JSON route. Pre-existing at HEAD, happens before any write.
    Mitigate with `MAX_CONTENT_LENGTH` and/or catching `RecursionError` in the helper.
- **Reviewer verdict**: **APPROVED** — "no JSON route still returns 500 on a non-object body. In every
  changed route the guard runs before any database access, push, Firebase call or session change…
  Valid frontend and mobile requests and `{}` bodies behave exactly as at HEAD."

---

## Issue #15 — Daily budget alert had no dedup

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+5/−1)
- **The bug, confirmed**: in `check_budget_alerts()`, the monthly 80%/100% alerts dedup against
  `family_settings.budget_alert_80_sent` / `budget_alert_100_sent` (the cycle month), but the daily
  check was just `if daily_total > budget_daily: send_push_to_family(...)`. Once a family was over its
  daily budget, **every** later payment add, edit, or recurring add sent the same push again.
- **What changed** — mirrors the monthly pattern exactly:
  1. New column `budget_alert_daily_sent TEXT DEFAULT ''`, added both in `CREATE TABLE family_settings`
     (fresh databases) and in the `init_db()` ALTER migration loop (existing databases), the same two
     ways the 80%/100% markers are added.
  2. The daily check now alerts only if `daily_total > budget_daily` **and**
     `budget_alert_daily_sent != today`, then writes `today` to the column in the same `with get_db()`
     block (which commits on exit, as the monthly markers do).
  3. The alert is marked sent **whatever `send_push_to_family` returns** (e.g. `no_tokens`) — the same
     choice the monthly alerts already make. Push text, thresholds and prints unchanged.
- **Verification** (reviewer; own script, fresh DB copies, JWT test client, push stubbed, threads
  neutralized, `now_israel` patched, HEAD loaded as a separate module on its own copy):
  - **Diff integrity despite merged hunks**: git merged two earlier hunks with this edit, so a raw
    hunk comparison no longer lines up. Proven instead by hashing: applying `pre_edit.diff` to
    `HEAD:app.py` and LF-normalizing gives blob `f676a62` — exactly the post-image recorded in
    `pre_edit.diff` — and `diff -u` between that reconstruction and the current file shows only this
    +5/−1 change. (All hashes of the LF-normalized form; checked two ways, so `core.autocrlf` doesn't
    skew it.)
  - **Push counts**: cross the budget, then add / update / recurring-single / recurring-all / web
    `/add_payment` → **1** daily push that day; day 2 → 2; day 3 → 3. **HEAD sent 11** over the same
    sequence.
  - **Edge cases**: total exactly equal to budget → no push (strict `>` kept; +0.01 → 1 push);
    `budget_daily` 0 or NULL → no push, row byte-for-byte unchanged; total drops below budget after a
    delete, then re-crosses the same day → still 1 push; midnight — 23:59:59 fires for day 1, 00:00:01
    at a lower total doesn't, crossing on day 2 fires again (`today` and the stored payment `date` both
    come from `now_israel()`, so marker and `date(date)=?` use the same day); no `family_settings` row →
    early return, no row created.
  - **Monthly behavior identical to HEAD**: push titles/bodies and 80/100 markers match exactly,
    including the re-fire on the next cycle; the monthly block is byte-identical.
  - **Migration**: on a filesystem copy of the real DB, the column is added with `''`, every other
    `family_settings` value is unchanged, `init_db()` ran three times without error, and the tuple sits
    inside the same `try/except OperationalError` loop. On a fresh DB the column exists. The `CREATE
    TABLE` diff against HEAD is a single added line.
  - All 5 `check_budget_alerts(fid)` call sites unchanged. `py_compile` passes; 3159 CRLF, 0 bare LF;
    real DB sha256 `8229690d…499d57` unchanged; HEAD `bb0a195`.
- **Existing tests**: nothing in `test_files/` expects a repeated daily alert or lists `family_settings`
  columns; `test_edge_cases.py` 467-494 only checks status codes.
- **Flagged, not fixed** (pre-existing semantics, shared with the monthly alerts):
  - Check-then-send race: two payments at the same moment can both see "not sent" and both push.
  - Changing a budget doesn't reset any marker — raising the budget mid-day and exceeding it again
    won't re-alert that day.
- **Reviewer verdict**: **APPROVED** — "The daily alert now fires exactly once per Israel day through
  every caller and fires again on each new day, including across midnight… Monthly pushes and markers
  match HEAD exactly."

---

## Issue #16 — FCM push worker never pruned dead tokens

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+35/−0)
- **The bug, confirmed**: `_send_push_worker` POSTs to FCM once per token and only prints on any
  exception, so tokens from uninstalled apps stay in `push_tokens` forever and every push to that family
  retries them.
- **Design decision — prune only on a definitive signal**: a token is deleted **only** when FCM's error
  body contains an `FcmError` detail (`@type` `type.googleapis.com/google.firebase.fcm.v1.FcmError`)
  with `errorCode == "UNREGISTERED"`. Deliberately **not** on:
  - a bare **404** — a wrong `project_id` also returns 404, and pruning on it would wipe every token for
    every family;
  - **`INVALID_ARGUMENT`** (400) — it can mean a bad token *or* a bad payload, so one malformed message
    could wipe every token;
  - `SENDER_ID_MISMATCH`, 401/403, 429, 5xx, timeouts, network errors, or unreadable bodies.
- **What changed**:
  - New helper `_is_unregistered_fcm_error(body_bytes)` that never raises and matches the rule above
    exactly (`error.details` must be a list containing that dict).
  - In the worker, a new `except urllib.error.HTTPError` branch **before** the generic `except`. It
    prints the same `Push send error` line as before, reads the body capped at 64 KB inside try/except,
    and if the helper matches, runs `DELETE FROM push_tokens WHERE token=?` for **that loop iteration's
    token** inside its own try/except. New log lines are plain ASCII and print only the first 12
    characters of the token.
  - Unchanged: the success path, payload, headers, timeout, loop order, `send_push_to_family` and its
    Issue #8 statuses, credential/project lookups, `_fcm_credentials` (Issue #17).
- **Verification** (reviewer's own 58-check script; fresh DB copy, sockets blocked, `urlopen` mocked,
  worker called synchronously, HEAD's worker extracted for comparison):
  - **Integrity**: `pre_edit.diff` applied to `HEAD:app.py` with no fuzz reproduces post-image
    `07c2eaaf539b…a1130fea`; `diff -u` against the current file shows only the #16 hunks.
  - **Success path**: URL, data, headers, method POST, timeout=10 byte-identical to HEAD; a 200
    response is never read or parsed, even if its body contains `UNREGISTERED`.
  - **Exception order**: a spy confirmed `URLError` and `socket.timeout` still go to the old branch and
    never reach the helper; `HTTPError` reaches the new one.
  - **Deletes**: B `UNREGISTERED` → only B removed; all three `UNREGISTERED` → all three removed and an
    **other family's token** kept; A `UNREGISTERED` + C 500 → only A removed.
  - **No delete, loop continues**: 404 without an `FcmError` detail; `UNREGISTERED` only in
    `status`/`message`; wrong or missing `@type`; lowercase `unregistered`; `"UNREGISTERED "` with a
    trailing space; 400 `INVALID_ARGUMENT` with and without a detail; 403 `SENDER_ID_MISMATCH`; 401; 429;
    500; 503; `URLError`; `socket.timeout`; `TimeoutError`; `ConnectionResetError`; malformed bodies
    (non-JSON, empty, `read()` raising, `read()` returning None, `fp=None`, 10 MB with the marker past
    64 KB, `null`, `[]`, `error:null`, `details` as string/dict, non-string `errorCode`, invalid UTF-8);
    **deeply nested JSON raising `RecursionError`** inside `json.loads`, at both 400 KB and 60 KB — caught,
    helper returns False, nothing escapes.
  - **DB failure during delete**: all three tokens still attempted, nothing deleted, log shows
    `Push token cleanup failed: OperationalError`.
  - **Delete safety**: parameterized SQL on a `NOT NULL UNIQUE` column (at most one row); an
    injection-shaped token `x' OR 1=1 --` deleted only its own row. Only the token FCM rejected can be
    deleted.
  - **Logging**: captured under strict cp1255 — pure ASCII, nothing escaped; a long token's
    `SECRETSUFFIX` never appeared in output.
  - `py_compile` passes; 3194 CRLF, 0 bare LF; real DB sha256 `8229690d…499d57` identical at start and
    end; HEAD `bb0a195`.
- **Existing tests**: nothing in `test_files/` references `_send_push_worker` or token pruning;
  `push_tokens` deletes there are only test setup/cleanup by `user_id`.
- **Flagged, not fixed**:
  - `SENDER_ID_MISMATCH` (token belongs to another Firebase project) is also permanently dead for this
    project and is a reasonable future pruning candidate. `INVALID_ARGUMENT` is too ambiguous to prune
    on without more detail.
  - An `UNREGISTERED` marker beyond the 64 KB read cap is ignored — real FCM error bodies are far
    smaller.
  - The `HTTPError` response object isn't explicitly closed; like every `get_db()` connection in
    `app.py`, it's left to garbage collection.
- **Reviewer verdict**: **APPROVED** — "a token is pruned only when an `HTTPError` body contains an
  FcmError detail with an exact `errorCode == "UNREGISTERED"`. Every other signal I tried deleted
  nothing… No exception escaped the loop. The delete is parameterized and hits only the rejected token's
  unique row."

---

## Issue #17 — `_fcm_credentials` OAuth2 cache mutated without a lock

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+15/−8)
- **ISSUES.md understated it — this was a lost-push bug, not just wasted work.**
  `get_fcm_access_token()` checked, created, refreshed and then **re-read the module global** to
  return the token. If thread A refreshed credential X while thread B replaced the global with a
  fresh, unrefreshed Y, A returned `Y.token` — still `None`. `send_push_to_family` treats that as
  `'no_credentials'` and **silently skips the push**. Reproduced deterministically on HEAD with forced
  interleaving: A got `None`, 2 creates and 2 refreshes; through `send_push_to_family` it returned
  `'no_credentials'` and started 0 workers.
- **What changed**: `_fcm_credentials_lock = threading.Lock()` next to `_fcm_credentials`. The
  check → create → refresh → token-read sequence now runs inside `with _fcm_credentials_lock:` using a
  local `creds`, and the function returns `creds.token` — always from the credential that same call
  validated. The missing-file check and its print stay outside the lock (filesystem read only). File
  path, scopes, prints, the outer `except` and the `None` returns are identical to HEAD. A plain
  `Lock` is safe: nothing inside the region calls back into app code or takes another lock (it's the
  only lock in `app.py`).
- **Verification** (reviewer's own script; functions extracted from HEAD and the working tree, google-auth
  mocked, sockets blocked, `app` never imported, no DB opened):
  - **Integrity**: `pre_edit.diff` applied to `HEAD:app.py` → blob `8e67b5c242bc…b51810`, matching
    the recorded post-image; `diff -u` shows only #17.
  - `_fcm_credentials` is read/written only inside the lock (grep: init, `global`, one read, one write).
  - **Forced interleaving**: HEAD → A `None`, B `tok-2`, 2 creates + 2 refreshes. Fix → B blocks on
    the lock while A refreshes; both get `tok-1`, 1 create + 1 refresh.
  - **Stress, 100 threads × 5 rounds** (credential alternately `None`/expired, refresh sleeping
    0–10 ms): fix → exactly 1 create, 1 refresh, **0 `None`**, one distinct token per round. HEAD for
    contrast → 100 creates per round and **25–88 `None` results per round**.
  - Single-threaded behavior identical to HEAD (`tok-1 tok-1 tok-2`, 2 creates + 2 refreshes after
    expiry).
  - Error paths — create raising, refresh raising, `.token` raising, missing file → `None` with the
    same print as HEAD; the next call completes within 3 s and the lock isn't left held.
  - `py_compile` passes; 3201 CRLF, 0 bare LF; real DB sha256 `8229690d…499d57` unchanged; HEAD `bb0a195`.
- **Flagged, not fixed — refresh latency** (confirmed in installed google-auth 2.49.1):
  `transport/requests.py:47` sets a 120 s default timeout, and `_client.py:190` retries the token
  request up to 3 times with exponential backoff (1 s start, ×2). A hung refresh can make push callers —
  including request handlers, since `send_push_to_family` fetches the token synchronously — queue
  behind the lock for several minutes. Before the fix each caller would hang on its own refresh, so this
  isn't new, but a shorter timeout on the refresh `Request` would be a worthwhile hardening.
- **Reviewer verdict**: **APPROVED** — "Every read and write of `_fcm_credentials` is inside a
  `with`-managed lock, and the token returned comes from the credential that same call checked and
  refreshed… The 100×5 stress test gave exactly one create and one refresh per round and no `None`."

---

## Issue #18 — Session and CSRF cookies had no `Secure`/`SameSite`

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+12/−1). `templates/settings.html` byte-identical.
- **The gap**: no `SESSION_COOKIE_SECURE`/`SAMESITE`/`HTTPONLY` config existed, and
  `inject_csrf_token()` set the `csrf_token` cookie with **no flags at all**. The app has genuinely
  been served over plain HTTP (the Capacitor config used a LAN IP with `cleartext: true`), so neither
  cookie was protected against interception.
- **Two hard constraints, both honoured**:
  1. **`csrf_token` must stay non-HttpOnly** — `base.html`'s fetch shim reads it from
     `document.cookie` (Issue #6). Making it HttpOnly would 400 every web POST/PUT/DELETE. It is now
     set with an **explicit** `httponly=False` plus a comment saying why, so nobody "hardens" it later
     and breaks CSRF.
  2. **`Secure` is gated on `APP_ENV == 'production'`** (the Issue #4 flag), so local HTTP development
     keeps working.
- **What changed**: `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`,
  `SESSION_COOKIE_SECURE = (APP_ENV == 'production')` next to the existing CSRF/Mail config; and
  `inject_csrf_token()` now passes `httponly=False, samesite='Lax', secure=(APP_ENV == 'production')`.
  Cookie name, value and path unchanged. CSRF enforcement, `check_csrf`, the shim, auth and all routes
  untouched.
- **Verification** (reviewer; raw `Set-Cookie` headers **and** runtime `app.config`, DB copies,
  Firebase stubbed, threads no-op'd):

  | Mode | `csrf_token` | `session` |
  |---|---|---|
  | dev (`APP_ENV` unset, http) | `Path=/; SameSite=Lax` — **no HttpOnly, no Secure** | `HttpOnly; Path=/; SameSite=Lax` — no Secure |
  | prod (`APP_ENV=production`, https) | `Secure; Path=/; SameSite=Lax` — still **no HttpOnly** | `Secure; HttpOnly; Path=/; SameSite=Lax` |

  - **Shim still works**: token parsed with `base.html:173-174`'s own logic (91 chars, no `=` padding to
    truncate), sent as `X-CSRFToken` → `/add_payment` 302 with `payments` 0→1 **in both modes**;
    without the header → 400, 0 rows.
  - **Dev HTTP login not broken**: `GET /login` → `POST /login` 302 `/home` → `GET /home` 200 → a
    CSRF-protected POST wrote a row.
  - **Capacitor `SameSite=Lax` is a no-op**, verified independently: `capacitor.config.json` points
    `server.url` at the remote HTTPS host, so the WebView's document origin **is** the server;
    `MainActivity` extends `BridgeActivity` with no custom `loadUrl` (only `getBridge().reload()`);
    `www/index.html` (2418 B) has **zero** `fetch`/`XHR`/`axios`. Every cookie-bearing request is
    same-origin. The `capacitor://localhost` CORS entry only covers `/api/*`, which is `@csrf.exempt` +
    Bearer JWT and sends no cookies. (Android WebView is Chromium, which has defaulted to `Lax` since
    Chrome 80, so this only makes existing behavior explicit.)
  - **JWT/mobile unaffected**: empty cookie jar + Bearer → `GET /api/payments` 200 and
    `POST /api/payments/add` 201 with a row written, in both modes.
  - **`logout()`**: the flagless `delete_cookie('csrf_token')` still clears (deletion matches on
    name/path); `inject_csrf_token` then appends a fresh cookie, which is byte-for-byte HEAD behavior.
    A later `GET /home` 302s to `/login` in both modes.
  - **Integrity**: git blob chain confirms `app.py 0f72e83 → 15c0c37` and
    `settings.html 21762d1 → 893a1e8`, with the working `settings.html` `cmp`-identical to the pre-#18
    reconstruction; `diff -u` shows only the 2 #18 hunks. Issue #11 intact (`FAMILY_SCOPED_TABLES`,
    `delete_family`, both `data-delete-family` hooks). `py_compile` passes; 3252 CRLF, 0 bare LF, no
    final newline. Real DB sha256 `8229690d…499d57` identical at start and end; HEAD `f67fb88`.
  - The fixer reported `+14/−1` and two sha256 prefixes the reviewer couldn't reproduce; the actual diff
    is **+12/−1** and the git-blob/`cmp` evidence supersedes the prefixes. Cosmetic reporting slip, not
    a code issue.
- **Existing tests**: no test file mentions cookies, and the suites POST only to `/api/*` over
  `http://127.0.0.1` with `APP_ENV` unset, so `Secure` never applies. `locustfile.py` reads
  `csrf_token` from the `requests` cookie jar — unaffected in dev.
- **Reviewer verdict**: **APPROVED** — "`csrf_token` stays non-HttpOnly so the `base.html` shim keeps
  working… `Secure` appears only when `APP_ENV == 'production'` so dev login and writes over plain HTTP
  are unaffected."

---

## Issue #19 — `mail.send()` had no SMTP timeout (and ran inside a DB transaction)

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+105/−25 vs HEAD, 6 hunks). `templates/settings.html` byte-identical.
- **Worse than ISSUES.md described.** ISSUES.md only noted the missing timeout. In fact the
  `mail.send()` call sat **inside** `with get_db() as conn:` in **both** change-password routes (a
  Hebrew comment at the old line 843 said so deliberately). `get_db()` returns a raw
  `sqlite3.Connection`, and `with conn:` is a **transaction** context manager — so a hung SMTP call
  held the RESERVED write lock from the `UPDATE users` for the entire hang, not just the request
  thread.
- **Why a background thread rather than a timeout** (verified in the installed source, not guessed):
  **Flask-Mail 0.10.0**'s `Connection.configure_host()` calls `smtplib.SMTP(host, port)` with **no
  `timeout` argument**, and `init_mail()` reads exactly 11 config keys with **no `MAIL_TIMEOUT`**. A
  config timeout is impossible. `socket.setdefaulttimeout()` was deliberately **not** used — it is
  process-global and would also affect Firebase, FCM and other sockets.
- **What changed**: new `send_mail_async(msg)` next to `mail = Mail(app)` — a **daemon** thread
  running `with app.app_context(): mail.send(msg)`, with `try/except → print('Mail error: …')` both
  inside the worker and around `Thread.start()`, mirroring `send_push_to_family`. Both routes now
  capture the row data they need inside the `with` block, then build and dispatch the mail **after**
  it. Subject, recipients, sender and HTML are unchanged.
- **Verification** (reviewer's own measurements; HEAD loaded as a separate module on its own DB copy,
  sockets blocked, mail stubbed):

  | | HEAD | Fixed |
  |---|---|---|
  | Request time during a blocked send (web / api) | 3.50 s / 3.52 s | **0.17 s / 0.16 s** |
  | Concurrent second-connection `UPDATE users` during the hang | `OperationalError: database is locked` after ~2.3 s | **OK in 0.01 s** |

  - **The email is provably unchanged**: `subject`, `recipients`, `sender`, `html`, `body`, `cc`,
    `bcc`, `reply_to`, `extra_headers`, `charset` all compare equal between HEAD and the fix on both
    routes (diff dict `{}`); raw `as_bytes()` differs only in random MIME boundaries and `Message-ID`.
    html sha256: web `538b1e7c…`, api `44d4e312…`.
  - **10/10 behavior cases identical to HEAD** across both routes: success (302→`/home` + the same
    flash / 200 + the same Hebrew JSON, with the new password hash active), wrong current password
    (302→`/settings` + error flash / 401), short password (400), `email IS NULL`, `email = ''` (change
    succeeds, **0** mails sent). A mail failure still never fails the request.
  - **Thread correctness**: `daemon=True` (verified by intercepting `threading.Thread`); a proper app
    context confirmed by re-running the **real** Flask-Mail path with `suppress=True`; worker
    exceptions and a failing `Thread.start()` are both caught; 50 always-failing sends → no crash, no
    thread growth (5→5). **No request-bound state is read in the thread**: `Message.__init__` resolves
    `sender` from `current_app` at construction time, the HTML is a plain f-string over already-copied
    `sqlite3.Row` values, and `notify_email` is captured inside the `with`. The thread touches only the
    module globals `app`/`mail` and the finished `msg`.
  - Issues #4, #11 and #18 intact; `templates/settings.html` byte-identical to the pre-#19
    reconstruction (`cmp` clean); recorded blob hashes reproduce exactly; `diff -u` shows only the 6
    #19 hunks. `py_compile` passes; 3281 CRLF, 0 bare LF, no final newline, no BOM. Real DB sha256
    `8229690d…499d57` identical at start and end; HEAD `f67fb88`.
- **Existing tests**: `/api/auth/change-password` appears in `test_flows.py:175,190,196` and
  `test_deep_audit.py:168,179`, all asserting only status codes and a subsequent login — all
  unchanged. No test touches the web route or asserts on mail.
- **Flagged, not fixed**: a permanently-hung SMTP now leaks one **daemon** thread per change-password
  request instead of blocking a request thread — strictly better, but still unbounded. A `Mail`
  subclass that passes a `timeout` to `smtplib`, or a bounded worker queue, would close it.
- **Reviewer verdict**: **APPROVED** — "The email is provably unchanged… All ten behavior cases
  across both routes are identical to HEAD… My own measurements reproduce the win (3.5 s → 0.17 s, and
  `database is locked` → `OK in 0.01 s` for a concurrent write)."

---

## Issue #20 — Background scheduler threads weren't safe for multi-worker deployment

- **Severity**: Medium
- **Status**: ✅ **Fixed**
- **Files changed**: `app.py` (+75/−0, 5 hunks). `templates/settings.html` untouched.
- **The problem**: `check_auto_archive()` (300 s loop) and `check_feeding_reminders()` (60 s loop) start
  as daemon threads at **import**, so under gunicorn every worker runs its own copy of both loops
  against the same SQLite file.
- **Why a code fix rather than a deployment setting**: `docker-compose-new.yml` builds the app from
  `/docker/ourhome` **on the VPS**, so the Dockerfile and its gunicorn command are not in this repo —
  the worker count is unknowable here. ISSUES.md suggested gating on `WEB_CONCURRENCY`, but that would
  need configuration nobody can verify from the repo, and would silently disable the jobs if forgotten.
  A **DB-backed lease** is automatic, configuration-free, and cannot regress a single-worker deployment.
- **What changed**: `import uuid`; a `scheduler_leases (job_name TEXT PRIMARY KEY, owner TEXT NOT NULL,
  expires_at TEXT NOT NULL)` table added to `init_db()`'s executescript like `login_attempts`;
  `SCHEDULER_OWNER_ID` (pid + random hex, computed once at import); `_note_lease_lost()` (one ASCII
  line, once per job); and `_acquire_scheduler_lease(job_name, ttl)` built on a single atomic SQLite
  **UPSERT** — `ON CONFLICT(job_name) DO UPDATE … WHERE scheduler_leases.owner = excluded.owner OR
  scheduler_leases.expires_at < ?` — so it can only **renew its own** lease or **steal a genuinely
  expired** one, confirmed by reading the row back. It never raises (returns `False` on any error) and
  always closes its connection. Each loop calls it first inside `while True:` (ttl 900 archive, 180
  reminder) and skips that tick if it isn't the owner. Job logic and all dedup columns are untouched.
  Runtime `sqlite3.sqlite_version` is **3.35.5**, so UPSERT is supported (no fallback needed).
- **Verification** (reviewer's own tests, real OS processes — gunicorn forks, so threads would not be
  valid evidence):
  - **Barrier test**: 6 processes × 40 rounds → exactly 1 winner in 40/40 rounds, one lease row.
  - **Expiry-boundary test** (all processes spin until the code's own string comparison says expired,
    then fire at once): 6×30, 8×45 and 10×50 → **107 rounds, zero double-wins**, with all 8 processes
    winning some round (proving real stealing, not starvation).
  - **Negative control**: the identical harness against a naive SELECT-then-UPDATE produced multiple
    simultaneous winners (5/30 and 2/12 rounds, up to 4 at once) — so the test would have caught a flaw.
  - **Single-process parity**: both jobs, seeded for a due auto-archive and a due feeding reminder, run
    against HEAD loaded as a separate module → **every table row-by-row identical**, identical push
    payloads, identical dedup columns. The only delta was `archived_cycles.archived_at`, a SQL
    `DEFAULT CURRENT_TIMESTAMP` differing by 2 s between runs.
  - **Over time**: the owner won the lease on **every** tick (8 archive, 9 reminder) and did the work
    each time — no self-lockout. A non-owner skipped all work, wrote nothing, still slept its full
    interval (no hot spin), and printed its standby line once.
  - **The bug this prevents, reproduced**: 6 procs × 10 rounds → HEAD sent duplicate feeding pushes in
    1 round; 8 procs × 12 rounds → HEAD duplicated in **2 rounds (3 and 4 pushes)**. The fix sent
    exactly 1 in all 22 rounds. (Auto-archive turned out to be safer on HEAD than expected — its
    `archived=FALSE` re-query closes most of the window — so the reminder loop is where this really bit.)
  - **14 failure modes, none raised**: missing table, unreachable path, path-is-a-directory, live
    foreign lease, expired lease, garbage/empty/NULL `expires_at`, NULL `owner` (live and expired),
    write-locked DB (False after the 5.6 s busy timeout), schema drift. No connection leak over 3000
    calls including error paths. SQL injection via `job_name` (`x'); DROP TABLE users;--`) left `users`
    intact.
  - `init_db()` idempotent (3× on a real-DB copy and a fresh DB), existing data byte-identical.
  - Integrity: pre-#20 blobs `d0443d87…`/`893a1e8e…` confirmed; `diff -u` shows only #20; Issues
    #11/#18/#19 intact; `py_compile` passes; 3356 CRLF, 0 bare LF, no final newline; real DB sha256
    `8229690d…499d57` unchanged; HEAD `f67fb88`. (The fixer reported +71/4 hunks; the real diff is
    +75/5 — a cosmetic miscount.)
- **Existing tests**: nothing in `test_files/` references the schedulers, `scheduler_leases` or the
  dedup columns; `test_flows.py` uses the manual `/api/payments/archive` route, which is unchanged.
- **Notes, not defects**:
  - **Lexical time comparison verified** correct across midnight, month, year and hour rollovers. An
    Israel DST shift can steal ~1 h early (spring) or delay a takeover ~1 h (autumn) but **cannot**
    produce two owners — the same naive-local-time caveat as Issue #7.
  - `SCHEDULER_OWNER_ID` captures `os.getpid()` at import, so under `gunicorn --preload` every fork
    would inherit one ID. Harmless today because threads do not survive `fork()` (the loops simply
    wouldn't run in the children), but it would break if the loops were ever started from a post-fork
    hook.
- **Reviewer verdict**: **APPROVED** — "I reproduced the race it fixes (HEAD sent up to 4 duplicate
  feeding pushes in a round) and then failed to break the fix across 107 expiry-boundary rounds with up
  to 10 real processes firing at the instant the lease died — while a naive SELECT-then-UPDATE broke
  repeatedly under the identical harness."

---

### Newly discovered — not in ISSUES.md, not yet fixed

- **🔴 HIGH — takeover of unlinked accounts via Firebase's public sign-up (pre-existing at
  `bb0a195`).** Found by the Issue #9 adversarial reviewer; **not independently confirmed against
  the real Firebase project** (agents make no network calls by design). The Firebase Web API key is
  public by nature (it's in the client and in `firebase_config.py:25`), and with the Email/Password
  provider enabled, Firebase's REST `accounts:signUp` endpoint lets anyone create an account for
  **any** email without proving they own it. For a victim whose local row is unlinked
  (`firebase_uid=''` — no Firebase account exists for that email, which is exactly the Issue #9
  population), an attacker can: (1) call `signUp` with the victim's email and a password of their
  choosing; (2) log in normally. Firebase then succeeds, and both `login()` and `api_login()` look up
  the local user by `email=? OR firebase_uid=?` and **link** the attacker's new `fb_uid` onto the
  victim's row (`if fb_uid and not user['firebase_uid']: UPDATE`). Result: full account takeover, and
  the attacker's Firebase account becomes the victim's permanent login. Issue #9's fix does not create
  or widen this, and the optional `get_user_by_email` hardening above would not close it.
  **DECISION (2026-09-18, by the repo owner): close it with the Firebase console setting only — no
  code change.** The code guard (refusing to auto-link unless the local password also matches) was
  considered and **declined**, so `login()`/`api_login()` still link a successful Firebase login to a
  local row by email alone. That is acceptable **only while client-side sign-up stays disabled**.

  ### 👉 Action required by the owner, in the Firebase console
  1. Open the project → **Authentication** → **Settings** → **User actions**.
  2. Uncheck / disable **"Enable create (sign-up)"**.
  3. Verify afterwards that registration in the app still works: it runs server-side through the
     Admin SDK (`firebase_create_user`), which is unaffected by that setting.
  4. Sanity-check that a direct REST `accounts:signUp` call with the public Web API key is now
     rejected (e.g. returns `ADMIN_ONLY_OPERATION`).

  **If that setting is ever re-enabled, this exposure returns**, because nothing in the code prevents
  the email-only auto-link. If you later want defence in depth, the code guard above is the fix, and
  it pairs naturally with the Issue #9 follow-up (unlinked accounts still have no password-reset path).

- **The scheduler threads start before `init_db()` runs.** Confirmed during Issue #20:
  `_archive_thread.start()` is at `app.py:3244`, `_reminder_thread.start()` at `:3349`, but the
  module-level `init_db()` call is at `:3352` — *after* both. On a brand-new database the first
  reminder tick races table creation. Booted on an empty DB, the first tick acquired nothing, no crash,
  threads stayed alive, and it self-healed 60 s later. At HEAD the same tick printed
  `Feeding reminder error: no such table: family_settings`; with the lease it now fails silently, which
  is a small **observability** loss. Moving the `init_db()` call above the two `Thread.start()` lines
  would remove the window entirely — a one-line reorder, deliberately left out of #20's scope.

- **🟠 `firebase_update_password()` is called inside the `with get_db()` transaction** in both
  change-password routes (`app.py:866` web, `app.py:2445` api), right after the `UPDATE users`. It is
  an outbound Firebase HTTPS call, so it holds the SQLite **RESERVED write lock** for its whole
  duration — exactly the problem Issue #19 just fixed for mail, in a different subsystem. Confirmed
  by the #19 reviewer **on the fixed tree**: hanging that call gave a 3.33 s request and a concurrent
  `UPDATE` failing with `OperationalError: database is locked` after 2.29 s. Unlike mail, this one
  can't simply be moved to a thread — the route needs its result to decide whether the change
  succeeded — so the fix is to do the Firebase call **before** opening the DB block, or to close the
  transaction before calling out. Note `firebase_update_password` does at least use `requests` with a
  timeout, so it can't hang indefinitely.

- **`WTF_CSRF_SSL_STRICT` is Flask-WTF's default `True`, and there is no `ProxyFix`.** Found during
  Issue #18 and confirmed identical on HEAD, so it is pre-existing. Over HTTPS, `csrf.protect()`
  additionally requires a `Referer` matching the host: a request without one gets
  `400 "The referrer header is missing."`. **Not a risk today** — the app sets no `Referrer-Policy`
  header and no `<meta name="referrer">`, so under Chromium's default
  `strict-origin-when-cross-origin` both same-origin form posts and same-origin `fetch` send a
  full-URL `Referer`, including in the Android WebView. Two reasons to document it anyway: (a) adding a
  `no-referrer` policy or a stricter CSP later would **silently 400 every web write**; (b) with TLS
  terminated upstream by Traefik and no `ProxyFix`, `request.is_secure` is `False`, so the referrer
  check never fires in production at all, while the `Secure` cookie flag still applies because it is
  config-driven. Worth an explicit decision on `WTF_CSRF_SSL_STRICT` plus `ProxyFix` so the behavior is
  intentional rather than accidental.

- **`node_modules/` is tracked in git — 2,347 files.** `git ls-files --ignored
  --exclude-standard -c` reports 2,369 tracked-but-ignored files total: `node_modules/`
  (2,347), `.idea/` (7), `android/.idea/` (7), `__pycache__/` (4), and the 4 DB files.
  Same root cause as Issue #2 (the broken `.gitignore` let them be committed), but only
  the DB files are in scope for #2. Flagged for a separate decision — untracking 2,347
  vendored files is a large, noisy commit and should be a deliberate choice.

- **The app crashes on Windows whenever stdout is redirected or piped.** Discovered while
  verifying Issue #4 and independently reproduced by the reviewer. `firebase_config.py:66`
  prints an emoji (`✅`) at module import time; on this machine `sys.stdout.encoding` is
  `cp1255` (Python 3.9.7), so `python app.py > out.txt` or `python app.py | tee log` dies with
  `UnicodeEncodeError` before any route is served — stdout comes back empty. Confirmed
  **pre-existing**, not introduced by any fix: the pre-fix backup of `firebase_config.py`
  crashes identically at its line 43. Not a production risk (containers are Linux/UTF-8) and
  not a risk for Issue #4's guard (its refusal path is pure ASCII), but it breaks the ordinary
  Windows dev workflow of capturing server logs to a file. Fix would be a one-line
  `sys.stdout.reconfigure(encoding='utf-8')` guard or ASCII-only startup prints. **Note this
  affects the whole codebase's emoji-`print()` idiom, not just that one line.** Confirmed during
  Issue #8 that it now also includes the Issue #4 guard's own messages at `app.py:77` and `:81`
  (see the finding logged after Issue #8). A single `sys.stdout.reconfigure(encoding='utf-8',
  errors='replace')` at the very top of `app.py` — before `firebase_config` is imported — would
  cover every site at once.

- **Other GET-mutating routes** — `history_data` (`/api/history/data`) and
  `history_month_detail` (`/api/history/month`) run `UPDATE archived_cycles SET month=?` on
  GET-only routes. See the Issue #6 correction above. Confirmed low risk (idempotent, no
  request-controlled input reaches the write), but it contradicts ISSUES.md's claim that
  `/delete_payment/` was the only such route.

- **The CSRF fetch shim has no same-origin check.** Found while verifying Issue #6.
  `base.html:166-179` attaches the `X-CSRFToken` header to **every** POST/PUT/DELETE/PATCH
  request, including absolute cross-origin URLs — which would leak the user's CSRF token to a
  third-party host. **Not currently exploitable**: a grep of `templates/` finds zero
  absolute-URL `fetch(` calls, so no code path triggers it today. It is a latent footgun that
  becomes live the moment someone adds a `fetch('https://…')` to a template. Fix is a one-line
  guard (only attach when the URL is relative or same-origin). Pre-existing, not introduced by
  any fix in this run.

- **`/api/auth/login` returns 500 on non-string JSON fields.** Found while reviewing Issue #7.
  Sending `username` or `email` as a number, list, or `null` crashes on the `.strip()` calls at
  the top of `api_login()` with an unhandled exception. Pre-existing (those lines were not
  touched by the fix) and not a security bypass — a crafted request just gets a 500 instead of a
  400. Same class of bug as Issue #14 (unsafe JSON body handling); worth folding into that fix.

---

# ▶️ RUN STATUS — resume here

Keep this section current: it is the single source of truth for where the run stands.

## Progress: 20 of 31 issues addressed — all 20 fixed & approved

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `.gitignore` UTF-16 encoding | Critical | ✅ Fixed & approved — committed `bb0a195` |
| 2 | DB files tracked in git | Critical | ✅ Fixed & approved — committed `bb0a195` |
| 3 | `serviceAccountKey.json` exposure | Critical | ✅ Fixed & approved — committed `bb0a195` |
| 4 | Weak production secrets | Critical | ✅ Fixed & approved — committed `bb0a195` |
| 5 | Stored XSS (16 sinks) | Critical | ✅ Fixed & approved — committed `bb0a195` |
| 6 | CSRF via `GET /delete_payment` | High | ✅ Fixed & approved — committed `bb0a195` |
| 7 | No rate limiting on local login fallback | High | ✅ Fixed & approved — **uncommitted** |
| 8 | `firebase-service-account.json` missing locally | Medium | ✅ Fixed & approved — **uncommitted** |
| 9 | Users with no Firebase account can never log in | Medium | ✅ Fixed & approved — **uncommitted** |
| 10 | Dead local password-reset flow | Medium | ✅ Fixed & approved (removed) — **uncommitted** |
| 11 | No way to delete a family / transfer ownership | Medium | ✅ Fixed & approved (sole-member delete) — **uncommitted** |
| 12 | `/api/recurring` POST/PUT skip input validation | Medium | ✅ Fixed & approved (2nd review) — **uncommitted** |
| 13 | `add_feeding` can 500 after the DB write committed | Medium | ✅ Fixed & approved (re-approved after follow-up) — **uncommitted** |
| 14 | Inconsistent JSON body parsing between API layers | Medium | ✅ Fixed & approved — **uncommitted** |
| 15 | Daily budget alert has no dedup | Medium | ✅ Fixed & approved — **uncommitted** |
| 16 | FCM worker never prunes dead tokens | Medium | ✅ Fixed & approved — **uncommitted** |
| 17 | `_fcm_credentials` cache mutated without a lock | Medium | ✅ Fixed & approved |
| 18 | Session/CSRF cookies lack `Secure`/`SameSite` | Medium | ✅ Fixed & approved — **uncommitted** |
| 19 | `mail.send()` has no SMTP timeout | Medium | ✅ Fixed & approved |
| 20 | Scheduler threads unsafe under multiple workers | Medium | ✅ Fixed & approved |
| 21 | Missing security regression tests (JWT/CSRF) | Medium | ⬜ **next** |
| 22–31 | Remaining | Medium→Low | ⬜ Not started |

Commit history for this run (all on `android_firebase_integration`, **nothing pushed**):
1. `bb0a195` — Issues #1-6.
2. `f67fb88` — Issues #7-#10, #12-#17.
3. **"Fix 4 more issues (#11, #18, #19, #20)"** — the commit made at this pause.
| NEW | 🔴 Takeover of unlinked accounts via Firebase public sign-up | High | ⚠️ **Needs a human decision** — see "Newly discovered" |

**All Critical and High issues from ISSUES.md are cleared.** 1 rejection across 12 issues (Issue
#12, first review — fixed and approved on the second). One
**new** High was found during review of #9 and is waiting on a decision.

## How this run works (for whoever picks it up)

Each issue gets two agents with fresh context, one issue at a time:
1. A **fixer** implements only that issue, minimally, and reports what it changed.
2. An independent **reviewer** verifies the diff, runs the relevant tests, and returns
   `APPROVED` or `REJECTED: <reasons>`. No issue is logged as Fixed until it's approved.

Constraints that proved important and should be carried forward:
- Reviewers get an explicit **"do not reject for X"** list of out-of-scope items, so they don't
  bounce a fix for something deliberately deferred.
- **Database rule (tightened after the Issue #7 incident):**
  - Never open any SQLite connection to a DB file in the repo root — **not even read-only**, since
    a read-only connection to a WAL database can still touch `-shm`, and closing a connection can
    checkpoint the WAL into the main file.
  - Get a test DB by copying at the filesystem level only (`cp`, `Copy-Item`, `shutil.copy2`)
    into the scratchpad, then connect to the copy.
  - Set `DATABASE_PATH` to that copy **before** importing `app` — `init_db()` runs at import.
  - Never run scripts in `test_files/`: they connect to `finance_tracker.db` by relative path.
  - Record the real DB's sha256 / size / mtime (file hashing only) at start and end; they must
    match.
- Use Flask's in-process test client (or a spare port, never 5000), with `APP_ENV` unset and
  `PYTHONIOENCODING=utf-8` (importing the app prints emoji, which crashes under cp1255 when stdout
  is piped).
- No agent may run `git add`/`commit`/`rm`/`push` or rewrite history.
- Fixers are told `app.py` holds the user's own uncommitted work, and reviewers verify its diff
  is undisturbed. This caught nothing so far — which is the point.

This process earned its keep: reviewers corrected the **fixers** twice and corrected
**ISSUES.md itself three times** (see corrections logged under Issues #4, #5, and #6). It also
surfaced one process failure — the Issue #7 fixer opened the real DB — which is why the database
rule above is now stricter.

## Working-tree state

Branch `android_firebase_integration`, **three unpushed commits** on top of `e8f8310` (see the list
above). At this pause the working tree is clean apart from the pre-existing items below. Check with
`git log --oneline -4` and `git status --porcelain` before resuming.

Pre-existing and deliberately left out of commits — the user's own work or derived artifacts:
` M capacitor.config.json` (LAN-IP → production-domain switch), ` M android/.idea/misc.xml` (IDE
metadata), ` M __pycache__/*.pyc` (bytecode).

Real DB: `finance_tracker.db` sha256 `8229690d46a62156…499d57`, 139,264 bytes, mtime
2026-09-17 18:34:00, **no `-wal`/`-shm` files**. Any later agent should find exactly this at
start and end (unless the user has run the app in between, which legitimately changes it).

## ⚠️ Queued for the human — none of these can be automated

1. **Rotate `SECRET_KEY`, `JWT_SECRET`, `FINANCE_APP_SECRET_KEY`** into the server `.env` and
   redeploy. Rotating `JWT_SECRET` **logs out every web session and mobile JWT.**
2. **Rotate the Firebase Admin SDK key** — it was exposed in git history through two scrubs, so
   any clone taken before them still has it.
3. **Decide on the PII history scrub** — untracking only stops future commits. Note
   `HEAD:finance_tracker.db-wal` is a **436,752-byte** blob, so most committed family/financial
   data lives in the WAL, not the `.db`.
4. **Legacy `finance-app` service** still ships `DEFAULT_USER=admin` / `DEFAULT_PASS=admin` on a
   routable hostname — rotate or decommission.
5. **Before the next `docker compose up`**, the server `.env` must define all four secrets —
   `${VAR:?}` now fails validation for the whole file, which would also block `traefik` and
   `n8n` from starting. Running containers are unaffected until re-up.
6. **Decide on `node_modules/`** (2,347 tracked files) — untracking is a large, noisy commit.

## ⏸️ Paused after Issue #20

**No decisions are outstanding.** Both earlier questions were answered on 2026-09-18: the Firebase
takeover is to be closed by the **console setting only** (no code guard — see the action steps under
"Newly discovered"), and Issue #11 was built as **sole-member delete only**.

### 👉 The one manual task still open
Firebase console → **Authentication → Settings → User actions** → disable **"Enable create
(sign-up)"**. Until that is done, the unlinked-account takeover is still open, and because the code
guard was declined, that setting is the only thing closing it.

## Next step

**Issue #21** — missing security regression tests: nothing in the suite forges a JWT with a wrong
secret and asserts 401, and nothing asserts that CSRF actually blocks a token-less web POST. Notes
before starting:
- These are **new tests**, not app changes — the first issue of the run in that category. The suites
  are standalone `requests` scripts against a live server on `http://127.0.0.1:5000` that talk to the
  **real** `finance_tracker.db` by relative path. A fixer must not run them; decide how the new tests
  get executed (and by whom) before writing them.
- Useful material already exists in the scratchpad harnesses from #6, #7 and #18, which did exactly
  these checks in-process against DB copies.
- Consider whether these belong as in-process tests (safe, no live server, no real DB) rather than
  appended to the existing live-server scripts.

**High-value follow-ups found during review** (not in ISSUES.md; each is written up under "Newly
discovered"):
- `update_payment` with `amount: "abc"` returns 500 **after committing** the bad value — the Issue #13
  bug, on payments.
- `firebase_update_password()` runs inside the DB transaction, holding the write lock during an
  outbound HTTPS call (the Issue #19 bug, different subsystem).
- The scheduler threads start **before** `init_db()` — a one-line reorder fixes it.
- `update_feeding` is unvalidated; the baby tracker's `submitAdd` ignores the HTTP response, so
  rejected saves vanish silently.
- `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at the top of `app.py` would fix every
  cp1255 emoji-print crash on Windows at once.

Keep verifying ISSUES.md claims before fixing — it has been wrong or understated in Issues #4, #5,
#6, #8, #9, #12, #14, #17, #19 and #20.

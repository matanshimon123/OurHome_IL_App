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

---

### Newly discovered — not in ISSUES.md, not yet fixed

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
  affects the whole codebase's emoji-`print()` idiom, not just that one line.**

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

---

# ⏸️ RUN PAUSED — resume here

Stopped at a clean boundary after Issue #6. **Nothing has been committed.** All work sits in the
working tree for review. Every issue attempted so far is fixed *and* reviewer-approved — there
is no half-finished work and no outstanding verification debt.

## Progress: 6 of 31 issues, all approved

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `.gitignore` UTF-16 encoding | Critical | ✅ Fixed & approved |
| 2 | DB files tracked in git | Critical | ✅ Fixed & approved |
| 3 | `serviceAccountKey.json` exposure | Critical | ✅ Fixed & approved |
| 4 | Weak production secrets | Critical | ✅ Fixed & approved |
| 5 | Stored XSS (16 sinks) | Critical | ✅ Fixed & approved |
| 6 | CSRF via `GET /delete_payment` | High | ✅ Fixed & approved |
| 7 | No rate limiting on local login fallback | High | ⬜ **next** |
| 8–31 | Remaining | Medium→Low | ⬜ Not started |

**All 5 Critical issues and the first High are cleared.** 0 rejections across 6 reviews.

## How this run works (for whoever picks it up)

Each issue gets two agents with fresh context, one issue at a time:
1. A **fixer** implements only that issue, minimally, and reports what it changed.
2. An independent **reviewer** verifies the diff, runs the relevant tests, and returns
   `APPROVED` or `REJECTED: <reasons>`. No issue is logged as Fixed until it's approved.

Constraints that proved important and should be carried forward:
- Reviewers get an explicit **"do not reject for X"** list of out-of-scope items, so they don't
  bounce a fix for something deliberately deferred.
- Any agent that runs the app must point `DATABASE_PATH` at a **temp copy** of the database and
  use a spare port. Never run against the real `finance_tracker.db`.
- No agent may run `git add`/`commit`/`rm`/`push` or rewrite history.
- Fixers are told `app.py` holds the user's own uncommitted work, and reviewers verify its diff
  is undisturbed. This caught nothing so far — which is the point.

This process earned its keep: reviewers corrected the **fixers** twice and corrected
**ISSUES.md itself three times** (see corrections logged under Issues #4, #5, and #6).

## Exact working-tree state at pause

HEAD is unchanged at `e8f8310` on branch `android_firebase_integration`. The reflog has no new
entries — nothing was committed, reset, or rewritten.

```
 M .gitignore                          Issue #1 — UTF-16LE → UTF-8, no BOM
 M app.py                     130/48   user's own 89/47 + #4 guard (+37) + #6 (+4/-1)
 M firebase_config.py          20/0    Issue #3 — in-repo credential warning
 M templates/baby_tracker.html 21/7    Issue #5 — XSS
 M templates/dashboard.html    25/7    Issue #5 — XSS, + Issue #6 fetch POST
 M templates/history.html       1/1    Issue #5 — esc() hardening
 M templates/home.html          4/1    Issue #5 — XSS
 M templates/settings.html     24/4    Issue #5 — XSS
 M templates/shopping_list.html 32/12  Issue #5 — XSS
 D  finance_tracker.db                 Issue #2 — staged deletion (file intact on disk)
 D  finance_tracker.db-shm             Issue #2 — staged deletion (file intact on disk)
 D  finance_tracker.db-wal             Issue #2 — staged deletion (file intact on disk)
 D  test_files/finance_tracker.db      Issue #2 — staged deletion (0-byte placeholder)
 ?? .env.example                       Issue #3 — new, placeholders only, safe to commit
 ?? docker-compose-new.yml             Issue #4 — de-secreted, now safe to commit
```

Pre-existing and unrelated to this run: ` M android/.idea/misc.xml` (IDE metadata),
` M capacitor.config.json` (the user's own LAN-IP → production-domain switch),
` M __pycache__/*.pyc` (bytecode; `firebase_config.cpython-39.pyc` was regenerated by
verification test imports — a derived artifact, safe to discard).

**Safety net**: a snapshot of every dirty file as it stood *before* this run is in the session
scratchpad at `backup_pre_fixes/` (19 files). Note the session scratchpad is temporary — if
these changes matter, commit or copy them somewhere durable.

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

## Suggested first step on resume

**Start directly on Issue #7** (no rate limiting on the local password fallback,
`app.py` `api_login()` ~2061-2081 / `api_register()` ~2108-2144). There is no leftover work from
Issues #1-6 — all six are approved and closed.

Before resuming, two things are worth doing first:

1. **Commit or branch the current work.** Six issues' worth of changes are uncommitted, and the
   only pre-run backup lives in a temporary session scratchpad. A `git switch -c security-fixes`
   plus a commit would make this durable. Review the staged DB deletions before committing —
   they're intentional, but they're the kind of thing worth looking at twice.
2. **Read the "Queued for the human" list below.** Two of those items (secret rotation, Firebase
   key rotation) are the actual security remediation; the code fixes only stop the bleeding.

### Note on Issue #7 specifically

Issue #7 depends on a factual claim worth re-verifying before fixing: that
`/api/auth/register` accepts an **empty** email (`if email and not re.match(...)` skips
validation when `email` is falsy), creating accounts that then authenticate through the
unthrottled local `check_password_hash` branch in `/api/auth/login`. Confirm that path is real
and reachable before designing a fix around it — given ISSUES.md has already been wrong three
times, verify rather than trust it.

Also note the likely fix (Flask-Limiter) **adds a dependency**, which is a step up from every
fix so far — all six to date were dependency-free. Worth a deliberate decision between adding
the library versus a small hand-rolled attempt counter, and worth checking whether rate-limit
state should live in SQLite (survives restarts, works across gunicorn workers) rather than in
process memory, given the multi-worker concern already noted in Issue #20.

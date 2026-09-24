# Design refresh: Concept A ("Pop") across the whole app

Branch: `design-refresh` (no new branch, nothing committed). Reference material in `design-concepts/` was only read, never modified.

## 1. What was reverted first

The earlier redesign attempt was discarded completely, back to the last real commit (`90cf8dd`).

- **Restored from git:** `CLAUDE.md`, `MainActivity.java`, `app.py`, `static/css/style.css`, `static/manifest.json`, `static/sw.js`, `www/index.html`, and all 12 templates (`admin`, `baby_tracker`, `base`, `dashboard`, `family_setup`, `forgot_password`, `history`, `home`, `login`, `register`, `settings`, `shopping_list`).
- **Deleted (untracked leftovers of that attempt):** `DECISIONS.md`, `static/js/`, `templates/_icons.html`, `templates/error.html`.
- The working tree was clean (apart from the untouched `design-concepts/`) before any new work started.

Everything below was then built fresh on top of `90cf8dd`.

## 2. The design system

One stylesheet and one small helper library, extending `design-concepts/concept-a/concept.css` and `concept.js`. No framework, no Bootstrap, no Font Awesome, no Chart.js.

| File | What it holds |
|---|---|
| `static/css/style.css` | Concept A tokens (cream, ink, coral, sun, mint, sky, grape, peach), Rubik + Varela Round, sticker cards (ink outline + offset shadow), blob hero headers, chips and chip-buttons, buttons, avatars, stats, forms, keypad, segmented control, switch rows, lists, bottom sheets, confirm dialog, toast, the nav pill with the bouncing blob, the labelled radial FAB, progress ring, checkable pills, spring/pop motion. |
| `static/js/pop.js` | Extends `concept.js`: `Pop.api` (fetch + JSON), `toast`, `confetti`, `squish`, `openSheet/closeSheet` (scroll lock, Escape, backdrop), `confirm` (promise dialog, replaces `window.confirm`), `copyText`, `share` (Capacitor Share → Web Share → copy), count-up, money/date helpers, nav blob and FAB behaviour, password show/hide. |
| `static/js/expense-sheet.js` + `templates/_expense_sheet.html` | The shared add/edit expense sheet (Concept A keypad), used by Home and Expenses. |

Conventions: page-specific styles live in the page's `{% block head %}`; every action has words, not just an icon; forms and edits open in bottom sheets; destructive actions go through `Pop.confirm`.

## 3. Screen by screen

| Screen | Concept A patterns | Real logic kept / added |
|---|---|---|
| Base layout | Nav pill with blob (5 labelled tabs), toast, fonts, safe areas | CSRF fetch wrapper, flash → toast, service worker, Android page-ready, push registration (unchanged) |
| Error page (new) | Peach hero, message sticker, big buttons | 404/403/405/400/500; web gets the page, `/api/` keeps JSON |
| Login / Register / Forgot password | Sun/mint auth hero, logo sticker, chunky fields, show-password | Same forms and routes; register shows a password-mismatch warning before sending |
| Family setup | Join/create stickers, invite "ticket", avatar stack, confetti on success | Same join/create routes; share + copy code |
| Home | Sun hero with greeting and avatar stack, pulse row, ink forecast sticker with sparkline, jar, week coins, shopping ring + pills, baby timer + day band, radial FAB | All numbers from `/api/home-summary`; check items from home; add expense / item; forecast explained in a sheet |
| Expenses | Sky hero with count-up total, bubble split, sticker list grouped by day, keypad sheet, FAB | Recurring payments (log one / log all / edit / delete), bill detective, category filter, archive, Excel, first-time setup dialog. Editing a payment: amount, category, description (above the keypad) and **date** (limited to the current cycle and today); save and delete side by side |
| Cycle analysis (new) | Sky hero, sticker charts, sheets | Cycle race vs. last cycle with projection and budget, calendar heatmap, last 6 cycles vs. average, per-category change |
| History | Grape hero, year switcher, highlight stickers, chunky month bars | Year totals, most/least expensive cycle, top category, trend, month sheet sorted by date or category |
| Shopping list | Peach hero with progress ring, checkable pills, sticker add card | Add (with quantity + department), check/uncheck, edit (name, qty, department, photo, favourite), delete, clear cart, favourites (add one / add all / new / edit / remove), share the list |
| Baby tracker | Grape hero with live timer card, quick-log grid, 24h radial clock, pillow stack, timeline | All six event types with amounts/side/type/medication, edit/delete, week view with day details, feeding reminder switch |
| Settings | Mint hero with profile; a short **hub** with one row per category, each showing a live summary, and one screen per category (`#family`, `#notifications`, `#finance`, `#account`) with a labelled back button; the phone's back button, reload and direct links work | Family: invite share/copy, members (remove / leave / delete family). Notifications: my notifications (a switch per kind of push, per person) + the family feeding reminder. Finance: budget + cycle day (admin only, with confirm) + expense categories. Account and data: display name, password, Excel export, archive. Hub: admin link, logout |
| Admin | Ink hero, KPI stickers, HTML sticker bars (Chart.js removed) | Same server data as before |
| Offline | Sun hero, sad-cloud sticker | New service-worker offline page; restyled Android fallback page whose retry now really reconnects |

## 4. Borrowed from Concepts B and C

Every borrowed idea is re-skinned in Concept A's style.

- **Cycle race (from B), in cycle analysis.** A day-by-day running total against last cycle is the clearest answer to "are we spending more than last month?". A big slider sits next to the scrubbable chart, so it works without fine finger control.
- **Calendar heatmap (from C), in cycle analysis.** It shows *which days* were expensive, which a total can't. Each cell is a ≥44px button with the day and amount written in it.
- **Feeding intervals (from C), in the baby tracker.** Gaps between feeds matter more to parents than a list of times. Long gaps are coloured and also said in words.
- **Keyword auto-categorising (from C), in the shopping list.** C used it for expenses; applied to shopping it guesses the department as you type ("חלב" → חלבי). It always says it guessed and never overrides a department you picked. Hebrew final letters are folded so "מלפפון" also matches "מלפפונים".
- **Native share (from the concepts' feature notes), on shopping and invites.** Families send lists and codes over WhatsApp anyway.
- **Settings as a hub with one screen per category**, rather than accordions (which grow back into a long page and jump when opened) or popups (long content scrolling inside a popup, and the phone's back button doesn't close them). This is the pattern Android and iPhone settings use.
- **Charts run right to left** (day 1 / oldest on the right), consistent with the calendar and the week coins.

## 5. Accessibility guardrail: how Concept A was adapted

- **Readable colour contrast.** Text on bright fills is ink. White text only sits on the deep shades (`--sky-deep`, `--grape-deep`, ink). Coloured text uses the darker `--mint-ink` / `--coral-ink`, and muted text is `--ink-2`. Every screen passed an automated WCAG contrast audit.
- **Text size.** Nothing below 13px, body 16px.
- **Tap targets.** Every tap target is at least 44×44.
- **Words on every button.** Quantity steppers say "עוד/פחות", switches are whole rows with their state in words ("פעיל/כבוי"), and chart bars have spoken labels.
- **Clear back-navigation.** Every sub-screen (analysis, history, admin, forgot password) has a labelled "חזרה ל…" button, and the nav always marks where you are.
- **Direction.** RTL throughout.
- **Reduced motion** turns off confetti.

## 6. Backend changes (every one)

All changes are additive. No existing response key was removed or renamed, no auth decorator or family filter changed, and every new query is scoped by `family_id` and behind `@require_auth`.

| # | Where | Change | Why |
|---|---|---|---|
| 1 | `app.py` error handlers | `HTTPException` / `Exception` handlers: web requests get `templates/error.html`, `/api/` requests get `{"error", "code": "HTTP_<n>"}` JSON. Tracebacks still go to the log. | Branded error states without breaking API clients |
| 2 | `init_db()` ALTER list | `payments.added_by`, `shopping_items.added_by` (nullable INTEGER, idempotent) | "Who added it" on rows |
| 3 | `add_payment`, `add_payment_api`, `add_recurring_to_month`, `add_all_recurring`, `add_shopping_item`, `add_favorites` | Store `added_by` (current user) | Same |
| 4 | `GET /api/payments`, `GET /api/shopping-items` | Added `added_by_name` (LEFT JOIN users); payments also get `time` | Same, plus time on rows |
| 5 | New helpers | `_cycle_progress`, `_prev_cycle_month`, `_finance_extras` (projection = spent + pending recurring + variable pace × days left; fixed/variable split; same-point-last-cycle; running totals; Sun–Sat week), `_seconds_since_last_feed`, `_feeding_rhythm` (median gap of recent feeds), `_cycle_start_for` | Shared by home, expenses, analysis, baby |
| 6 | `/home` | Passes `family_name`, `members` | Greeting and avatar stack |
| 7 | `GET /api/home-summary` | Adds `finance.*` extras (above), `shopping.items`, `hour`, `baby.sleep_mins / last_feed_secs / typical_gap_min / next_expected / recent` | Home cards |
| 8 | `/dashboard` | Passes `fin_extra` | Comparison chip and projection |
| 9 | New `/finance/analysis` + `GET /api/finance/analysis` | Read-only aggregation: current/previous cycle (daily + cumulative), last 12 cycles, average, per-category now / same point last cycle / 6-cycle average | The requested analysis view |
| 10 | New `GET /api/recurring/suggestions` | Read-only: charges repeating with ≈ the same amount in ≥3 of the last 6 cycles that aren't recurring yet | Bill detective on Expenses |
| 11 | `/history` | Passes `current_month` | Marks the running cycle |
| 12 | `GET /api/feedings/data` | `stats` adds `last_feed_secs`, `typical_gap_min`, `next_expected` | Baby timer and rhythm |
| 13 | New table `notification_prefs` + `GET/PUT /api/notifications/prefs` | One row per person: `expenses`, `budget`, `cycle`, `shopping`, `baby`, `feeding_reminder`, `family` (missing row = everything on). PUT changes only the keys it sends, and only true/false for known keys. If a `notification_prefs` table already exists with an older column layout (an earlier prototype left one in a developer database), the new columns are added by the `init_db()` upgrade list. If the preferences can't be read, `send_push_to_family` delivers instead of dropping the push. | Each person chooses which notifications reach their phone |
| 14 | `send_push_to_family(..., module=None)` + `_push_recipient_tokens` | Optional `module`: people who turned that kind off are skipped. All 19 call sites are tagged with their kind. Without `module`, behaviour is exactly as before. The feeding-reminder hours stay a family setting. | Same |
| 15 | `PUT /api/payments/<id>` + `_cycle_month_for_date` | Accepts an optional `date` (`YYYY-MM-DD`). Before anything is written it must be a real date, not in the future, for a payment that isn't archived, and not in an archived cycle; otherwise 400 and nothing changes. Keeps the time of day; recomputes `month`/`year` with the family's cycle day. Response adds `month`. | Changing an expense's date |

## 7. App shell and PWA (non-backend)

- **`static/sw.js`.**
  - It no longer precaches Bootstrap, Font Awesome or Chart.js.
  - It precaches the design system and a new `static/offline.html`.
  - Cache is `ourhome-pop-1`, and old caches are deleted.
  - API calls are never cached.
  - Pages with nothing cached get the offline page.
- **`www/index.html` (Android fallback page).** Restyled in Pop and self-contained. Its retry button now really reloads the app; before, it only restarted a timer. `SERVER` must stay in sync with `capacitor.config.json`.
- **`MainActivity.java`.** Splash colours changed from blue to ink/grape, with more readable status text and a sun-coloured retry button. Colours only; no logic changed.
- **`static/manifest.json`.** `theme_color` is `#FFC531` and `background_color` is `#FFF6E9`.
- **`base.html`.** On Android, the status-bar icons switch light/dark per screen, so they stay readable over both dark and light heroes. This uses the installed `@capacitor/status-bar` and does nothing in a browser. **Not verified on a device.**
- **`CLAUDE.md`.** Documents the new files (`analysis.html`, `error.html`, `_expense_sheet.html`, `static/js/`, `offline.html`, this file), the UI conventions, and the `categories.name` known issue.
- **Removed from `base.html`:** a debug script that POSTed device details to `/api/debug-cap` on every page load. Push registration, the CSRF fetch wrapper and the Android page-ready signal are unchanged.

## 8. Verification

Each screen was checked in a fresh headless Chrome at 390×844 against a scratch copy of the app (port 5001, scratch database), never the real `finance_tracker.db` or port 5000. Every check covered:

- an automated audit: WCAG contrast on every text node, text size ≥13px, tap targets ≥44px, a visible label on every button/link, no horizontal overflow, no console or network errors
- end-to-end flows asserted against the database
- visual review of screenshots

The per-screen log is at the end of this file.

## 8b. No silent failures when saving (after the six-week incident)

Expenses were reported as added in the UI but never reached the server, for about six weeks (last real payment 5 Aug 2026). The cause was in the pre-refresh client: `dashboard.html` did `await fetch('/api/payments/add', …)` and then cleared the form and showed "תשלום נוסף!" **without ever looking at the response**. Whatever the server answered — 401, 500, anything — the user was told it was saved.

The API itself is fine: an expired session returns a clean `401 {"code":"AUTH_REQUIRED"}` as JSON, never an HTML redirect, on both the old and the new code.

What changed:

- **`Pop.api` (`static/js/pop.js`) decides what counts as a save.** A 200 whose body is not JSON (a login page, a proxy error page) is now a **failure**, not a success — that is the trap this class of bug falls into. 401/403 gets its own `reason` so the screen can say "log in again", and every result carries `reason` and `retriable`. `Pop.netMsg(r)` turns a result into the sentence the user reads.
- **GET is retried automatically** (twice, backing off). **Writes are never retried on their own**: `/api/payments/add` is not idempotent, and a blind retry can record the expense twice. The user is offered a retry button instead, and the retry test asserts exactly one row is added.
- **The expense sheet shows a failure state** (`.exp-error` + "נסו שוב", or "התחברות מחדש" on 401). The sheet stays open with the amount, category and description intact, so the retry re-sends what was typed. Success — toast, confetti, closing the sheet, refreshing the list — only ever happens after the server confirms.
- **The one remaining unchecked write was fixed**: "register all recurring payments" (`dashboard.html`) ignored every result and always claimed success; it now counts what got through and names what didn't.
- **Push-token registration** (`base.html`) now checks the response instead of discarding it.
- **Service worker: not involved, and proven not to be.** It already returns early for non-GET and for `/api/`, so it can never answer a save. The test asserts the worker controls the page, that a save still lands in the database, and that no `/api/` response is in any cache.
- **Asset version bumped `pop1` → `pop2`** (and the cache to `ourhome-pop-2`) so phones actually pick up the fixed JavaScript instead of a cached copy.
- **`float(f['amount'] or 0)` in `feedings_data`** (`app.py`): one row with a NULL amount used to 500 the whole baby tracker. The app can't create such a row (`add_feeding` rejects it), so this is defence only.

Verified in a real browser (`vs_nosilent.py`, 48 checks): for a 200-that-is-HTML, a 500, no connection at all, and an expired session — nothing is ever reported as saved, a written reason appears, the sheet stays open with the typed values, and the database row count is unchanged. Then retry saves exactly once.

**Still unexplained: why the server refused those writes for six weeks.** The client change makes the next failure visible immediately; it does not tell us what went wrong in August. Worth checking on the server: the Flask/Gunicorn log around 5 Aug for 4xx/5xx on `/api/payments/add`, `df -h` (a full disk makes SQLite fail writes while reads keep working), and that the database file and its directory are writable by the app user.

## 8c. Expenses screen density pass

Measured on the same data, deployed build (`80ca438`) vs now, at 390×844:

| | deployed | now |
|---|---|---|
| category breakdown section | 465px | **181px** (−61%) |
| tallest transaction row | 74px | 59px (−20%) |
| tallest recurring row | 74px | 58px (−22%) |
| whole page | 3196px | 2704px (−15%) |

**Bubble pack → one proportional bar + a ranked scrolling legend.** The bubbles cost ~230px of SVG and then repeated every percentage in a legend underneath. The replacement is a single 30px stacked bar (the shape of the cycle at a glance) above one horizontally scrolling row of ranked chips, each carrying `₪amount · share%`. Every number now appears exactly once, in the chips; the bar is purely proportional.

Why this and not a donut or a ranked list with inline bars: any per-category *control* has to be ≥44px tall, so six always-visible rows cost ≥264px however they are drawn — a ranked list could not beat the bubbles by much. Putting the categories on one `.chip-scroll` line (the pattern the expense sheet already uses for its category picker) keeps full-size tap targets while costing a single row. The bar segments are `aria-hidden` and non-interactive on purpose: a 2% sliver would otherwise be a 6px tap target and fail the accessibility audit. The bar carries an `aria-label` spelling out the whole breakdown for screen readers.

**Dense rows** are a `.item.dense` modifier on the existing row component: 34px icon (was 44), 15px title, 13px subtitle, 16px amount, 8px padding. Nothing was removed — payer avatar, amount, title, category dot and name, and time all remain. Compact is not cramped: rows stay ≥44px tall and no text is under 13px, both asserted.

**FAB**: holds all three actions — expense, recurring, cycle analysis — and is labelled **פעולות** rather than הוספה, because it no longer only creates things. The analysis card was removed from the top of the screen, since the FAB now covers it. (An earlier pass had done the opposite; the owner preferred the entry point in the menu.) `Pop` used to hardcode `'הוספה'` when closing the menu, which silently overwrote whatever a page put in `.lbl`; it now keeps each page's own word, so Home still reads הוספה where the menu really is only creation.

**The recurring block earns its place.** It used to be a full card at the top of the screen at all times, including when there was nothing to do. Now it has three states: nothing set up → a single line offering to set one up; something due (a new cycle, or a charge not yet logged) → the full card, which is exactly when the reminder is useful; everything logged → a single line saying so, which reopens the list on tap for editing. A full card is ~260px; the collapsed line is 82px.

**Recurring and the cycle start — verified, not assumed.** `add_recurring_to_month` files the payment under `month = get_cycle_month(fid)`, which is the cycle, not the calendar month of "today". Tested with the cycle deliberately started six days before today (cycle day 15, today the 21st): the row lands in cycle `2026-09`, the cycle total moves by exactly the amount, the home summary and the expense list agree, and `_cycle_month_for_date` maps today to the same cycle. So a recurring charge registered mid-cycle counts for the whole cycle. No backend change was needed; the FAB reuses this same route.

**Category suggestion — genuinely shared.** The matching engine moved into `Pop.foldHe/guessRules/guessFrom` in `pop.js`, and the shopping list now calls it instead of its own copy. Only the vocabulary differs, because the two taxonomies are unrelated: shopping guesses supermarket *departments* (חלבי, קפואים…), expenses guess *expense categories* (רכב, משק בית…). The Hebrew final-letter folding (מלפפון → מלפפונים) is shared, which is the part that was actually hard to get right. The guess only pre-selects a chip, is labelled "נבחרה לפי התיאור, אפשר לשנות", stops the moment the user taps any chip, and never runs when editing an existing payment.

**Double-tap zoom, site-wide.** `touch-action: manipulation` on `html, body` and on interactive elements in `style.css` — this is the fix that actually works on iOS Safari, which has ignored `user-scalable=no` since iOS 10. The viewport tag also gained `maximum-scale=1, minimum-scale=1, user-scalable=no` in `base.html` (every page), `static/offline.html` and `www/index.html`. Note the trade-off: `user-scalable=no` also blocks pinch-zoom, which works against WCAG 1.4.4; `touch-action` alone would have stopped double-tap zoom while leaving pinch available. It is set as asked — say the word and I will drop `user-scalable=no` and keep the `touch-action` fix. Verified on `/dashboard`, `/home`, `/shopping-list`, `/settings` and `/login`.

## 8d. Bottom bar on iOS, backdated expenses, photos on new shopping items

**The bottom nav slid up into the page while scrolling in iPhone Safari.** `html, body { overflow-x: hidden }` turns the page into a scroll container, and iOS then drags `position: fixed` children along with the scroll instead of pinning them. `overflow-x: clip` crops identically without creating that container, so it is now applied through `@supports (overflow:clip)` with the old `hidden` left as the fallback. The bar also gets `transform: translateZ(0)` so iOS composites it on its own layer rather than repainting it a frame late. **This cannot be verified here** — headless Chrome does not reproduce the iOS behaviour. What is verified is that the bar stays pinned while scrolling, sits at the bottom of the viewport, and that no sideways scrolling appeared when `overflow-x` changed.

**A new expense can be backdated.** `POST /api/payments/add` accepted no date at all and always stamped `now`; it now takes an optional `date`. The rules are the same ones the edit route already enforced, so they moved into one `_validate_payment_date()` used by both: a real date, not in the future, and not inside an archived cycle. In the sheet the date hides behind a 📅 button next to the description that reads "היום" until another day is picked, so the common case stays a two-tap flow. The date is only sent when it is not today. Verified end to end: an expense dated two days back is stored with that date and files into the cycle that date belongs to, while an ordinary add is still stamped today.

**A photo can go on a shopping item as it is created**, not only through a later edit — `POST /api/shopping-items` ignored `image` and now accepts it (rejecting anything that is not a `data:image/` string). Camera and gallery are **separate inputs**, because one `accept="image/*"` input alone opens the gallery in the Android WebView; the camera one carries `capture="environment"`. Both the add form and the edit sheet offer the pair, and both run the same 800px JPEG resize. **The camera needs a device check**: the Android manifest declares no `CAMERA` permission, which is the correct setup for `<input capture>` (declaring it without it being granted blocks the capture intent), but that cannot be confirmed from here.

One audit rule was narrowed: a button whose entire content is a real photograph and which carries an `aria-label` is no longer counted as an unlabelled icon. The rule exists to catch emoji-only buttons, and those are still flagged. This surfaced because photos on new items make the list thumbnails far more common.

## 9. Follow-ups (flagged, not implemented)

- **Partner spending race and settle-up.** Needs a payer/settlement model.
- **Swipe-to-split an expense.**
- **Chores module.**
- **`docker-compose-new.yml` and `.env.example` still assume the key must be configured.** The Web API key default in `firebase_config.py` was restored on purpose (it matches production, and Web API keys are public by design), so login works with no variable set. But the compose file still aborts `docker compose up` when `.env` has no `FIREBASE_API_KEY` (`${FIREBASE_API_KEY:?...}`), and copying `.env.example` as-is would set the placeholder `your-firebase-web-api-key`, which overrides the default and breaks login. Both lines come from the issue #23 change and need the owner's decision.
- **Quiet hours for notifications.** Per-person switches per kind now exist (backend #13–14); a "don't disturb between 23:00 and 07:00" setting doesn't yet.
- **Tapping a notification doesn't open the related screen.** The app just opens.
- **A device token can occasionally be missed.** Push listeners are attached after `register()`; Capacitor's docs attach them first.
- **The permission prompt shows on the login screen**, before sign-in.
- **Changing the reminder hours can send a reminder straight away.** If the baby is already past the new time, the family gets one within a minute.
- **A word instead of a number in `/api/payments/add` returns a server error** (500) instead of a bad-input reply (400). The edge-case suite provokes this.
- **`categories.name` is UNIQUE table-wide.** Two families can't use the same custom name. This needs a table rebuild with `UNIQUE(family_id, name)`.
- **Dark mode.**
- **Clear the service-worker cache on logout.** Visited pages stay cached on the device, as before the refresh.
- **Feedings don't record who logged them.** There is no `added_by` there; this could be added like payments.
- **Status-bar colour and native splash drawable.** Check both on a real device.
- **Logged-out `/admin` redirect chain.** A logged-out visit goes to `/home` and then `/login` (existing behaviour, auth left untouched).
- **Earlier Android fallback text.** The native splash still says "ניהול משפחתי חכם"; the web copy uses "ניהול הבית של המשפחה".

## 10. Verification log

All 15 screens passed a final full pass on 19.9.2026. Each screen ran in its own clean browser: **370 checks, 0 failed.** After per-person notification settings were added, Settings was re-verified with 55 checks and the baby tracker with 46, and two extra checks cover the Android plugin layer and push recipients (bottom two rows). "Runs" counts the completed runs recorded while building each screen. The failures before green were real bugs found and fixed along the way, for example:

- white-on-white text on the baby timer card
- 43px calendar cells, one pixel under the 44px tap target
- an icon-only "+" button
- Hebrew final letters breaking the shopping department guess

| Screen | Checks | Final full pass | Runs | Failed runs before green |
|---|---|---|---|---|
| Base layout + nav | 21 | PASS | 3 | 1 |
| Error pages | 10 | PASS | 3 | 1 |
| Login | 10 | PASS | 2 | 0 |
| Register | 9 | PASS | 5 | 3 |
| Forgot password | 7 | PASS | 2 | 0 |
| Family setup | 14 | PASS | 2 | 0 |
| Home | 37 | PASS | 7 | 0 |
| Expenses (incl. editing the date) | 42 | PASS | 5 | 0 |
| Cycle analysis (new) | 33 | PASS | 4 | 1 |
| History | 29 | PASS | 4 | 0 |
| Shopping list | 47 | PASS | 4 | 1 |
| Baby tracker | 46 | PASS | 4 | 1 |
| Settings (hub + 4 screens, incl. my notifications) | 78 | PASS | 5 | 0 |
| Admin | 12 | PASS | 4 | 1 |
| Offline states | 17 | PASS | 2 | 0 |
| Android plugin layer (stand-in Capacitor plugins) | 18 | PASS | 1 | 0 |
| Who receives each push (unit check on a DB copy) | 10 | PASS | 1 | 0 |

**Existing API suites** (`test_files/`) ran against copies pointed at an isolated scratch server with a copy of the scratch database, never port 5000 or `finance_tracker.db`:

| Suite | Passed | Failed |
|---|---|---|
| test_production | 54 | 0 |
| test_edge_cases | 85 | 1 |
| test_flows | 62 | 0 |

That matches the pre-refresh baseline. The one failure is the known table-wide `categories.name` UNIQUE issue (see follow-ups).

**Incident during verification.** One check of the Android fallback page's retry button loaded the production URL once: `https://new.matanshimonwebapp.online/home` (a GET that redirected to its login page; nothing was submitted). The URL block I had set did not apply to top-level navigations. That check now runs on a local copy that points at the scratch server.

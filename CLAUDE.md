# OurHome IL — Project Context

## Overview
Family finance & household management app for Israeli families.
Flask + SQLite backend, Jinja2 templates, wrapped as Android app via Capacitor.
Firebase Cloud Messaging (FCM V1) for push notifications.

## Tech Stack
- **Backend**: Python/Flask, SQLite, JWT auth, Jinja2 templates
- **Android**: Capacitor WebView (loads from server URL), Firebase FCM
- **Dev**: PyCharm (Flask), Android Studio (Android), Windows/PowerShell

## Project Structure
```
app.py                  — Main Flask backend (~2700 lines)
templates/
  base.html             — Base template, push notification registration
  home.html             — Home dashboard
  dashboard.html        — Expense tracking dashboard
  shopping_list.html    — Shopping list
  baby_tracker.html     — Baby tracker (feedings, diapers, sleep)
  settings.html         — Settings (family, budget, categories, cycle_day)
  history.html          — Archive history
  login.html / register.html / etc.
android/                — Capacitor Android project
  app/src/main/java/.../MainActivity.java
capacitor.config.json   — Capacitor config (server URL)
firebase-service-account.json — FCM credentials
test_files/
  test_production.py    — 58 API tests
  test_edge_cases.py    — 87 edge case tests
  test_flows.py         — 60 flow tests
```

## Database Tables
families, users, payments, categories, archived_cycles, app_settings,
shopping_items, shopping_favorites, feedings, recurring_payments,
push_tokens, family_settings

## Key Architecture Decisions

### Billing Cycles (cycle_day)
- Each family sets a `cycle_day` (1-28) in family_settings
- `get_cycle_month(family_id)` returns the current cycle's month string
- `get_cycle_range(family_id)` returns start, end, label
- cycle_day=1 = calendar month (backward compatible)
- cycle_day=10 = cycle runs 10th to 9th of next month
- Auto-archive scheduler archives previous cycle when new one starts
- Only family admin (created_by) can change cycle_day

### Push Notifications
- FCM V1 API via service account
- `send_push_to_family(fid, title, body, exclude_user_id=None)`
- All user actions use exclude_user_id (don't notify yourself)
- System alerts (budget, feeding reminder) go to everyone
- Token registered via Capacitor PushNotifications plugin in base.html
- No push for checking shopping items (too noisy)

### Categories
- Default categories: family_id=NULL (9 system defaults)
- Custom categories: family_id=<family_id>
- `get_categories` returns both defaults + family customs
- DELETE blocked for defaults, allowed for custom (own family only)
- Categories JOIN in payment queries filters by family_id

### Family Isolation
- Every resource scoped by family_id
- All queries filter by family_id
- Tested: 3-family isolation stress test passes

### Auth
- Session-based for web, JWT for API/mobile
- `auto_jwt_auth` before_request populates session from JWT
- CSRF enforced for web forms, skipped for API (Bearer token)
- `require_auth` works for both session and JWT
- Duplicate email check in API register

## Recent Changes (Latest First)
1. Billing cycle feature (cycle_day, auto-archive, cycle labels)
2. Category management (family isolation, delete, duplicates fix)
3. Push notifications audit (all routes covered)
4. Feeding reminder (every 60s, sleep at end of loop)
5. Budget alerts (80% and 100% thresholds)
6. JWT API layer for Capacitor mobile app
7. Family admin vs system admin distinction

## Known Issues / TODO
- Production server + domain + SSL (currently local IP)
- Google Play Store upload
- Google Play Billing (free/premium)
- Email notifications not configured (need MAIL_USERNAME/PASSWORD env vars)
- App icon not yet added

## Testing
Run all tests with Flask running:
```
python test_files/test_production.py   # 58 tests — API basics
python test_files/test_edge_cases.py   # 87 tests — validation, injection, CORS
python test_files/test_flows.py        # 60 tests — complete user flows
```

## Important Patterns
- `get_cycle_month(fid)` instead of `now_israel().strftime('%Y-%m')`
- `int()` casting on all user IDs before comparison
- Push calls always include `exclude_user_id` for user actions
- `init_db()` checks existence before inserting default categories
- PowerShell quote escaping issues — use .py scripts instead of inline

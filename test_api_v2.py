#!/usr/bin/env python3
"""
OurHome IL — Step 2 Test: Existing routes with JWT
====================================================
python test_step2.py
"""

import sys, json, urllib.request, urllib.error, random, string, sqlite3, os

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
PASSED = 0
FAILED = 0
ERRORS = []

RND = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
USER1 = f"s2test_{RND}_a"
USER2 = f"s2test_{RND}_b"
FAMILY = f"s2fam_{RND}"
PW = "TestPass123"

# Cleanup old test data
DB = os.environ.get('DATABASE_PATH', 'finance_tracker.db')
if os.path.exists(DB):
    try:
        c = sqlite3.connect(DB)
        c.execute("DELETE FROM users WHERE username LIKE 's2test_%'")
        c.execute("DELETE FROM families WHERE name LIKE 's2fam_%'")
        c.commit()
        c.close()
    except:
        pass

print(f"🔧 Step 2 Test — existing routes with JWT")
print(f"   Users: {USER1}, {USER2}")
print()


def api(method, path, data=None, token=None, expect=200):
    global PASSED, FAILED, ERRORS
    url = f"{BASE_URL}{path}"
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req)
        status = resp.status
        raw = resp.read().decode()
        result = json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode()
        try:
            result = json.loads(raw) if raw.strip() else {}
        except:
            result = {"_raw": raw[:200]}
    name = f"{method} {path}"
    if status == expect:
        PASSED += 1
        print(f"  ✅ {name} -> {status}")
    else:
        FAILED += 1
        msg = f"  ❌ {name} -> {status} (expected {expect}) | {json.dumps(result, ensure_ascii=False)[:120]}"
        ERRORS.append(msg)
        print(msg)
    return status, result


def title(t):
    print(f"\n{'='*50}\n  {t}\n{'='*50}")


# ═══════════════════════════════════════
title("Setup — Register + Create Family")
# ═══════════════════════════════════════

# Register user 1
s, d = api("POST", "/api/auth/register", {
    "display_name": "יוזר אחד", "username": USER1,
    "email": f"{USER1}@test.com", "password": PW, "password2": PW
}, expect=201)
T1 = d.get("token")

# Register user 2
s, d = api("POST", "/api/auth/register", {
    "display_name": "יוזר שתיים", "username": USER2,
    "email": f"{USER2}@test.com", "password": PW, "password2": PW
}, expect=201)
T2 = d.get("token")

# Create family
s, d = api("POST", "/api/family/create", {"family_name": FAMILY}, token=T1, expect=201)
T1 = d.get("token", T1)
INVITE = d.get("family", {}).get("invite_code")

# Join family
s, d = api("POST", "/api/family/join", {"invite_code": INVITE}, token=T2)
T2 = d.get("token", T2)

print(f"       Setup complete: family={FAMILY}, code={INVITE}")


# ═══════════════════════════════════════
title("1. Home Summary (GET)")
# ═══════════════════════════════════════

s, d = api("GET", "/api/home-summary", token=T1)
if "finance" in d and "shopping" in d and "baby" in d:
    print(f"       All sections: ✅")


# ═══════════════════════════════════════
title("2. Categories (GET + POST)")
# ═══════════════════════════════════════

s, d = api("GET", "/api/categories", token=T1)
cats = d if isinstance(d, list) else d.get("categories", [])
print(f"       Categories: {len(cats)}")

s, d = api("POST", "/api/categories", {"name": f"cat_{RND}", "color": "#ff0000"}, token=T1, expect=201)


# ═══════════════════════════════════════
title("3. Payments (POST + GET + PUT + DELETE)")
# ═══════════════════════════════════════

# Add payment
s, d = api("POST", "/api/payments/add", {
    "description": f"תשלום טסט {RND}", "amount": 99.9, "category": "כללי"
}, token=T1, expect=201)
payment_id = d.get("id")
if payment_id:
    print(f"       Added payment: #{payment_id}")

# Get payments
s, d = api("GET", "/api/payments", token=T1)

# Update payment (if we got an ID)
if payment_id:
    api("PUT", f"/api/payments/{payment_id}", {
        "description": "תשלום מעודכן", "amount": 150
    }, token=T1)

# Delete payment
if payment_id:
    api("DELETE", f"/api/payments/{payment_id}", token=T1)


# ═══════════════════════════════════════
title("4. Shopping List (POST + GET + PUT + DELETE)")
# ═══════════════════════════════════════

# Add item
s, d = api("POST", "/api/shopping-items", {
    "name": f"חלב טסט {RND}", "quantity": 2
}, token=T1, expect=201)
item_id = d.get("id")
if item_id:
    print(f"       Added item: #{item_id}")

# Get items
s, d = api("GET", "/api/shopping-items", token=T1)

# Update item
if item_id:
    api("PUT", f"/api/shopping-items/{item_id}", {"checked": True}, token=T1)

# Delete item
if item_id:
    api("DELETE", f"/api/shopping-items/{item_id}", token=T1)

# Clear completed
api("DELETE", "/api/shopping-items/clear-completed", token=T1)


# ═══════════════════════════════════════
title("5. Baby Tracker (POST + GET + PUT + DELETE)")
# ═══════════════════════════════════════

# Add feeding
s, d = api("POST", "/api/feedings", {
    "feeding_type": "bottle", "amount": 120, "notes": "טסט"
}, token=T1, expect=201)
feed_id = d.get("id")
if feed_id:
    print(f"       Added feeding: #{feed_id}")

# Get feedings
api("GET", "/api/feedings/data", token=T1)

# Update feeding
if feed_id:
    api("PUT", f"/api/feedings/{feed_id}", {"amount": 150, "notes": "מעודכן"}, token=T1)

# Delete feeding
if feed_id:
    api("DELETE", f"/api/feedings/{feed_id}", token=T1)


# ═══════════════════════════════════════
title("6. Recurring Payments (POST + GET + PUT + DELETE)")
# ═══════════════════════════════════════

s, d = api("POST", "/api/recurring", {
    "description": f"חוזר {RND}", "amount": 50, "category": "קבועים"
}, token=T1, expect=201)
rec_id = d.get("id")
if rec_id:
    print(f"       Added recurring: #{rec_id}")

api("GET", "/api/recurring", token=T1)

if rec_id:
    api("PUT", f"/api/recurring/{rec_id}", {
        "description": "חוזר מעודכן", "amount": 75
    }, token=T1)
    api("DELETE", f"/api/recurring/{rec_id}", token=T1)


# ═══════════════════════════════════════
title("7. History & Charts")
# ═══════════════════════════════════════

api("GET", "/api/history/data", token=T1)
api("GET", "/api/chart_data", token=T1)


# ═══════════════════════════════════════
title("8. Family Management")
# ═══════════════════════════════════════

api("GET", "/api/family/info", token=T1)

# Remove member (user2 from family)
s, d = api("POST", "/api/family/remove-member", {"user_id": None}, token=T1)

# Family leave (user2)
api("POST", "/api/family/leave", token=T2)


# ═══════════════════════════════════════
title("9. Auth — no token = JSON 401 (not redirect)")
# ═══════════════════════════════════════

s, d = api("GET", "/api/home-summary", expect=401)
if d.get("code") == "AUTH_REQUIRED":
    print(f"       JSON error: ✅ (not HTML redirect)")

s, d = api("GET", "/api/payments", expect=401)
if d.get("code") == "AUTH_REQUIRED":
    print(f"       Payments 401: ✅")

s, d = api("POST", "/api/payments/add", {"description": "x", "amount": 1}, expect=401)
if d.get("code") == "AUTH_REQUIRED":
    print(f"       POST 401: ✅")


# ═══════════════════════════════════════
title("10. Web routes still work (HTML, not JSON)")
# ═══════════════════════════════════════

for route in ["/login", "/register"]:
    try:
        req = urllib.request.Request(f"{BASE_URL}{route}")
        resp = urllib.request.urlopen(req)
        html = resp.read().decode()
        if "<html" in html.lower():
            PASSED += 1
            print(f"  ✅ GET {route} -> HTML page")
        else:
            FAILED += 1
            print(f"  ❌ GET {route} -> not HTML")
    except Exception as e:
        FAILED += 1
        print(f"  ❌ GET {route} -> {e}")


# ═══════════════════════════════════════
title("🧹 Cleanup")
# ═══════════════════════════════════════

if os.path.exists(DB):
    try:
        c = sqlite3.connect(DB)
        c.execute("DELETE FROM users WHERE username LIKE 's2test_%'")
        c.execute("DELETE FROM families WHERE name LIKE 's2fam_%'")
        c.execute(f"DELETE FROM payments WHERE description LIKE '%{RND}%'")
        c.execute(f"DELETE FROM shopping_items WHERE name LIKE '%{RND}%'")
        c.execute(f"DELETE FROM recurring_payments WHERE description LIKE '%{RND}%'")
        c.commit()
        c.close()
        print(f"  ✅ Cleaned up")
    except Exception as e:
        print(f"  ⚠️  {e}")


# ═══════════════════════════════════════
title("📊 סיכום שלב 2")
# ═══════════════════════════════════════

total = PASSED + FAILED
print(f"""
  סה"כ:   {total} בדיקות
  עברו:    {PASSED} ✅
  נכשלו:   {FAILED} ❌
""")

if ERRORS:
    print("  שגיאות:")
    for e in ERRORS:
        print(f"  {e}")
    print()

if FAILED == 0:
    print("  🎉 שלב 2 הושלם! כל הנתיבים עובדים עם JWT!")
else:
    print(f"  ⚠️  {FAILED} בדיקות נכשלו")

sys.exit(0 if FAILED == 0 else 1)
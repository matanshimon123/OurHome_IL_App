"""
OurHome IL — Test Suite מלא
============================
כולל:
1. בדיקות יחידה (pytest) — לוגיקה ו-API
2. בדיקות עומס (locust) — מאות משתמשים מקבילים

הרצה:
  pytest tests/locustfile.py -v -k "not Locust"     # בדיקות בלבד
  locust -f tests/locustfile.py --host=http://localhost:5000  # עומס
"""

import random
import string
import time
import threading
import requests
import pytest

# ── הגדרות ──────────────────────────────────────────────
BASE_URL = "http://localhost:5000"
TEST_DB = "finance_tracker_test.db"
CATEGORIES = ['קבועים', 'משק בית', 'קניות - סופר', 'רכב', 'תינוק', 'כללי']
FEEDING_TYPES = ['bottle', 'breastfeeding', 'solid', 'diaper', 'medication', 'sleep']
SHOP_ITEMS = ['חלב', 'לחם', 'ביצים', 'גבינה', 'עגבניות', 'מלפפון', 'שמן', 'סוכר']
PAYMENTS = [
    ('נטפליקס', 55), ('חשמל', 380), ('מים', 120), ('סופר', 450),
    ('דלק', 300), ('תרופות', 80), ('מסעדה', 200), ('ביגוד', 150),
]


def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


# ════════════════════════════════════════════════════════
# SECTION 1 — Helper: Session-based client
# ════════════════════════════════════════════════════════

class AppClient:
    """Client שמחזיק session כמו דפדפן אמיתי"""

    def __init__(self):
        self.s = requests.Session()
        self.username = None
        self.family_code = None
        self.base = BASE_URL

    def _csrf(self):
        """קרא CSRF token מה-cookie"""
        return self.s.cookies.get('csrf_token', '')

    def register(self, username=None, password='Test1234!'):
        username = username or f"user_{rand_str()}"
        display = f"Test {username}"
        email = f"{username}@test.com"
        # קבל את ה-CSRF קודם
        self.s.get(f"{self.base}/register")
        r = self.s.post(f"{self.base}/register", data={
            'display_name': display,
            'username': username,
            'email': email,
            'password': password,
            'password2': password,
            'csrf_token': self._csrf(),
        }, allow_redirects=True)
        self.username = username
        return r

    def login(self, username, password='Test1234!'):
        self.s.get(f"{self.base}/login")
        r = self.s.post(f"{self.base}/login", data={
            'username': username,
            'password': password,
            'csrf_token': self._csrf(),
        }, allow_redirects=True)
        self.username = username
        return r

    def create_family(self, name=None):
        name = name or f"משפחת {rand_str(4)}"
        self.s.get(f"{self.base}/family")
        r = self.s.post(f"{self.base}/family/create", data={
            'family_name': name,
            'csrf_token': self._csrf(),
        }, allow_redirects=True)
        # חלץ את קוד ההזמנה מהדף
        if 'invite_code' in r.text or 'קוד' in r.text:
            import re
            m = re.search(r'id="inviteCode"[^>]*>([A-Z0-9]{6})', r.text)
            if m:
                self.family_code = m.group(1)
        return r

    def join_family(self, code):
        self.s.get(f"{self.base}/family")
        r = self.s.post(f"{self.base}/family/join", data={
            'invite_code': code,
            'csrf_token': self._csrf(),
        }, allow_redirects=True)
        return r

    def add_payment(self, desc=None, amount=None, category=None):
        desc = desc if desc is not None else random.choice(PAYMENTS)[0]
        amount = amount if amount is not None else random.choice(PAYMENTS)[1]
        category = category if category is not None else random.choice(CATEGORIES)
        r = self.s.post(f"{self.base}/api/payments/add",
                        json={'description': desc, 'amount': amount, 'category': category},
                        headers={'X-CSRFToken': self._csrf()})
        return r

    def get_payments(self):
        return self.s.get(f"{self.base}/api/payments")

    def add_shopping(self, name=None, qty=1):
        name = name or random.choice(SHOP_ITEMS)
        r = self.s.post(f"{self.base}/api/shopping-items",
                        json={'name': name, 'quantity': qty, 'category': ''},
                        headers={'X-CSRFToken': self._csrf()})
        return r

    def get_shopping(self):
        return self.s.get(f"{self.base}/api/shopping-items")

    def check_item(self, item_id, checked=True):
        r = self.s.put(f"{self.base}/api/shopping-items/{item_id}",
                       json={'checked': checked},
                       headers={'X-CSRFToken': self._csrf()})
        return r

    def add_feeding(self, ftype=None, amount=0):
        ftype = ftype or random.choice(FEEDING_TYPES)
        if ftype == 'bottle':
            amount = random.randint(60, 180)
        r = self.s.post(f"{self.base}/api/feedings",
                        json={'feeding_type': ftype, 'amount': amount, 'notes': ''},
                        headers={'X-CSRFToken': self._csrf()})
        return r

    def get_feedings(self):
        return self.s.get(f"{self.base}/api/feedings/data")

    def home_summary(self):
        return self.s.get(f"{self.base}/api/home-summary")

    def logout(self):
        return self.s.get(f"{self.base}/logout", allow_redirects=True)


# ════════════════════════════════════════════════════════
# SECTION 2 — pytest: בדיקות יחידה ו-integration
# ════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def server_up():
    """וודא שהשרת רץ"""
    try:
        r = requests.get(BASE_URL, timeout=5)
        assert r.status_code in (200, 302, 301)
    except Exception:
        pytest.skip("השרת לא רץ — הפעל את app.py ואז הרץ את הטסטים")


class TestRegistration:

    def test_register_new_user(self, server_up):
        """הרשמה של משתמש חדש"""
        c = AppClient()
        r = c.register()
        assert r.status_code == 200
        assert 'family' in r.url or 'home' in r.url, "אחרי הרשמה צריך להגיע ל-family/home"

    def test_duplicate_username(self, server_up):
        """שם משתמש כפול נדחה"""
        c1 = AppClient()
        username = f"dup_{rand_str()}"
        c1.register(username=username)
        c2 = AppClient()
        r = c2.register(username=username)
        assert 'תפוס' in r.text or 'error' in r.text.lower() or r.url.endswith('/register'), \
            "שם משתמש כפול צריך להיות נדחה"

    def test_invalid_username_format(self, server_up):
        """שם משתמש עם תווים לא חוקיים"""
        c = AppClient()
        c.s.get(f"{BASE_URL}/register")
        r = c.s.post(f"{BASE_URL}/register", data={
            'display_name': 'Test',
            'username': 'user name!',  # רווח ו-! לא חוקיים
            'email': 'test@test.com',
            'password': 'Test1234',
            'password2': 'Test1234',
            'csrf_token': c._csrf(),
        }, allow_redirects=True)
        assert 'register' in r.url or 'תווים' in r.text

    def test_password_too_short(self, server_up):
        """סיסמה קצרה מדי נדחית"""
        c = AppClient()
        c.s.get(f"{BASE_URL}/register")
        r = c.s.post(f"{BASE_URL}/register", data={
            'display_name': 'Test',
            'username': f'u_{rand_str()}',
            'email': 'test@test.com',
            'password': '123',
            'password2': '123',
            'csrf_token': c._csrf(),
        }, allow_redirects=True)
        assert 'register' in r.url or '6' in r.text

    def test_password_mismatch(self, server_up):
        """סיסמאות לא תואמות"""
        c = AppClient()
        c.s.get(f"{BASE_URL}/register")
        r = c.s.post(f"{BASE_URL}/register", data={
            'display_name': 'Test',
            'username': f'u_{rand_str()}',
            'email': 'test@test.com',
            'password': 'Test1234',
            'password2': 'Different1234',
            'csrf_token': c._csrf(),
        }, allow_redirects=True)
        assert 'register' in r.url or 'תואמות' in r.text


class TestLogin:

    def test_login_correct(self, server_up):
        """התחברות עם נתונים נכונים"""
        c = AppClient()
        un = f"login_{rand_str()}"
        c.register(username=un)
        c.logout()
        r = c.login(un)
        assert 'login' not in r.url

    def test_login_wrong_password(self, server_up):
        """התחברות עם סיסמה שגויה"""
        c = AppClient()
        un = f"wp_{rand_str()}"
        c.register(username=un)
        c.logout()
        r = c.login(un, password='WrongPass!')
        assert 'login' in r.url or 'שגויים' in r.text

    def test_login_nonexistent_user(self, server_up):
        """התחברות עם משתמש שלא קיים"""
        c = AppClient()
        r = c.login(f"ghost_{rand_str()}")
        assert 'login' in r.url or 'שגויים' in r.text

    def test_session_persists(self, server_up):
        """session נשמר אחרי התחברות"""
        c = AppClient()
        un = f"sess_{rand_str()}"
        c.register(username=un)
        c.create_family()
        r = c.home_summary()
        assert r.status_code == 200


class TestFamily:

    def test_create_family(self, server_up):
        """יצירת משפחה"""
        c = AppClient()
        c.register()
        r = c.create_family("משפחת טסט")
        assert r.status_code == 200

    def test_join_family(self, server_up):
        """הצטרפות למשפחה קיימת"""
        # משתמש א' יוצר
        c1 = AppClient()
        c1.register()
        c1.create_family()
        code = c1.family_code

        if not code:
            pytest.skip("לא הצלחנו לחלץ קוד הזמנה")

        # משתמש ב' מצטרף
        c2 = AppClient()
        c2.register()
        r = c2.join_family(code)
        assert r.status_code == 200

    def test_family_isolation(self, server_up):
        """בדיקה שמשפחות לא רואות נתונים אחד של השני"""
        # משפחה א'
        c1 = AppClient()
        c1.register()
        c1.create_family()
        c1.add_payment("הוצאה סודית", 999, "כללי")

        # משפחה ב'
        c2 = AppClient()
        c2.register()
        c2.create_family()

        payments = c2.get_payments().json()
        descs = [p['description'] for p in payments]
        assert "הוצאה סודית" not in descs, "משפחה ב לא אמורה לראות נתוני משפחה א"


class TestPayments:

    @pytest.fixture
    def logged_client(self, server_up):
        c = AppClient()
        c.register()
        c.create_family()
        return c

    def test_add_payment(self, logged_client):
        """הוספת תשלום"""
        r = logged_client.add_payment("נטפליקס", 55, "קבועים")
        assert r.status_code == 201

    def test_add_invalid_payment(self, logged_client):
        """תשלום עם סכום שלילי נדחה"""
        r = logged_client.add_payment("בדיקה", -50, "כללי")
        assert r.status_code == 400

    def test_add_zero_payment(self, logged_client):
        """תשלום עם סכום 0 נדחה"""
        r = logged_client.add_payment("בדיקה", 0, "כללי")
        assert r.status_code == 400

    def test_get_payments(self, logged_client):
        """קבלת רשימת תשלומים"""
        logged_client.add_payment("טסט", 100, "כללי")
        r = logged_client.get_payments()
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_delete_payment(self, logged_client):
        """מחיקת תשלום"""
        logged_client.add_payment("למחיקה", 50, "כללי")
        payments = logged_client.get_payments().json()
        pid = payments[0]['id']
        r = logged_client.s.post(f"{BASE_URL}/delete_payment/{pid}?api=1",
                                 headers={'X-CSRFToken': logged_client._csrf()})
        assert r.status_code == 200
        payments_after = logged_client.get_payments().json()
        ids_after = [p['id'] for p in payments_after]
        assert pid not in ids_after

    def test_update_payment(self, logged_client):
        """עדכון תשלום"""
        logged_client.add_payment("ישן", 100, "כללי")
        pid = logged_client.get_payments().json()[0]['id']
        r = logged_client.s.put(f"{BASE_URL}/api/payments/{pid}",
                                json={'description': 'חדש', 'amount': 200},
                                headers={'X-CSRFToken': logged_client._csrf()})
        assert r.status_code == 200


class TestShopping:

    @pytest.fixture
    def logged_client(self, server_up):
        c = AppClient()
        c.register()
        c.create_family()
        return c

    def test_add_item(self, logged_client):
        """הוספת פריט לרשימה"""
        r = logged_client.add_shopping("חלב", 2)
        assert r.status_code == 201

    def test_get_items(self, logged_client):
        """קבלת רשימת קניות"""
        logged_client.add_shopping("לחם")
        r = logged_client.get_shopping()
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_check_item(self, logged_client):
        """סימון פריט כנקנה"""
        logged_client.add_shopping("ביצים")
        items = logged_client.get_shopping().json()
        iid = items[0]['id']
        r = logged_client.check_item(iid, True)
        assert r.status_code == 200
        items_after = logged_client.get_shopping().json()
        item = next(i for i in items_after if i['id'] == iid)
        assert item['checked'] == True

    def test_delete_item(self, logged_client):
        """מחיקת פריט"""
        logged_client.add_shopping("מוצר למחיקה")
        items = logged_client.get_shopping().json()
        iid = items[0]['id']
        r = logged_client.s.delete(f"{BASE_URL}/api/shopping-items/{iid}",
                                   headers={'X-CSRFToken': logged_client._csrf()})
        assert r.status_code == 200

    def test_empty_name_rejected(self, logged_client):
        """פריט ללא שם נדחה"""
        r = logged_client.s.post(f"{BASE_URL}/api/shopping-items",
                                 json={'name': '', 'quantity': 1},
                                 headers={'X-CSRFToken': logged_client._csrf()})
        assert r.status_code == 400


class TestBabyTracker:

    @pytest.fixture
    def logged_client(self, server_up):
        c = AppClient()
        c.register()
        c.create_family()
        return c

    def test_add_bottle(self, logged_client):
        """הוספת האכלת בקבוק"""
        r = logged_client.add_feeding('bottle', 120)
        assert r.status_code == 201

    def test_add_diaper(self, logged_client):
        """הוספת חיתול"""
        r = logged_client.add_feeding('diaper', 0)
        assert r.status_code == 201

    def test_get_feedings(self, logged_client):
        """קבלת נתוני האכלות"""
        logged_client.add_feeding('bottle', 100)
        r = logged_client.get_feedings()
        assert r.status_code == 200
        data = r.json()
        assert 'stats' in data
        assert 'today_feedings' in data

    def test_feeding_stats(self, logged_client):
        """סטטיסטיקות האכלה נכונות"""
        logged_client.add_feeding('bottle', 100)
        logged_client.add_feeding('bottle', 80)
        r = logged_client.get_feedings()
        stats = r.json()['stats']
        assert stats['bottles'] >= 2
        assert stats['bottle_ml'] >= 180


class TestHomeSummary:

    def test_home_summary(self, server_up):
        """סיכום דף הבית"""
        c = AppClient()
        c.register()
        c.create_family()
        c.add_payment("חשמל", 380, "קבועים")
        c.add_shopping("חלב")
        c.add_feeding('bottle', 120)

        r = c.home_summary()
        assert r.status_code == 200
        data = r.json()
        assert 'finance' in data
        assert 'shopping' in data
        assert 'baby' in data
        assert data['finance']['count'] >= 1
        assert data['shopping']['total'] >= 1
        assert data['baby']['bottles'] >= 1


# ════════════════════════════════════════════════════════
# SECTION 3 — Load Test (Locust) — מאות משתמשים
# ════════════════════════════════════════════════════════

try:
    from locust import HttpUser, task, between, events
    import urllib3

    urllib3.disable_warnings()


    class OurHomeUser(HttpUser):
        """
        משתמש וירטואלי שמדמה שימוש אמיתי באפליקציה.
        כל משתמש:
        1. נרשם
        2. יוצר משפחה
        3. מבצע פעולות אקראיות בלופ
        """
        wait_time = between(1, 4)  # המתנה אקראית בין פעולות

        def on_start(self):
            """נרשם והתחבר"""
            self.username = f"load_{rand_str(10)}"
            self.password = "LoadTest1!"
            self.logged_in = False
            self.family_created = False
            self.csrf = ""

            # הרשמה
            self.client.get("/register", name="[setup] register page")
            self.csrf = self.client.cookies.get('csrf_token', '')
            r = self.client.post("/register",
                                 data={
                                     'display_name': f"Load User {self.username}",
                                     'username': self.username,
                                     'email': f"{self.username}@loadtest.com",
                                     'password': self.password,
                                     'password2': self.password,
                                     'csrf_token': self.csrf,
                                 },
                                 allow_redirects=True,
                                 name="[setup] register"
                                 )
            self.csrf = self.client.cookies.get('csrf_token', '')

            # יצירת משפחה
            if 'family' in r.url or 'family' in (r.history[-1].headers.get('Location', '') if r.history else ''):
                r2 = self.client.post("/family/create",
                                      data={
                                          'family_name': f"משפחת {self.username[:6]}",
                                          'csrf_token': self.csrf,
                                      },
                                      allow_redirects=True,
                                      name="[setup] create family"
                                      )
                self.csrf = self.client.cookies.get('csrf_token', '')
                self.family_created = True

            self.logged_in = True

        @task(4)
        def view_home(self):
            """צפייה בדף הבית — הכי נפוץ"""
            self.client.get("/home", name="view: home")
            self.client.get("/api/home-summary", name="api: home-summary")
            self.csrf = self.client.cookies.get('csrf_token', self.csrf)

        @task(3)
        def view_dashboard(self):
            """צפייה בדשבורד הוצאות"""
            self.client.get("/dashboard", name="view: dashboard")
            self.client.get("/api/payments", name="api: get-payments")

        @task(2)
        def add_payment(self):
            """הוספת תשלום"""
            desc, amount = random.choice(PAYMENTS)
            self.client.post("/api/payments/add",
                             json={
                                 'description': desc,
                                 'amount': amount + random.randint(-10, 50),
                                 'category': random.choice(CATEGORIES),
                             },
                             headers={'X-CSRFToken': self.csrf},
                             name="api: add-payment"
                             )

        @task(2)
        def shopping_flow(self):
            """זרימת קניות — הוסף + סמן"""
            self.client.get("/api/shopping-items", name="api: get-shopping")
            # הוסף פריט
            item_name = random.choice(SHOP_ITEMS)
            r = self.client.post("/api/shopping-items",
                                 json={'name': item_name, 'quantity': random.randint(1, 3), 'category': ''},
                                 headers={'X-CSRFToken': self.csrf},
                                 name="api: add-shopping"
                                 )
            if r.status_code == 201:
                iid = r.json().get('id')
                if iid:
                    # סמן כנקנה
                    self.client.put(f"/api/shopping-items/{iid}",
                                    json={'checked': True},
                                    headers={'X-CSRFToken': self.csrf},
                                    name="api: check-shopping"
                                    )

        @task(2)
        def baby_flow(self):
            """רישום אירוע תינוק"""
            ftype = random.choice(FEEDING_TYPES)
            amount = random.randint(60, 180) if ftype == 'bottle' else 0
            self.client.post("/api/feedings",
                             json={'feeding_type': ftype, 'amount': amount, 'notes': ''},
                             headers={'X-CSRFToken': self.csrf},
                             name="api: add-feeding"
                             )
            self.client.get("/api/feedings/data", name="api: feedings-data")

        @task(1)
        def view_history(self):
            """צפייה בהיסטוריה"""
            self.client.get("/api/history/data", name="api: history")

        @task(1)
        def view_shopping_page(self):
            """עמוד קניות"""
            self.client.get("/shopping-list", name="view: shopping")

        @task(1)
        def view_baby_page(self):
            """עמוד תינוק"""
            self.client.get("/baby-tracker", name="view: baby")

        @task(1)
        def view_chart_data(self):
            """נתוני גרף"""
            self.client.get("/api/chart_data", name="api: chart-data")

        def on_stop(self):
            """התנתק"""
            self.client.get("/logout", name="[teardown] logout")

except ImportError:
    pass  # locust לא מותקן — בדיקות pytest עדיין עובדות


# ════════════════════════════════════════════════════════
# SECTION 4 — Concurrent Test (threading) — ללא Locust
# ════════════════════════════════════════════════════════

class TestConcurrent:
    """בדיקת מקביליות עם Python threads — ללא Locust"""

    def test_10_concurrent_users(self, server_up):
        """10 משתמשים מוסיפים תשלומים בו-זמנית"""
        errors = []
        results = []

        def user_flow():
            try:
                c = AppClient()
                c.register()
                c.create_family()
                for _ in range(5):
                    r = c.add_payment()
                    results.append(r.status_code)
                    time.sleep(0.1)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=user_flow) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(errors) == 0, f"שגיאות: {errors}"
        assert all(s == 201 for s in results), f"חלק מהתשלומים נכשלו: {results}"

    def test_family_concurrent_members(self, server_up):
        """שני חברי משפחה מוסיפים נתונים בו-זמנית"""
        c1 = AppClient()
        c1.register()
        c1.create_family()
        code = c1.family_code

        if not code:
            pytest.skip("לא הצלחנו לחלץ קוד הזמנה")

        c2 = AppClient()
        c2.register()
        c2.join_family(code)

        errors = []

        def user1():
            for _ in range(10):
                r = c1.add_payment("חבר1", 100, "כללי")
                if r.status_code != 201:
                    errors.append(f"user1: {r.status_code}")

        def user2():
            for _ in range(10):
                r = c2.add_shopping("פריט_חבר2")
                if r.status_code != 201:
                    errors.append(f"user2: {r.status_code}")

        t1 = threading.Thread(target=user1)
        t2 = threading.Thread(target=user2)
        t1.start();
        t2.start()
        t1.join();
        t2.join()

        assert len(errors) == 0, f"שגיאות מקביליות: {errors}"

        # וודא שהנתונים נשמרו נכון
        payments = c1.get_payments().json()
        shopping = c1.get_shopping().json()
        assert len(payments) >= 10
        assert len(shopping) >= 10

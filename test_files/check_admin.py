import sqlite3, os

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'finance_tracker.db')
print(f"DB path: {db}")
print(f"DB exists: {os.path.exists(db)}")

if not os.path.exists(db):
    print("DB NOT FOUND!")
else:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    users = c.execute("SELECT id, username, display_name FROM users LIMIT 10").fetchall()
    print(f"Total users found: {len(users)}")
    for u in users:
        print(f"  {u['username']} ({u['display_name']})")
    c.close()
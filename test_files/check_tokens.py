import sqlite3, os
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'finance_tracker.db')
if not os.path.exists(db_path):
    db_path = '../finance_tracker.db'
c = sqlite3.connect(db_path)
c.row_factory = sqlite3.Row
rows = c.execute('''
    SELECT u.username, u.display_name, COUNT(p.id) as tokens
    FROM users u
    LEFT JOIN push_tokens p ON u.id = p.user_id
    WHERE u.family_id IS NOT NULL
    GROUP BY u.id
''').fetchall()
for r in rows:
    status = '✅' if r['tokens'] > 0 else '❌ NO PUSH TOKEN'
    print(f'{r["display_name"]} ({r["username"]}): {r["tokens"]} tokens {status}')
c.close()
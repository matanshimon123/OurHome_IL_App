import sqlite3
c = sqlite3.connect('finance_tracker.db')
c.execute("DELETE FROM users WHERE username LIKE 'apitest_%' OR username LIKE 'test_%'")
c.execute("DELETE FROM families WHERE name LIKE 'fam_%' OR name LIKE 'משפחת בדיקה%'")
c.commit()
print(f"Done! {c.total_changes} rows deleted")
c.close()
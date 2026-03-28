import sqlite3, os
c = sqlite3.connect('finance_tracker.db')
c.row_factory = sqlite3.Row

# Check recurring payments
recs = c.execute('SELECT * FROM recurring_payments ORDER BY id DESC LIMIT 5').fetchall()
print(f"Recurring: {len(recs)}")
for r in recs:
    print(f"  id={r['id']} fid={r['family_id']} desc={r['description']}")

# Check recent payments  
pays = c.execute('SELECT * FROM payments ORDER BY id DESC LIMIT 5').fetchall()
print(f"\nRecent payments: {len(pays)}")
for p in pays:
    print(f"  id={p['id']} fid={p['family_id']} desc={p['description']} month={p['month']}")

c.close()
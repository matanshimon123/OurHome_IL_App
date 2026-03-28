"""
ניקוי DB — מוחק משתמשי test/load ומשפחות ריקות
הרץ מתיקיית הפרויקט: python cleanup_db.py
"""
import sqlite3

c = sqlite3.connect('../finance_tracker.db')
c.row_factory = sqlite3.Row

# Count before
total_users = c.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
total_families = c.execute('SELECT COUNT(*) as c FROM families').fetchone()['c']

# Find test/load users
test_users = c.execute("""
    SELECT id, username FROM users 
    WHERE username LIKE 'test_%' OR username LIKE 'load_%' 
    OR username LIKE 'sess_%' OR username LIKE 'user_%'
    OR username LIKE 'apitest_%'
""").fetchall()

test_ids = [u['id'] for u in test_users]
print(f'Found {len(test_ids)} test/load users out of {total_users} total')

if not test_ids:
    print('Nothing to clean!')
    c.close()
    exit()

confirm = input(f'Delete {len(test_ids)} test users? (yes/no): ')
if confirm.lower() != 'yes':
    print('Cancelled.')
    c.close()
    exit()

# Delete related data
placeholders = ','.join('?' * len(test_ids))

# Get family IDs of test users
test_family_ids = [r['family_id'] for r in c.execute(
    f'SELECT DISTINCT family_id FROM users WHERE id IN ({placeholders}) AND family_id IS NOT NULL',
    test_ids).fetchall()]

# Delete test users' data
c.execute(f'DELETE FROM push_tokens WHERE user_id IN ({placeholders})', test_ids)
c.execute(f'DELETE FROM feedings WHERE family_id IN (SELECT DISTINCT family_id FROM users WHERE id IN ({placeholders}))', test_ids)
c.execute(f'DELETE FROM users WHERE id IN ({placeholders})', test_ids)

# Delete empty families (no users left)
if test_family_ids:
    for fid in test_family_ids:
        remaining = c.execute('SELECT COUNT(*) as c FROM users WHERE family_id=?', (fid,)).fetchone()['c']
        if remaining == 0:
            c.execute('DELETE FROM payments WHERE family_id=?', (fid,))
            c.execute('DELETE FROM shopping_items WHERE family_id=?', (fid,))
            c.execute('DELETE FROM shopping_favorites WHERE family_id=?', (fid,))
            c.execute('DELETE FROM recurring_payments WHERE family_id=?', (fid,))
            c.execute('DELETE FROM archived_cycles WHERE family_id=?', (fid,))
            c.execute('DELETE FROM family_settings WHERE family_id=?', (fid,))
            c.execute('DELETE FROM families WHERE id=?', (fid,))

c.commit()

# Count after
after_users = c.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
after_families = c.execute('SELECT COUNT(*) as c FROM families').fetchone()['c']

print(f'\n✅ Done!')
print(f'Users:    {total_users} → {after_users}')
print(f'Families: {total_families} → {after_families}')

# Show remaining real users
print('\nRemaining users:')
for u in c.execute('SELECT username, display_name, family_id FROM users ORDER BY id').fetchall():
    print(f'  {u["display_name"]} ({u["username"]}) — family_id={u["family_id"]}')

c.close()
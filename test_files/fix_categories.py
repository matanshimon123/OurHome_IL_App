"""
תיקון קטגוריות — מנקה כפילויות, שומר רק 9 ברירות מחדל
הרץ: python fix_categories.py
"""
import sqlite3

c = sqlite3.connect('../finance_tracker.db')
c.row_factory = sqlite3.Row

# 9 ברירות מחדל
DEFAULTS = {
    'קבועים', 'משק בית', 'קניות - סופר', 'קניות - אופנה',
    'רכב', 'תינוק', 'בילויים / פנאי', 'טיפוח', 'כללי'
}

# Count before
total = c.execute('SELECT COUNT(*) as c FROM categories').fetchone()['c']
print(f'Before: {total} categories')

# For each default category, keep only the LOWEST id
for name in DEFAULTS:
    rows = c.execute('SELECT id FROM categories WHERE name=? ORDER BY id', (name,)).fetchall()
    if len(rows) > 1:
        keep_id = rows[0]['id']
        delete_ids = [r['id'] for r in rows[1:]]
        placeholders = ','.join('?' * len(delete_ids))
        c.execute(f'DELETE FROM categories WHERE id IN ({placeholders})', delete_ids)
        print(f'  {name}: kept id={keep_id}, deleted {len(delete_ids)} duplicates')

# Delete test categories (not defaults, no family_id)
test_cats = c.execute(
    'SELECT id, name FROM categories WHERE family_id IS NULL AND name NOT IN (?,?,?,?,?,?,?,?,?)',
    tuple(DEFAULTS)).fetchall()
for cat in test_cats:
    c.execute('DELETE FROM categories WHERE id=?', (cat['id'],))
    print(f'  Deleted test category: {cat["name"]} (id={cat["id"]})')

# Make sure all defaults have family_id=NULL (global)
c.execute('UPDATE categories SET family_id=NULL WHERE name IN (?,?,?,?,?,?,?,?,?)',
          tuple(DEFAULTS))

c.commit()

# Count after
after = c.execute('SELECT COUNT(*) as c FROM categories').fetchone()['c']
cats = c.execute('SELECT id, name, color, family_id FROM categories ORDER BY name').fetchall()
print(f'\nAfter: {after} categories')
for cat in cats:
    fid = cat['family_id']
    label = 'DEFAULT' if fid is None else f'family={fid}'
    print(f'  id={cat["id"]} {cat["name"]} ({label})')

c.close()
print('\n✅ Done!')
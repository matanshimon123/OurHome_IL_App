import sqlite3
c = sqlite3.connect('../finance_tracker.db')
c.row_factory = sqlite3.Row

# Show all categories
cats = c.execute('SELECT id, name, color, family_id FROM categories ORDER BY name').fetchall()
print(f'Total categories: {len(cats)}')
for cat in cats:
    print(f'  id={cat["id"]} name={cat["name"]} family_id={cat["family_id"]}')

c.close()
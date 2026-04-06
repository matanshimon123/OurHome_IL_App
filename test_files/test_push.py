"""
הרץ מהפרויקט:  python test_push.py
ישלח push ישירות לשני הטוקנים ויראה את התגובה מ-FCM
"""
import sqlite3
import json
import urllib.request as urlreq
import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
import os

# ── טען FCM credentials ──
SA_PATH = '../firebase-service-account.json'
SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']

creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
creds.refresh(google.auth.transport.requests.Request())
access_token = creds.token

with open(SA_PATH) as f:
    project_id = json.load(f).get('project_id')

print(f'Project: {project_id}')
print(f'Token: {access_token[:40]}...\n')

# ── שלוף טוקנים מה-DB ──
conn = sqlite3.connect('../finance_tracker.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('''
    SELECT u.username, p.token 
    FROM push_tokens p 
    JOIN users u ON p.user_id = u.id
''').fetchall()
conn.close()

url = f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'

for r in rows:
    username = r['username']
    token = r['token']
    print(f'שולח ל-{username}...')

    payload = json.dumps({
        'message': {
            'token': token,
            'notification': {
                'title': '🧪 טסט התראה',
                'body': f'שלום {username}! ההתראות עובדות ✅'
            }
        }
    }).encode()

    req = urlreq.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    })
    try:
        resp = urlreq.urlopen(req, timeout=10)
        print(f'  ✅ הצלחה: {resp.read().decode()[:100]}')
    except urlreq.HTTPError as e:
        body = e.read().decode()
        print(f'  ❌ שגיאה {e.code}: {body}')
    except Exception as e:
        print(f'  ❌ שגיאה: {e}')
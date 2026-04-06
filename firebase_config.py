"""
Firebase Auth for OurHome IL — Server-Side Only
=================================================
All Firebase operations run from Flask (Python) — zero client-side JS.
No CORS issues, works from any domain.

Features:
- Create user (Admin SDK)
- Verify login (REST API)
- Send password reset email (REST API — Google sends automatically)
- Update password (Admin SDK)
"""

import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

# Web API key (public, used for REST API calls)
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', 'AIzaSyBXFTtFa5isjv79ZrtyVL7RfE-S_ofigdc')
FIREBASE_REST_URL = 'https://identitytoolkit.googleapis.com/v1'


# ──────────────────────────────────────────────
# INITIALIZATION
# ──────────────────────────────────────────────

def _init_firebase():
    if firebase_admin._apps:
        return
    cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH', 'serviceAccountKey.json')
    cred_json = os.environ.get('FIREBASE_CREDENTIALS')
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    elif os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        print("⚠️ Firebase credentials not found — Auth disabled")
        return
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Auth initialized")


_init_firebase()


# ──────────────────────────────────────────────
# REGISTER — Create user in Firebase Auth
# ──────────────────────────────────────────────

def firebase_create_user(email, password, display_name):
    """Create user in Firebase Auth.
    Returns (firebase_uid, error_message).
    """
    if not firebase_admin._apps:
        return None, None  # Firebase disabled, continue without it

    try:
        fb_user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
        )
        print(f'✅ Firebase user created: {fb_user.uid} ({email})')
        return fb_user.uid, None

    except firebase_auth.EmailAlreadyExistsError:
        return None, 'כתובת אימייל כבר רשומה'

    except Exception as e:
        print(f'⚠️ Firebase create user error: {e}')
        return None, None  # Don't block registration


# ──────────────────────────────────────────────
# LOGIN — Verify email+password via REST API
# ──────────────────────────────────────────────

def firebase_verify_login(email, password):
    """Verify email+password against Firebase Auth.
    Returns (firebase_uid, error_message).
    """
    try:
        url = f'{FIREBASE_REST_URL}/accounts:signInWithPassword?key={FIREBASE_API_KEY}'
        resp = requests.post(url, json={
            'email': email,
            'password': password,
            'returnSecureToken': True
        }, timeout=10)

        data = resp.json()

        if resp.ok:
            return data.get('localId'), None  # localId = firebase UID

        # Handle errors
        error_msg = data.get('error', {}).get('message', '')
        if error_msg in ('EMAIL_NOT_FOUND', 'INVALID_PASSWORD', 'INVALID_LOGIN_CREDENTIALS'):
            return None, 'אימייל או סיסמה שגויים'
        elif error_msg == 'USER_DISABLED':
            return None, 'החשבון הושבת'
        elif 'TOO_MANY_ATTEMPTS' in error_msg:
            return None, 'יותר מדי ניסיונות. נסה שוב מאוחר יותר'
        else:
            print(f'Firebase login error: {error_msg}')
            return None, 'שגיאה בהתחברות'

    except requests.Timeout:
        print('Firebase login timeout')
        return None, 'שגיאת חיבור — נסה שוב'

    except Exception as e:
        print(f'Firebase login error: {e}')
        return None, 'שגיאה בהתחברות'


# ──────────────────────────────────────────────
# FORGOT PASSWORD — Firebase sends email automatically
# ──────────────────────────────────────────────

def firebase_send_reset_email(email):
    """Send password reset email via Firebase.
    Google sends the email automatically — no SMTP config needed.
    Returns (success, error_message).
    """
    try:
        url = f'{FIREBASE_REST_URL}/accounts:sendOobCode?key={FIREBASE_API_KEY}'
        resp = requests.post(url, json={
            'requestType': 'PASSWORD_RESET',
            'email': email
        }, timeout=10)

        if resp.ok:
            print(f'✅ Password reset email sent to {email}')
            return True, None

        error_msg = resp.json().get('error', {}).get('message', '')
        if error_msg == 'EMAIL_NOT_FOUND':
            # Don't reveal if email exists — pretend success
            return True, None
        else:
            print(f'Firebase reset error: {error_msg}')
            return False, 'שגיאה בשליחת מייל'

    except Exception as e:
        print(f'Firebase reset error: {e}')
        return False, 'שגיאה בשליחת מייל'


# ──────────────────────────────────────────────
# CHANGE/UPDATE PASSWORD
# ──────────────────────────────────────────────

def firebase_update_password(email, new_password):
    """Update password in Firebase Auth.
    Non-blocking: if Firebase fails, local change still works.
    """
    if not firebase_admin._apps:
        return

    try:
        fb_user = firebase_auth.get_user_by_email(email)
        firebase_auth.update_user(fb_user.uid, password=new_password)
        print(f'✅ Firebase password updated for {fb_user.uid}')

    except firebase_auth.UserNotFoundError:
        print(f'ℹ️ Firebase user not found for {email} — skipping')

    except Exception as e:
        print(f'⚠️ Firebase password update error: {e}')


# ──────────────────────────────────────────────
# GET USER BY EMAIL
# ──────────────────────────────────────────────

def firebase_get_user(email):
    """Get Firebase user by email. Returns user record or None."""
    if not firebase_admin._apps:
        return None
    try:
        return firebase_auth.get_user_by_email(email)
    except:
        return None
from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('אין לך הרשאה לעמוד זה', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


def log_action(user_id, username, action, target_type, target_id, details, ip_address):
    from .db import get_db
    try:
        db = get_db()
        db.execute(
            '''INSERT INTO audit_logs
               (user_id, username, action, target_type, target_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, username, action, target_type, target_id, details, ip_address)
        )
        db.commit()
    except Exception:
        pass

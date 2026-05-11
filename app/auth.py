from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .utils import login_required, log_action

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)
        ).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            log_action(user['id'], user['username'], 'LOGIN', 'user', user['id'],
                       'Successful login', request.remote_addr)
            return redirect(url_for('main.dashboard'))

        flash('שם משתמש או סיסמה שגויים', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    if session.get('user_id'):
        log_action(session['user_id'], session['username'], 'LOGOUT', 'user',
                   session['user_id'], 'User logged out', request.remote_addr)
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()

    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        if not check_password_hash(user['password_hash'], current_pw):
            flash('הסיסמה הנוכחית שגויה', 'danger')
        elif new_pw != confirm_pw:
            flash('הסיסמאות החדשות אינן תואמות', 'danger')
        elif len(new_pw) < 6:
            flash('הסיסמה חייבת להכיל לפחות 6 תווים', 'danger')
        else:
            db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                       (generate_password_hash(new_pw), session['user_id']))
            db.commit()
            log_action(session['user_id'], session['username'], 'CHANGE_PASSWORD',
                       'user', session['user_id'], 'Password changed', request.remote_addr)
            flash('הסיסמה שונתה בהצלחה', 'success')

    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    return render_template('profile.html', user=user)

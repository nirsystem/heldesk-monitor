from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from .db import get_db
from .utils import admin_required, log_action

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@admin_required
def panel():
    db = get_db()
    stats = {
        'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'tickets': db.execute('SELECT COUNT(*) FROM tickets WHERE is_archived=0').fetchone()[0],
        'open': db.execute("SELECT COUNT(*) FROM tickets WHERE status='open' AND is_archived=0").fetchone()[0],
        'in_progress': db.execute("SELECT COUNT(*) FROM tickets WHERE status='in_progress' AND is_archived=0").fetchone()[0],
        'resolved': db.execute("SELECT COUNT(*) FROM tickets WHERE status='resolved' AND is_archived=0").fetchone()[0],
        'closed': db.execute("SELECT COUNT(*) FROM tickets WHERE status='closed' AND is_archived=0").fetchone()[0],
        'archived': db.execute('SELECT COUNT(*) FROM tickets WHERE is_archived=1').fetchone()[0],
    }
    recent_logs = db.execute(
        'SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 15'
    ).fetchall()
    all_tickets = db.execute('''
        SELECT t.*, u.username AS creator_name,
               (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
        FROM tickets t JOIN users u ON t.created_by = u.id
        WHERE t.is_archived = 0
        ORDER BY t.created_at DESC LIMIT 15
    ''').fetchall()

    return render_template('admin/panel.html', stats=stats,
                           recent_logs=recent_logs, all_tickets=all_tickets)


@admin_bp.route('/users')
@admin_required
def users():
    db = get_db()
    all_users = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')

        if not username or not password:
            flash('שם משתמש וסיסמה הם שדות חובה', 'danger')
            return render_template('admin/user_form.html')

        if len(password) < 6:
            flash('הסיסמה חייבת להכיל לפחות 6 תווים', 'danger')
            return render_template('admin/user_form.html')

        db = get_db()
        try:
            db.execute(
                'INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)',
                (username, generate_password_hash(password), email, role)
            )
            db.commit()
            log_action(session['user_id'], session['username'], 'CREATE_USER',
                       'user', None, f'Created user: {username} ({role})', request.remote_addr)
            flash(f'משתמש {username} נוצר בהצלחה', 'success')
            return redirect(url_for('admin.users'))
        except Exception:
            flash('שם המשתמש כבר קיים במערכת', 'danger')

    return render_template('admin/user_form.html')


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    if user_id == session['user_id']:
        flash('לא ניתן לנטרל את עצמך', 'danger')
        return redirect(url_for('admin.users'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        db.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
        db.commit()
        action = 'ACTIVATE_USER' if new_status else 'DEACTIVATE_USER'
        state_label = 'הופעל' if new_status else 'נוטרל'
        log_action(session['user_id'], session['username'], action, 'user', user_id,
                   f'User {user["username"]} {state_label}', request.remote_addr)
        flash(f'משתמש {user["username"]} {state_label}', 'success')

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('לא ניתן למחוק את עצמך', 'danger')
        return redirect(url_for('admin.users'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('משתמש לא נמצא', 'danger')
        return redirect(url_for('admin.users'))

    if user['role'] == 'admin':
        admin_count = db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        if admin_count <= 1:
            flash('לא ניתן למחוק את המנהל האחרון במערכת', 'danger')
            return redirect(url_for('admin.users'))

    username = user['username']
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    log_action(session['user_id'], session['username'], 'DELETE_USER',
               'user', user_id, f'Deleted user: {username}', request.remote_addr)
    flash(f'משתמש {username} נמחק בהצלחה', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/cleared')
@admin_required
def cleared_tickets():
    db = get_db()

    auto_delete_days_row = db.execute(
        "SELECT value FROM settings WHERE key='auto_delete_days'"
    ).fetchone()
    auto_delete_days = int(auto_delete_days_row['value']) if auto_delete_days_row else 0

    if auto_delete_days > 0:
        expired = db.execute(
            "SELECT id FROM tickets WHERE is_archived=1 AND archived_at IS NOT NULL "
            "AND julianday('now') - julianday(archived_at) >= ?",
            (auto_delete_days,)
        ).fetchall()
        if expired:
            ids = [r['id'] for r in expired]
            placeholders = ','.join('?' * len(ids))
            db.execute(f'DELETE FROM comments WHERE ticket_id IN ({placeholders})', ids)
            db.execute(f'DELETE FROM attachments WHERE ticket_id IN ({placeholders})', ids)
            db.execute(f'DELETE FROM tickets WHERE id IN ({placeholders})', ids)
            db.commit()
            log_action(session['user_id'], session['username'], 'AUTO_DELETE_TICKETS',
                       'ticket', None,
                       f'Auto-deleted {len(ids)} expired cleared tickets (>{auto_delete_days}d)',
                       request.remote_addr)

    tickets = db.execute('''
        SELECT t.*, u.username AS creator_name,
               (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
        FROM tickets t JOIN users u ON t.created_by = u.id
        WHERE t.is_archived = 1
        ORDER BY t.archived_at DESC
    ''').fetchall()

    return render_template('admin/cleared_tickets.html',
                           tickets=tickets,
                           auto_delete_days=auto_delete_days)


@admin_bp.route('/cleared/settings', methods=['POST'])
@admin_required
def save_cleared_settings():
    days = request.form.get('auto_delete_days', '0').strip()
    try:
        days = max(0, int(days))
    except ValueError:
        days = 0

    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('auto_delete_days', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(days),)
    )
    db.commit()
    log_action(session['user_id'], session['username'], 'UPDATE_SETTINGS',
               'settings', None,
               f'Set auto_delete_days={days}', request.remote_addr)
    if days == 0:
        flash('מחיקה אוטומטית בוטלה', 'success')
    else:
        flash(f'כרטיסים מוסלקים ימחקו אוטומטית לאחר {days} ימים', 'success')
    return redirect(url_for('admin.cleared_tickets'))


@admin_bp.route('/cleared/<int:ticket_id>/delete', methods=['POST'])
@admin_required
def delete_ticket(ticket_id):
    db = get_db()
    ticket = db.execute('SELECT * FROM tickets WHERE id=? AND is_archived=1', (ticket_id,)).fetchone()
    if not ticket:
        flash('כרטיס לא נמצא בכרטיסים המוסלקים', 'danger')
        return redirect(url_for('admin.cleared_tickets'))

    db.execute('DELETE FROM comments WHERE ticket_id=?', (ticket_id,))
    db.execute('DELETE FROM attachments WHERE ticket_id=?', (ticket_id,))
    db.execute('DELETE FROM tickets WHERE id=?', (ticket_id,))
    db.commit()
    log_action(session['user_id'], session['username'], 'DELETE_TICKET',
               'ticket', ticket_id,
               f'Deleted cleared ticket: {ticket["title"]}', request.remote_addr)
    flash(f'כרטיס #{ticket_id} נמחק לצמיתות', 'success')
    return redirect(url_for('admin.cleared_tickets'))


@admin_bp.route('/cleared/delete-all', methods=['POST'])
@admin_required
def delete_all_cleared():
    db = get_db()
    ids = [r['id'] for r in db.execute('SELECT id FROM tickets WHERE is_archived=1').fetchall()]
    if ids:
        placeholders = ','.join('?' * len(ids))
        db.execute(f'DELETE FROM comments WHERE ticket_id IN ({placeholders})', ids)
        db.execute(f'DELETE FROM attachments WHERE ticket_id IN ({placeholders})', ids)
        db.execute(f'DELETE FROM tickets WHERE id IN ({placeholders})', ids)
        db.commit()
        log_action(session['user_id'], session['username'], 'DELETE_ALL_CLEARED',
                   'ticket', None,
                   f'Bulk-deleted all {len(ids)} cleared tickets', request.remote_addr)
        flash(f'{len(ids)} כרטיסים נמחקו לצמיתות', 'success')
    else:
        flash('אין כרטיסים מוסלקים למחיקה', 'info')
    return redirect(url_for('admin.cleared_tickets'))


@admin_bp.route('/cleared/<int:ticket_id>/restore', methods=['POST'])
@admin_required
def restore_ticket(ticket_id):
    db = get_db()
    ticket = db.execute('SELECT * FROM tickets WHERE id=? AND is_archived=1', (ticket_id,)).fetchone()
    if not ticket:
        flash('כרטיס לא נמצא', 'danger')
        return redirect(url_for('admin.cleared_tickets'))

    db.execute(
        "UPDATE tickets SET is_archived=0, archived_at=NULL, status='open', "
        "updated_at=datetime('now') WHERE id=?",
        (ticket_id,)
    )
    db.commit()
    log_action(session['user_id'], session['username'], 'RESTORE_TICKET',
               'ticket', ticket_id,
               f'Restored cleared ticket: {ticket["title"]}', request.remote_addr)
    flash(f'כרטיס #{ticket_id} שוחזר בהצלחה', 'success')
    return redirect(url_for('admin.cleared_tickets'))


@admin_bp.route('/logs')
@admin_required
def logs():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    total = db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
    log_entries = db.execute(
        'SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('admin/logs.html', logs=log_entries,
                           page=page, total_pages=total_pages, total=total)

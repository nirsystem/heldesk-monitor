from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from .db import get_db
from .utils import login_required, log_action
from .s3 import upload_file, get_presigned_url

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    db = get_db()
    uid = session['user_id']
    role = session['role']

    if role == 'admin':
        total = db.execute('SELECT COUNT(*) FROM tickets WHERE is_archived=0').fetchone()[0]
        open_c = db.execute("SELECT COUNT(*) FROM tickets WHERE status='open' AND is_archived=0").fetchone()[0]
        inp = db.execute("SELECT COUNT(*) FROM tickets WHERE status='in_progress' AND is_archived=0").fetchone()[0]
        resolved = db.execute("SELECT COUNT(*) FROM tickets WHERE status='resolved' AND is_archived=0").fetchone()[0]
        recent = db.execute('''
            SELECT t.*, u.username AS creator_name,
                   (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
            FROM tickets t JOIN users u ON t.created_by = u.id
            WHERE t.is_archived = 0
            ORDER BY t.created_at DESC LIMIT 10
        ''').fetchall()
    elif role == 'technician':
        total = db.execute('SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND is_archived=0', (uid,)).fetchone()[0]
        open_c = db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND status='open' AND is_archived=0", (uid,)).fetchone()[0]
        inp = db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND status='in_progress' AND is_archived=0", (uid,)).fetchone()[0]
        resolved = db.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to=? AND status='resolved' AND is_archived=0", (uid,)).fetchone()[0]
        recent = db.execute('''
            SELECT t.*, u.username AS creator_name,
                   (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
            FROM tickets t JOIN users u ON t.created_by = u.id
            WHERE t.assigned_to = ? AND t.is_archived = 0
            ORDER BY t.created_at DESC LIMIT 10
        ''', (uid,)).fetchall()
    else:
        total = db.execute('SELECT COUNT(*) FROM tickets WHERE created_by=? AND is_archived=0', (uid,)).fetchone()[0]
        open_c = db.execute("SELECT COUNT(*) FROM tickets WHERE created_by=? AND status='open' AND is_archived=0", (uid,)).fetchone()[0]
        inp = db.execute("SELECT COUNT(*) FROM tickets WHERE created_by=? AND status='in_progress' AND is_archived=0", (uid,)).fetchone()[0]
        resolved = db.execute("SELECT COUNT(*) FROM tickets WHERE created_by=? AND status='resolved' AND is_archived=0", (uid,)).fetchone()[0]
        recent = db.execute('''
            SELECT t.*, u.username AS creator_name,
                   (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
            FROM tickets t JOIN users u ON t.created_by = u.id
            WHERE t.created_by = ? AND t.is_archived = 0
            ORDER BY t.created_at DESC LIMIT 10
        ''', (uid,)).fetchall()

    return render_template('dashboard.html',
                           total=total, open_c=open_c, inp=inp, resolved=resolved,
                           recent=recent)


@main_bp.route('/tickets')
@login_required
def tickets():
    db = get_db()
    uid = session['user_id']
    role = session['role']
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')

    query = '''
        SELECT t.*, u.username AS creator_name,
               (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
        FROM tickets t JOIN users u ON t.created_by = u.id
        WHERE t.is_archived = 0
    '''
    params = []

    if role == 'technician':
        query += ' AND t.assigned_to = ?'
        params.append(uid)
    elif role == 'user':
        query += ' AND t.created_by = ?'
        params.append(uid)

    if status_filter:
        query += ' AND t.status = ?'
        params.append(status_filter)
    if priority_filter:
        query += ' AND t.priority = ?'
        params.append(priority_filter)

    query += ' ORDER BY t.created_at DESC'
    tickets_list = db.execute(query, params).fetchall()

    return render_template('tickets/list.html', tickets=tickets_list,
                           status_filter=status_filter, priority_filter=priority_filter)


@main_bp.route('/tickets/new', methods=['GET', 'POST'])
@login_required
def new_ticket():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        category = request.form.get('category', 'general')

        if not title or not description:
            flash('כותרת ותיאור הם שדות חובה', 'danger')
            return render_template('tickets/new.html')

        db = get_db()
        cursor = db.execute(
            'INSERT INTO tickets (title, description, priority, category, created_by) VALUES (?, ?, ?, ?, ?)',
            (title, description, priority, category, session['user_id'])
        )
        ticket_id = cursor.lastrowid

        file = request.files.get('attachment')
        if file and file.filename:
            s3_key = upload_file(file, ticket_id)
            if s3_key:
                db.execute(
                    'INSERT INTO attachments (ticket_id, filename, s3_key, uploaded_by) VALUES (?, ?, ?, ?)',
                    (ticket_id, file.filename, s3_key, session['user_id'])
                )

        db.commit()
        log_action(session['user_id'], session['username'], 'CREATE_TICKET',
                   'ticket', ticket_id, f'Created ticket: {title}', request.remote_addr)
        flash('הכרטיס נפתח בהצלחה!', 'success')
        return redirect(url_for('main.ticket_detail', ticket_id=ticket_id))

    return render_template('tickets/new.html')


@main_bp.route('/tickets/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    db = get_db()
    uid = session['user_id']
    role = session['role']

    ticket = db.execute('''
        SELECT t.*, u.username AS creator_name,
               (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
        FROM tickets t JOIN users u ON t.created_by = u.id
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()

    if not ticket:
        flash('כרטיס לא נמצא', 'danger')
        return redirect(url_for('main.tickets'))

    if role == 'user' and ticket['created_by'] != uid:
        flash('אין לך הרשאה לצפות בכרטיס זה', 'danger')
        return redirect(url_for('main.tickets'))

    if role == 'technician' and ticket['assigned_to'] != uid:
        flash('אין לך הרשאה לצפות בכרטיס זה', 'danger')
        return redirect(url_for('main.tickets'))

    comments = db.execute('''
        SELECT c.*, u.username FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.ticket_id = ? ORDER BY c.created_at ASC
    ''', (ticket_id,)).fetchall()

    attachments = db.execute('''
        SELECT a.*, u.username AS uploader FROM attachments a
        JOIN users u ON a.uploaded_by = u.id
        WHERE a.ticket_id = ?
    ''', (ticket_id,)).fetchall()

    technicians = db.execute(
        "SELECT id, username FROM users WHERE role IN ('admin','technician') AND is_active=1"
    ).fetchall()

    return render_template('tickets/detail.html',
                           ticket=ticket, comments=comments,
                           attachments=attachments, technicians=technicians)


@main_bp.route('/tickets/<int:ticket_id>/update', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    db = get_db()
    uid = session['user_id']
    role = session['role']

    ticket = db.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        flash('כרטיס לא נמצא', 'danger')
        return redirect(url_for('main.tickets'))

    action = request.form.get('action')

    if action == 'comment':
        content = request.form.get('content', '').strip()
        if content:
            db.execute('INSERT INTO comments (ticket_id, user_id, content) VALUES (?, ?, ?)',
                       (ticket_id, uid, content))
            db.commit()
            log_action(uid, session['username'], 'ADD_COMMENT', 'ticket', ticket_id,
                       f'Added comment to ticket #{ticket_id}', request.remote_addr)
            flash('תגובה נוספה בהצלחה', 'success')

    elif action == 'status' and role in ('admin', 'technician'):
        new_status = request.form.get('status')
        valid = ('open', 'in_progress', 'resolved', 'closed')
        if new_status in valid:
            old_status = ticket['status']
            archive = new_status in ('resolved', 'closed')
            if archive:
                db.execute(
                    "UPDATE tickets SET status=?, updated_at=datetime('now'), "
                    "is_archived=1, archived_at=datetime('now') WHERE id=?",
                    (new_status, ticket_id)
                )
            else:
                db.execute(
                    "UPDATE tickets SET status=?, updated_at=datetime('now'), "
                    "is_archived=0, archived_at=NULL WHERE id=?",
                    (new_status, ticket_id)
                )
            db.commit()
            log_action(uid, session['username'], 'UPDATE_STATUS', 'ticket', ticket_id,
                       f'Status: {old_status} → {new_status}', request.remote_addr)
            if archive:
                flash(f'סטטוס עודכן ל-{new_status} — הכרטיס הועבר לכרטיסים המוסלקים', 'success')
            else:
                flash(f'סטטוס עודכן ל-{new_status}', 'success')

    elif action == 'assign' and role == 'admin':
        assigned_to = request.form.get('assigned_to') or None
        if assigned_to:
            assigned_to = int(assigned_to)
        db.execute("UPDATE tickets SET assigned_to=?, updated_at=datetime('now') WHERE id=?",
                   (assigned_to, ticket_id))
        db.commit()
        if assigned_to:
            assignee = db.execute('SELECT username FROM users WHERE id = ?', (assigned_to,)).fetchone()
            name = assignee['username'] if assignee else 'unknown'
        else:
            name = 'nobody'
        log_action(uid, session['username'], 'ASSIGN_TICKET', 'ticket', ticket_id,
                   f'Assigned to {name}', request.remote_addr)
        flash('הכרטיס הוקצה בהצלחה', 'success')

    elif action == 'attachment':
        file = request.files.get('attachment')
        if file and file.filename:
            s3_key = upload_file(file, ticket_id)
            if s3_key:
                db.execute(
                    'INSERT INTO attachments (ticket_id, filename, s3_key, uploaded_by) VALUES (?, ?, ?, ?)',
                    (ticket_id, file.filename, s3_key, uid)
                )
                db.commit()
                log_action(uid, session['username'], 'ADD_ATTACHMENT', 'ticket', ticket_id,
                           f'Uploaded file: {file.filename}', request.remote_addr)
                flash('הקובץ הועלה בהצלחה', 'success')
            else:
                flash('שגיאה בהעלאת הקובץ — ודא ש-S3 מוגדר', 'warning')

    return redirect(url_for('main.ticket_detail', ticket_id=ticket_id))


@main_bp.route('/tickets/<int:ticket_id>/attachment/<int:att_id>')
@login_required
def get_attachment(ticket_id, att_id):
    db = get_db()
    uid = session['user_id']
    role = session['role']

    ticket = db.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        flash('כרטיס לא נמצא', 'danger')
        return redirect(url_for('main.tickets'))

    if role == 'user' and ticket['created_by'] != uid:
        flash('אין הרשאה', 'danger')
        return redirect(url_for('main.tickets'))

    att = db.execute('SELECT * FROM attachments WHERE id = ? AND ticket_id = ?',
                     (att_id, ticket_id)).fetchone()
    if not att:
        flash('קובץ לא נמצא', 'danger')
        return redirect(url_for('main.ticket_detail', ticket_id=ticket_id))

    url = get_presigned_url(att['s3_key'])
    if url == '#':
        flash('שגיאה בגישה לקובץ — S3 לא מוגדר', 'warning')
        return redirect(url_for('main.ticket_detail', ticket_id=ticket_id))

    from flask import redirect as flask_redirect
    return flask_redirect(url)


@main_bp.route('/kanban')
@login_required
def kanban():
    db = get_db()
    uid = session['user_id']
    role = session['role']

    base = '''
        SELECT t.*, u.username AS creator_name,
               (SELECT username FROM users WHERE id = t.assigned_to) AS assignee_name
        FROM tickets t JOIN users u ON t.created_by = u.id
        WHERE t.status = ? AND t.is_archived = 0
    '''
    extra_params = []

    if role == 'technician':
        base += ' AND t.assigned_to = ?'
        extra_params = [uid]
    elif role == 'user':
        base += ' AND t.created_by = ?'
        extra_params = [uid]

    base += ' ORDER BY t.created_at DESC'

    columns = {}
    for status in ('open', 'in_progress', 'resolved', 'closed'):
        columns[status] = db.execute(base, [status] + extra_params).fetchall()

    return render_template('kanban.html', columns=columns)

import os
import uuid
import sqlite3
import cv2
import csv
from datetime import date, datetime
from scoring import calculate_complete_score
from database import update_live_integrity_score
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    flash,
    session,
    Response,
    jsonify,
    send_file
)

from database import (
    init_db,
    get_db_connection,
    log_event,
    get_candidate_by_email,
    get_candidate_by_id,
    get_admin_by_username,
    get_session_by_id,
    get_session_events,
    export_session_csv,
)
from face_monitor import FaceMonitor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = "proctorguard_internship_milestone_secret_key"

face_monitor = FaceMonitor(BASE_DIR)
from flask import send_from_directory


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def ensure_database_schema():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Session'")
        if cursor.fetchone() is None:
            conn.close()
            return

        columns = [row[1] for row in cursor.execute("PRAGMA table_info(Session)")]

        if 'face_presence_ratio' not in columns:
            cursor.execute("ALTER TABLE Session ADD COLUMN face_presence_ratio REAL DEFAULT 0.0")

        if 'risk_level' not in columns:
            cursor.execute("ALTER TABLE Session ADD COLUMN risk_level TEXT DEFAULT 'Low Risk'")

        if 'integrity_score' not in columns:
            cursor.execute("ALTER TABLE Session ADD COLUMN integrity_score REAL DEFAULT 100.0")

        if 'total_penalty' not in columns:
            cursor.execute("ALTER TABLE Session ADD COLUMN total_penalty REAL DEFAULT 0.0")

        if 'suspicious_event_count' not in columns:
            cursor.execute("ALTER TABLE Session ADD COLUMN suspicious_event_count INTEGER DEFAULT 0")

        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def calculate_weighted_integrity_score(session_id):
    conn = get_db_connection()
    session_row = conn.execute(
        "SELECT session_id, total_detected_seconds, total_session_seconds FROM Session WHERE session_id=?",
        (session_id,)
    ).fetchone()
    events = conn.execute(
        "SELECT event_type FROM EventLog WHERE session_id=?",
        (session_id,)
    ).fetchall()
    conn.close()

    if not session_row:
        return {
            "score": 100,
            "penalty": 0,
            "suspicious_event_count": 0,
            "risk_label": "Low Risk",
            "face_presence_ratio": 0,
        }

    result = calculate_complete_score(
        events,
        session_row["total_detected_seconds"] or 0,
        session_row["total_session_seconds"] or 0,
    )

    return {
        "score": result["score"],
        "penalty": result.get("penalty", result.get("total_penalty", 0)),
        "suspicious_event_count": result["suspicious_event_count"],
        "risk_label": result["risk_label"],
        "face_presence_ratio": result["face_presence_ratio"],
    }


def persist_session_score(session_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    else:
        close_conn = False

    try:
        result = calculate_weighted_integrity_score(session_id)
        conn.execute(
            """
            UPDATE Session
            SET integrity_score=?,
                total_penalty=?,
                suspicious_event_count=?,
                risk_level=?,
                face_presence_ratio=?
            WHERE session_id=?
            """,
            (
                result["score"],
                result["penalty"],
                result["suspicious_event_count"],
                result["risk_label"],
                result["face_presence_ratio"],
                session_id,
            ),
        )
        conn.commit()
        return result
    finally:
        if close_conn:
            conn.close()


def log_event_and_update_score(candidate_id, event_type, timestamp, remarks, session_id=None, screenshot_path=None):
    if session_id is None:
        session_id = session.get("active_session_id")

    log_event(
        candidate_id,
        event_type,
        timestamp,
        remarks,
        session_id=session_id,
        screenshot_path=screenshot_path,
    )

    if session_id:
        persist_session_score(session_id)


@app.route('/view_screenshot/<int:event_id>')
def view_screenshot(event_id):
    conn = get_db_connection()
    event = conn.execute(
        "SELECT screenshot_path, candidate_id FROM EventLog WHERE id=?",
        (event_id,)
    ).fetchone()
    conn.close()

    if not event:
        return "Event log not found", 404

    s_path = event["screenshot_path"]
    if not s_path:
        fallback_bytes = face_monitor.create_fallback_proctor_frame(
            event["candidate_id"] or "Candidate",
            is_warning=True
        )
        return Response(fallback_bytes, mimetype="image/jpeg")

    full_path = s_path if os.path.isabs(s_path) else os.path.join(BASE_DIR, s_path)

    if not os.path.exists(full_path):
        fallback_bytes = face_monitor.create_fallback_proctor_frame(
            event["candidate_id"] or "Candidate",
            is_warning=True
        )
        return Response(fallback_bytes, mimetype="image/jpeg")

    return send_file(full_path)


@app.before_request
def initialize_system():
    init_db()
    ensure_database_schema()

@app.route('/video_feed')
def video_feed():
    """Streaming route for HTML pages to render live webcam frames."""
    return Response(
        face_monitor.generate_frames(db_log_callback=log_event_and_update_score),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
@app.route("/api/integrity_score")
def get_integrity_score():

    if "candidate_id" not in session:
        return jsonify({"score": 100, "penalty": 0, "risk_level": "Low Risk", "face_presence_ratio": 0, "suspicious_event_count": 0})

    conn = get_db_connection()

    row = conn.execute("""
        SELECT session_id, integrity_score, total_penalty
        FROM Session
        WHERE candidate_id=?
        AND status!='Completed'
        ORDER BY start_time DESC
        LIMIT 1
    """,(session["candidate_id"],)).fetchone()

    conn.close()

    if row and row["session_id"]:
        latest = calculate_weighted_integrity_score(row["session_id"])
        return jsonify({
            "score": latest["score"],
            "penalty": latest["penalty"],
            "risk_level": latest["risk_label"],
            "face_presence_ratio": latest["face_presence_ratio"],
            "suspicious_event_count": latest["suspicious_event_count"],
        })

    return jsonify({
        "score":100,
        "penalty":0,
        "risk_level":"Low Risk",
        "face_presence_ratio":0,
        "suspicious_event_count":0,
    })
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        c_id = request.form.get('candidate_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not c_id or not name or not email or not password:
            flash("Error: All form fields are mandatory.")
            return redirect('/register')

        if get_candidate_by_email(email):
            flash("Error: An account with this email address already exists.")
            return redirect('/register')

        if get_candidate_by_id(c_id):
            flash("Error: Candidate ID already exists.")
            return redirect('/register')

        photo_path = face_monitor.capture_registration_photo(c_id)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO Candidate (candidate_id, name, email, password, photo_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (c_id, name, email, password, photo_path, now_str))
            conn.commit()
            
            log_event(c_id, 'Candidate Registered', now_str, f"Registered profile for {name} ({email}) with photo capture.")
            
            flash("Registration successful! Please log in to continue.","success")
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            flash("Error: Could not complete registration.")
            return redirect('/register')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Error: Email and password are required for candidate login.')
            return redirect('/login')

        candidate = get_candidate_by_email(email)

        if candidate and candidate['password'] == password:
            session['candidate_id'] = candidate['candidate_id']
            session['name'] = candidate['name']
            session['email'] = candidate['email']

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_event(candidate['candidate_id'], 'Candidate Login', now_str, f"Successful candidate login from email {email}")
            return redirect('/dashboard')

        flash('Error: Invalid email or password credentials.')
        return redirect('/login')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'candidate_id' not in session:
        return redirect('/login')

    candidate = get_candidate_by_id(session['candidate_id'])
    
    conn = get_db_connection()
    active_session = conn.execute(
        'SELECT * FROM Session WHERE candidate_id = ? ORDER BY start_time DESC LIMIT 1',
        (session['candidate_id'],)
    ).fetchone()
    

    events=[]

    if active_session:

        events = conn.execute("""
SELECT *
FROM EventLog
WHERE session_id = ?
ORDER BY id DESC
LIMIT 20
""", (active_session["session_id"],)).fetchall()
    conn.close()
    return render_template('dashboard.html',candidate=candidate,active_session=active_session,events=events)

@app.route("/admin")
def admin():
    if session.get('candidate_id') and not session.get('admin_logged_in'):
        flash("Access Denied: Candidates are not authorized to access Administrator Dashboard.")
        return redirect('/dashboard')
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    conn = get_db_connection()

    total_candidates = conn.execute(
        "SELECT COUNT(*) FROM Candidate"
    ).fetchone()[0]

    active_sessions = conn.execute("""
    SELECT COUNT(*)
    FROM Session
    WHERE status IN ('Ongoing', 'Paused')
""").fetchone()[0]

    completed_sessions = conn.execute(
        "SELECT COUNT(*) FROM Session WHERE status='Completed'"
    ).fetchone()[0]

    avg_score = conn.execute(
        "SELECT ROUND(AVG(integrity_score),1) FROM Session"
    ).fetchone()[0] or 0

    total_events = conn.execute(
        "SELECT COUNT(*) FROM EventLog"
    ).fetchone()[0]

    suspicious_events = conn.execute(
        "SELECT COUNT(*) FROM EventLog WHERE event_type IN ('Face Not Detected', 'Browser Focus Lost', 'Browser Tab Switch', 'Multiple Faces Detected')"
    ).fetchone()[0]

    face_events = conn.execute(
        "SELECT COUNT(*) FROM EventLog WHERE event_type='Face Not Detected'"
    ).fetchone()[0]

    browser_events = conn.execute(
        "SELECT COUNT(*) FROM EventLog WHERE event_type='Browser Focus Lost'"
    ).fetchone()[0]

    highest_score = conn.execute(
        "SELECT MAX(integrity_score) FROM Session"
    ).fetchone()[0] or 0

    lowest_score = conn.execute(
        "SELECT MIN(integrity_score) FROM Session"
    ).fetchone()[0] or 0

    avg_face_presence_ratio = conn.execute(
        "SELECT ROUND(AVG(face_presence_ratio), 2) FROM Session"
    ).fetchone()[0] or 0

    attended_candidates = conn.execute(
        "SELECT COUNT(DISTINCT candidate_id) FROM Session WHERE status IN ('Completed', 'Ongoing')"
    ).fetchone()[0] or 0

    above_score_count = conn.execute(
        "SELECT COUNT(*) FROM Session WHERE integrity_score >= 70"
    ).fetchone()[0] or 0

    below_score_count = conn.execute(
        "SELECT COUNT(*) FROM Session WHERE integrity_score < 70"
    ).fetchone()[0] or 0

    face_detection_accuracy = conn.execute(
        "SELECT ROUND(AVG(face_presence_ratio), 1) FROM Session"
    ).fetchone()[0] or 100.0

    tab_events = conn.execute(
        "SELECT COUNT(*) FROM EventLog WHERE event_type='Browser Tab Switch'"
    ).fetchone()[0] or 0

    multi_face_events = conn.execute(
        "SELECT COUNT(*) FROM EventLog WHERE event_type='Multiple Faces Detected'"
    ).fetchone()[0] or 0

    high_integrity_candidates = conn.execute('''
        SELECT 
            s.session_id,
            s.candidate_id,
            c.name as candidate_name,
            c.email as candidate_email,
            s.start_time,
            s.end_time,
            s.integrity_score,
            s.face_presence_ratio,
            s.suspicious_event_count,
            s.risk_level,
            s.status
        FROM Session s
        JOIN Candidate c ON s.candidate_id = c.candidate_id
        WHERE s.integrity_score >= 70
        ORDER BY s.integrity_score DESC, s.start_time DESC
    ''').fetchall()

    low_integrity_candidates = conn.execute('''
        SELECT 
            s.session_id,
            s.candidate_id,
            c.name as candidate_name,
            c.email as candidate_email,
            s.start_time,
            s.end_time,
            s.integrity_score,
            s.face_presence_ratio,
            s.suspicious_event_count,
            s.risk_level,
            s.status
        FROM Session s
        JOIN Candidate c ON s.candidate_id = c.candidate_id
        WHERE s.integrity_score < 70
        ORDER BY s.integrity_score ASC, s.start_time DESC
    ''').fetchall()

    candidate_id = request.args.get("candidate_id", "")
    event_type = request.args.get("event_type", "")
    date = request.args.get("date", "")

    query = "SELECT * FROM EventLog WHERE 1=1"
    params = []

    if candidate_id:
        query += " AND candidate_id=?"
        params.append(candidate_id)

    if event_type:
        query += " AND event_type=?"
        params.append(event_type)

    if date:
        query += " AND date(timestamp)=?"
        params.append(date)

    query += " ORDER BY id DESC"

    events = conn.execute(query, params).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_candidates=total_candidates,
        attended_candidates=attended_candidates,
        active_sessions=active_sessions,
        completed_sessions=completed_sessions,
        avg_score=avg_score,
        above_score_count=above_score_count,
        below_score_count=below_score_count,
        face_detection_accuracy=face_detection_accuracy,
        total_events=total_events,
        suspicious_events=suspicious_events,
        face_events=face_events,
        browser_events=browser_events,
        tab_events=tab_events,
        multi_face_events=multi_face_events,
        highest_score=highest_score,
        lowest_score=lowest_score,
        avg_face_presence_ratio=avg_face_presence_ratio,
        high_integrity_candidates=high_integrity_candidates,
        low_integrity_candidates=low_integrity_candidates,
        events=events
    )
@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not name or not email or not password:
            flash("Error: All fields are required for administrator registration.")
            return redirect('/admin/register')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO Admin (username, password, email, name, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password, email, name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            flash("Administrator profile registered successfully! Please log in below.", "success")
            return redirect('/admin/login')
        except sqlite3.IntegrityError:
            conn.close()
            flash("Error: Administrator username or email already exists.")
            return redirect('/admin/register')

    return render_template('admin_register.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('candidate_id') and not session.get('admin_logged_in'):
        flash("Access Denied: Candidate accounts cannot access Administrator Login.")
        return redirect('/dashboard')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Error: Username and password are required for administrator login.")
            return redirect('/admin/login')

        admin = get_admin_by_username(username)
        if admin and admin['password'] == password:
            session['admin_logged_in'] = True
            session['admin_username'] = admin['username']
            flash("Administrator login successful.", "success")
            return redirect('/admin')

        flash("Invalid admin username or password.")

    return render_template('admin_login.html')
@app.route('/admin/logout')
def admin_logout():

    session.pop('admin_logged_in', None)

    return redirect('/admin/login')
@app.route("/event_logs")
def event_logs():
    conn = get_db_connection()

    candidate_id = request.args.get("candidate_id", "")
    event_type = request.args.get("event_type", "")
    date = request.args.get("date", "")

    query = "SELECT * FROM EventLog WHERE 1=1"
    values = []

    if candidate_id:
        query += " AND candidate_id=?"
        values.append(candidate_id)

    if event_type:
        query += " AND event_type=?"
        values.append(event_type)

    if date:
        query += " AND DATE(timestamp)=?"
        values.append(date)

    query += " ORDER BY timestamp DESC"

    events = conn.execute(query, values).fetchall()

    conn.close()

    return render_template(
        "event_logs.html",
        events=events
    )
@app.route('/exam')
def exam():
    if 'candidate_id' not in session:
        return redirect('/login')

    candidate = get_candidate_by_id(session['candidate_id'])
    return render_template('exam.html', candidate=candidate)

@app.route('/api/monitoring_status')
def monitoring_status():
    status_data = face_monitor.get_current_status()
    return jsonify(status_data)
@app.route('/api/live_score')
def live_score():

    if 'active_session_id' not in session:
        return jsonify({"score": 100, "penalty": 0, "risk_level": "Low Risk", "face_presence_ratio": 0, "suspicious_event_count": 0, "browser_focus_lost_count": 0})

    session_id = session['active_session_id']
    result = calculate_weighted_integrity_score(session_id)

    conn = get_db_connection()
    session_row = conn.execute(
        "SELECT browser_focus_lost_count FROM Session WHERE session_id = ?",
        (session_id,)
    ).fetchone()
    conn.close()

    return jsonify({
        "score": result["score"],
        "penalty": result["penalty"],
        "risk_level": result["risk_label"],
        "face_presence_ratio": result["face_presence_ratio"],
        "suspicious_event_count": result["suspicious_event_count"],
        "browser_focus_lost_count": session_row["browser_focus_lost_count"] if session_row else 0,
    })
@app.route('/api/log_event', methods=['POST'])
def api_log_event():

    if 'candidate_id' not in session:
        return jsonify({'status': 'error'}), 401

    data = request.get_json() or {}

    event_type = data.get("event_type")
    remarks = data.get("remarks", "")

    if not event_type:
        return jsonify({
            "status": "error",
            "message": "event_type is required"
        }), 400

    candidate_id = session["candidate_id"]
    session_id = session.get("active_session_id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    screenshot_path = None

    if event_type == "Browser Focus Lost":
        screenshot_path = face_monitor.capture_browser_screenshot()

    log_event_and_update_score(
        candidate_id,
        event_type,
        now,
        remarks,
        session_id=session_id,
        screenshot_path=screenshot_path
    )

    return jsonify({
        "status": "success"
    })
@app.route('/update_session/<action>')
def update_session(action):
    if 'candidate_id' not in session:
        return redirect('/login')

    c_id = session['candidate_id']
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    cursor = conn.cursor()

    existing = cursor.execute(
        'SELECT * FROM Session WHERE candidate_id = ? ORDER BY start_time DESC LIMIT 1', (c_id,)
    ).fetchone()

    if action == 'start':
        s_id = str(uuid.uuid4())[:8]
        session['active_session_id'] = s_id
        cursor.execute(
            'INSERT INTO Session(session_id,candidate_id,start_time,status,face_absent_count,browser_focus_lost_count,tab_switch_count,multiple_face_count,suspicious_event_count,integrity_score,total_penalty)VALUES(?,?,?,?,0,0,0,0,0,100,0)',(s_id, c_id, now_str, 'Ongoing'))
        conn.commit()
        face_monitor.start_monitoring_session(s_id, c_id)
        log_event(c_id, 'Exam Session Started', now_str, 'Candidate initiated proctored exam session.', session_id=s_id)
        flash("Exam session started successfully.")
        conn.close()
        return redirect('/exam')

    elif action == 'pause' and existing:
        s_id = existing['session_id']
        cursor.execute('UPDATE Session SET status = ? WHERE session_id = ?', ('Paused', s_id))
        conn.commit()
        log_event(c_id, 'Exam Session Paused', now_str, 'Candidate toggled session state to Paused.', session_id=s_id)
        flash("Exam session toggled to Paused.")
        conn.close()
        return redirect('/dashboard')

    elif action == 'resume' and existing:
        s_id = existing['session_id']
        cursor.execute('UPDATE Session SET status = ? WHERE session_id = ?', ('Ongoing', s_id))
        conn.commit()
        log_event(c_id, 'Exam Session Resumed', now_str, 'Candidate toggled session state back to Ongoing.', session_id=s_id)
        flash("Exam session toggled to Resumed (Ongoing).")
        conn.close()
        return redirect('/exam')

    elif action == 'end' and existing:

        s_id = existing['session_id']

        metrics = face_monitor.stop_monitoring_session()

        cursor.execute("""
        UPDATE Session
        SET status=?,
            end_time=?,
            face_absent_count=?,
            total_detected_seconds=?,
            total_session_seconds=?
        WHERE session_id=?
    """, (
        'Completed',
        now_str,
        metrics['absence_count'],
        metrics['total_detected_seconds'],
        metrics['total_session_seconds'],
        s_id
    ))

        conn.commit()

        result = persist_session_score(s_id, conn=conn)
        score = result["score"]
        penalty = result["penalty"]
        risk = result["risk_label"]

        log_event(
            c_id,
            "Integrity Score Calculated",
            now_str,
            f"Score={score}, Penalty={penalty}, Risk={risk}",
            session_id=s_id
        )

        log_event(
            c_id,
            "Exam Session Submitted",
            now_str,
            f"Integrity Score={score}",
            session_id=s_id
        )

        flash("Exam completed successfully.")
        session.pop('active_session_id', None)

        conn.close()

        return redirect(f"/session_summary/{s_id}")


@app.route('/session_summary/<session_id>')
def session_summary(session_id):
    if 'candidate_id' not in session:
        return redirect('/login')

    candidate = get_candidate_by_id(session['candidate_id'])
    session_data = get_session_by_id(session_id)
    if session_data is None:
        session_data = {}
    else:
        session_data = dict(session_data)

    scoring = calculate_weighted_integrity_score(session_id)
    session_data.update({
        "integrity_score": scoring["score"],
        "total_penalty": scoring["penalty"],
        "risk_level": scoring["risk_label"],
        "face_presence_ratio": scoring["face_presence_ratio"],
        "suspicious_event_count": scoring["suspicious_event_count"],
    })
    events = get_session_events(session_id)
    return render_template('summary.html', candidate=candidate, session_data=session_data, events=events)

@app.route('/export_csv/<session_id>')
def export_csv(session_id):
    if not session.get('admin_logged_in'):
        if 'candidate_id' not in session:
            flash("Error: Please log in to download event log CSV report.")
            return redirect('/login')

        conn = get_db_connection()
        session_row = conn.execute(
            "SELECT candidate_id FROM Session WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        conn.close()

        if not session_row or session_row['candidate_id'] != session['candidate_id']:
            flash("Access Denied: You can only download CSV reports for your own exam sessions.")
            return redirect('/dashboard')

    filename = f"proctor_log_{session_id}.csv"
    filepath = os.path.join(BASE_DIR, filename)

    success = export_session_csv(session_id, filepath)
    if success:
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        flash("Error generating CSV export file.")
        return redirect('/dashboard' if 'candidate_id' in session else '/admin')


@app.route('/export_event_logs_csv')
def export_event_logs_csv():
    if not session.get('admin_logged_in') and 'candidate_id' not in session:
        flash("Error: Please log in to download event log CSV report.")
        return redirect('/login')

    conn = get_db_connection()
    c_id = session.get('candidate_id')

    if session.get('admin_logged_in'):
        events = conn.execute("SELECT * FROM EventLog ORDER BY id DESC").fetchall()
        filename = "all_proctor_event_logs.csv"
    else:
        events = conn.execute("SELECT * FROM EventLog WHERE candidate_id = ? ORDER BY id DESC", (c_id,)).fetchall()
        filename = f"event_logs_{c_id}.csv"

    conn.close()

    filepath = os.path.join(BASE_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['Log ID', 'Candidate ID', 'Session ID', 'Event Type', 'Penalty', 'Timestamp', 'Remarks', 'Screenshot Path'])
        for e in events:
            writer.writerow([
                e['id'],
                e['candidate_id'],
                e['session_id'] or '',
                e['event_type'],
                e['penalty'],
                e['timestamp'],
                e['remarks'],
                e['screenshot_path'] or ''
            ])

    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    print("Starting Integrated Proctoring Flask Application on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)

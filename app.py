import os
import uuid
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, flash, session, Response, jsonify, send_file

from database import (
    init_db, get_db_connection, log_event, 
    get_candidate_by_email, get_candidate_by_id, 
    get_session_by_id, get_session_events, export_session_csv
)
from face_monitor import FaceMonitor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = "proctorguard_internship_milestone_secret_key"

face_monitor = FaceMonitor(BASE_DIR)
def calculate_integrity_score(session_id, metrics):
    """
    Calculates Integrity Score based on session statistics.
    """

    conn = get_db_connection()

    row = conn.execute("""
        SELECT face_absent_count,
       browser_focus_lost_count,
       tab_switch_count,
       multiple_face_count
        FROM Session
        WHERE session_id=?
    """, (session_id,)).fetchone()

    conn.close()

    score = 100
    penalty = 0

    face_absent = row["face_absent_count"]
    browser_lost = row["browser_focus_lost_count"]
    tab_switch = row["tab_switch_count"]
    multiple_face = row["multiple_face_count"]

    total_session = metrics["total_session_seconds"]
    detected = metrics["total_detected_seconds"]

    face_absence_duration = max(0, total_session - detected)

    penalty += face_absent * 5
    penalty += browser_lost * 10
    penalty += tab_switch * 10
    penalty += multiple_face * 15
    if face_absence_duration > 10:
        penalty += 5

    if face_absence_duration > 30:
        penalty += 10

    # --------------------
    # Rule 4
    # --------------------
    if face_absent >= 5:
        penalty += 5

    # --------------------
    # Rule 5
    # --------------------
    if browser_lost >= 5:
        penalty += 10

    score = max(0, 100 - penalty)

    if score >= 90:
        risk = "Excellent"

    elif score >= 75:
        risk = "Good"

    elif score >= 50:
        risk = "Suspicious"

    elif score >= 25:
        risk = "High Risk"

    else:
        risk = "Very High Risk"

    return score, penalty, risk

@app.before_request
def initialize_system():
    init_db()

@app.route('/video_feed')
def video_feed():
    """Streaming route for HTML pages to render live webcam frames."""
    return Response(
        face_monitor.generate_frames(db_log_callback=log_event), 
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/')
def index():
    if 'candidate_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

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
            
            flash("Registration successful! Please log in to continue.")
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

        candidate = get_candidate_by_email(email)

        if candidate and candidate['password'] == password:
            session['candidate_id'] = candidate['candidate_id']
            session['name'] = candidate['name']
            session['email'] = candidate['email']

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_event(candidate['candidate_id'], 'Candidate Login', now_str, f"Successful candidate login from email {email}")
            
            return redirect('/dashboard')
        else:
            flash("Error: Invalid email or password credentials.")
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

    return render_template('dashboard.html',candidate=candidate,active_session=active_session,events=events)


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

@app.route('/api/log_event', methods=['POST'])
def api_log_event():
    if 'candidate_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.get_json() or {}
    event_type = data.get('event_type', 'JS Event')
    remarks = data.get('remarks', '')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c_id = session['candidate_id']
    s_id = session.get('active_session_id')

    log_event(c_id, event_type, now_str, remarks, session_id=s_id)
    
    if event_type == 'Browser Focus Lost' and s_id:
        conn = get_db_connection()
        if s_id:

            conn = get_db_connection()

    if event_type == "Browser Focus Lost":

        conn.execute("""
        UPDATE Session
        SET browser_focus_lost_count =
        browser_focus_lost_count + 1
        WHERE session_id=?
        """,(s_id,))

    elif event_type == "Browser Tab Switch":

        conn.execute("""
        UPDATE Session
        SET tab_switch_count =
        tab_switch_count + 1
        WHERE session_id=?
        """,(s_id,))

    elif event_type == "Multiple Face Detected":

        conn.execute("""
        UPDATE Session
        SET multiple_face_count =
        multiple_face_count + 1
        WHERE session_id=?
        """,(s_id,))

    elif event_type == "Face Not Detected":

        conn.execute("""
        UPDATE Session
        SET face_absent_count =
        face_absent_count + 1
        WHERE session_id=?
        """,(s_id,))

        conn.execute("""
        UPDATE Session SET suspicious_event_count =face_absent_count +browser_focus_lost_count +tab_switch_count +multiple_face_countWHERE session_id=?""",(s_id,))

        conn.commit()
        conn.close()

    return jsonify({'status': 'success'})

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

    # -------------------------
    # Calculate Integrity Score
    # -------------------------

    score, penalty, risk = calculate_integrity_score(s_id, metrics)
    cursor.execute("""
SELECT
    face_absent_count,
    browser_focus_lost_count,
    tab_switch_count,
    multiple_face_count
FROM Session
WHERE session_id = ?
""", (s_id,))

    row=  cursor.fetchone()

    suspicious=row["face_absent_count"] + \
           row["browser_focus_lost_count"] + \
           row["tab_switch_count"] + \
           row["multiple_face_count"]

    cursor.execute("""
        UPDATE Session
        SET integrity_score=?,
            total_penalty=?,
            suspicious_event_count=?,
            risk_level=?
        WHERE session_id=?
    """, (
        score,
        penalty,
        suspicious,
        risk,
        s_id
    ))

    conn.commit()

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

    conn.close()

    return redirect(f"/session_summary/{s_id}")


@app.route('/session_summary/<session_id>')
def session_summary(session_id):
    if 'candidate_id' not in session:
        return redirect('/login')

    candidate = get_candidate_by_id(session['candidate_id'])
    session_data = get_session_by_id(session_id)
    events = get_session_events(session_id)
    print(candidate)
    print(session_data)
    return render_template('summary.html', candidate=candidate, session_data=session_data, events=events)

@app.route('/export_csv/<session_id>')
def export_csv(session_id):
    if 'candidate_id' not in session:
        return redirect('/login')

    filename = f"proctor_log_{session_id}.csv"
    filepath = os.path.join(BASE_DIR, filename)
    
    success = export_session_csv(session_id, filepath)
    if success:
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        flash("Error generating CSV export file.")
        return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    print("Starting Integrated Proctoring Flask Application on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)

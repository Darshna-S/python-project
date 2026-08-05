import sqlite3
import os
import csv
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

def get_db_connection():
    """Returns a SQLite database connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the required database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Candidate Registration Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Candidate (
            candidate_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            photo_path TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    # 2. Exam Session Tracking Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Session (
            session_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,

            face_absent_count INTEGER DEFAULT 0,
            browser_focus_lost_count INTEGER DEFAULT 0,
            tab_switch_count INTEGER DEFAULT 0,
            multiple_face_count INTEGER DEFAULT 0,
            suspicious_event_count INTEGER DEFAULT 0,
            penalty INTEGER DEFAULT 0,

            total_detected_seconds REAL DEFAULT 0.0,
            total_session_seconds REAL DEFAULT 0.0,

            integrity_score INTEGER DEFAULT 100,
            total_penalty INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'Excellent',

            FOREIGN KEY (candidate_id)
            REFERENCES Candidate(candidate_id)
        )
    ''')
            
    
    # 3. Event Logging Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS EventLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            candidate_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,

            penalty INTEGER DEFAULT 0,

            remarks TEXT,
            screenshot_path TEXT,

            FOREIGN KEY(candidate_id)
            REFERENCES Candidate(candidate_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def log_event(candidate_id,event_type,timestamp,remarks,session_id=None,screenshot_path=None):

    penalty = 0

    if event_type == "Face Not Detected":
        penalty = 5

    elif event_type == "Browser Focus Lost":
        penalty = 10

    elif event_type == "Browser Tab Switch":
        penalty = 10

    elif event_type == "Multiple Faces Detected":
        penalty = 15

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        INSERT INTO EventLog (session_id, candidate_id, event_type, timestamp, penalty, remarks, screenshot_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (session_id, candidate_id, event_type, timestamp, penalty, remarks, screenshot_path)
    )
    if session_id:

        if event_type == "Face Not Detected":
            cursor.execute("""
                UPDATE Session
                SET face_absent_count = face_absent_count + 1
                WHERE session_id=?
            """, (session_id,))

        elif event_type == "Browser Focus Lost":
            cursor.execute("""
                UPDATE Session
                SET browser_focus_lost_count = browser_focus_lost_count + 1
                WHERE session_id=?
            """, (session_id,))

        elif event_type == "Browser Tab Switch":
            cursor.execute("""
                UPDATE Session
                SET tab_switch_count = tab_switch_count + 1
                WHERE session_id=?
            """, (session_id,))

        elif event_type == "Multiple Faces Detected":
            cursor.execute("""
                UPDATE Session
                SET multiple_face_count = multiple_face_count + 1
                WHERE session_id=?
            """, (session_id,))

    conn.commit()
    conn.close()
def update_live_integrity_score(session_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    session = cursor.execute("""
        SELECT *
        FROM Session
        WHERE session_id=?
    """, (session_id,)).fetchone()

    if not session:
        conn.close()
        return

    penalty = (
        session["face_absent_count"] * 5 +
        session["browser_focus_lost_count"] * 10 +
        session["tab_switch_count"] * 10 +
        session["multiple_face_count"] * 15
    )

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

    suspicious = (
        session["face_absent_count"] +
        session["browser_focus_lost_count"] +
        session["tab_switch_count"] +
        session["multiple_face_count"]
    )

    cursor.execute("""
        UPDATE Session
        SET integrity_score=?,
            total_penalty=?,
            suspicious_event_count=?,
            risk_level=?
        WHERE session_id=?
    """,
    (
        score,
        penalty,
        suspicious,
        risk,
        session_id
    ))
    # Save updates
    conn.commit()
    conn.close()
    

def get_candidate_by_email(email):
    """Fetches candidate record by email."""
    conn = get_db_connection()
    candidate = conn.execute('SELECT * FROM Candidate WHERE email = ?', (email,)).fetchone()
    conn.close()
    return candidate

def get_candidate_by_id(candidate_id):
    """Fetches candidate record by candidate_id."""
    conn = get_db_connection()
    candidate = conn.execute('SELECT * FROM Candidate WHERE candidate_id = ?', (candidate_id,)).fetchone()
    conn.close()
    return candidate

def get_session_by_id(session_id):
    """Fetches exam session record by session_id."""
    conn = get_db_connection()
    session_data = conn.execute('SELECT * FROM Session WHERE session_id = ?', (session_id,)).fetchone()
    conn.close()
    return session_data

def get_session_events(session_id):
    """Fetches all events logged for a specific session."""
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM EventLog WHERE session_id = ? ORDER BY id ASC', (session_id,)).fetchall()
    conn.close()
    return events

def export_session_csv(session_id, output_filepath):
    """Generates a CSV report containing Candidate Profile, Session Summary, and Event Logs."""
    conn = get_db_connection()
    session_data = conn.execute('''
        SELECT s.*, c.name, c.email, c.photo_path 
        FROM Session s
        JOIN Candidate c ON s.candidate_id = c.candidate_id
        WHERE s.session_id = ?
    ''', (session_id,)).fetchone()
    
    events = conn.execute('''
        SELECT * FROM EventLog WHERE session_id = ? ORDER BY id ASC
    ''', (session_id,)).fetchall()
    
    conn.close()
    
    if not session_data:
        return False
        
    with open(output_filepath, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        
        # Header Section: Session & Candidate Metadata
        writer.writerow(['=========================================='])
        writer.writerow(['AUTOMATED PROCTORING SESSION LOG REPORT'])
        writer.writerow(['=========================================='])
        writer.writerow(['Report Generated At', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        writer.writerow(['CANDIDATE DETAILS'])
        writer.writerow(['Candidate ID', session_data['candidate_id']])
        writer.writerow(['Full Name', session_data['name']])
        writer.writerow(['Email Address', session_data['email']])
        writer.writerow(['Registration Photo Path', session_data['photo_path']])
        writer.writerow([])
        writer.writerow(['SESSION METRICS SUMMARY'])
        writer.writerow(['Session ID', session_data['session_id']])
        writer.writerow(['Start Time', session_data['start_time']])
        writer.writerow(['End Time', session_data['end_time'] or 'N/A'])
        writer.writerow(['Status', session_data['status']])
        writer.writerow(['Total Face Absent Count', session_data['face_absent_count']])
        writer.writerow(['Total Browser Focus Lost Count', session_data['browser_focus_lost_count']])
        writer.writerow(['Total Tab Switch Count',session_data['tab_switch_count']])
        writer.writerow(['Multiple Face Count',session_data['multiple_face_count']])      
        writer.writerow(['Suspicious Event Count',session_data['suspicious_event_count']])
        writer.writerow(['Face Detected Time (Seconds)', f"{session_data['total_detected_seconds']:.1f}"])
        writer.writerow(['Total Session Time (Seconds)', f"{session_data['total_session_seconds']:.1f}"])
        writer.writerow(['Integrity Score', session_data['integrity_score']])
        writer.writerow(['Total Penalty', session_data['total_penalty']])
        writer.writerow(['Risk Level', session_data['risk_level']])
        writer.writerow([])
        writer.writerow(['EVENT LOG CHRONOLOGY'])
        writer.writerow([
    'Log ID',
    'Candidate ID',
    'Session ID',
    'Event Type',
    'Penalty',
    'Timestamp',
    'Remarks',
    'Screenshot Path'
])
        
        for event in events:
            writer.writerow([
    event['id'],
    event['candidate_id'],
    event['session_id'] or '',
    event['event_type'],
    event['penalty'],
    event['timestamp'],
    event['remarks'],
    event['screenshot_path'] or ''
])
    return True
def get_admin_dashboard_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    total_candidates = cursor.execute(
        "SELECT COUNT(*) FROM Candidate"
    ).fetchone()[0]

    active_sessions = cursor.execute("""
        SELECT COUNT(*)
        FROM Session
        WHERE status IN ('Ongoing','Paused')
    """).fetchone()[0]

    completed_sessions = cursor.execute(
        "SELECT COUNT(*) FROM Session WHERE status='Completed'"
    ).fetchone()[0]

    avg_integrity = cursor.execute(
        "SELECT ROUND(AVG(integrity_score),2) FROM Session"
    ).fetchone()[0]

    if avg_integrity is None:
        avg_integrity = 0

    suspicious_events = cursor.execute(
        "SELECT COUNT(*) FROM EventLog WHERE penalty > 0"
    ).fetchone()[0]

    conn.close()

    return {
        "total_candidates": total_candidates,
        "active_sessions": active_sessions,
        "completed_sessions": completed_sessions,
        "avg_score": avg_integrity,
        "total_events": suspicious_events
    }
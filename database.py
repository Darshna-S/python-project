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
            total_detected_seconds REAL DEFAULT 0.0,
            total_session_seconds REAL DEFAULT 0.0,
            FOREIGN KEY (candidate_id) REFERENCES Candidate (candidate_id)
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
            remarks TEXT,
            FOREIGN KEY (candidate_id) REFERENCES Candidate (candidate_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def log_event(candidate_id, event_type, timestamp, remarks, session_id=None):
    """Inserts a proctoring or workflow event record into SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO EventLog (session_id, candidate_id, event_type, timestamp, remarks)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, candidate_id, event_type, timestamp, remarks))
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
        writer.writerow(['Face Detected Time (Seconds)', f"{session_data['total_detected_seconds']:.1f}"])
        writer.writerow(['Total Session Time (Seconds)', f"{session_data['total_session_seconds']:.1f}"])
        writer.writerow([])
        writer.writerow(['EVENT LOG CHRONOLOGY'])
        writer.writerow(['Log ID', 'Candidate ID', 'Session ID', 'Event Type', 'Timestamp', 'Remarks'])
        
        for event in events:
            writer.writerow([
                event['id'],
                event['candidate_id'],
                event['session_id'] or '',
                event['event_type'],
                event['timestamp'],
                event['remarks']
            ])
            
    return True
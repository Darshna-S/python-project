import os
import sqlite3
import re
import uuid
from datetime import datetime
import cv2
from flask import Flask, render_template, request, redirect, flash, session, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=BASE_DIR)
app.secret_key = "super_secret_internship_key"

# Ensure the photos directory exists
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'photos')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DATABASE = os.path.join(BASE_DIR, 'database.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Candidate (
            candidate_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            photo_path TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Session (
            session_id TEXT PRIMARY KEY,
            candidate_id TEXT,
            start_time TEXT,
            end_time TEXT,
            status TEXT,
            FOREIGN KEY (candidate_id) REFERENCES Candidate (candidate_id)
        )
    ''')
    # Target Assignment Component: Event Log Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_logs (
            event_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            remarks TEXT,
            FOREIGN KEY (candidate_id) REFERENCES Candidate (candidate_id)
        )
    ''')
    conn.commit()
    conn.close()

# OpenCV Video Stream Generator
def gen_frames():
    camera = cv2.VideoCapture(0)  # Open system webcam
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode frame to JPEG format to push over HTTP
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    camera.release()

@app.route('/video_feed')
def video_feed():
    """Live streaming route for the HTML page to read webcam frames."""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    if 'candidate_id' in session:
        return redirect('/dashboard')
    return redirect('/register')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        c_id = request.form.get('candidate_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not c_id or not name or not email or not password:
            flash("Error: All fields are mandatory.")
            return redirect('/register')

        # Check for Duplicate Email
        conn = get_db_connection()
        cursor = conn.cursor()
        if cursor.execute('SELECT email FROM Candidate WHERE email = ?', (email,)).fetchone():
            conn.close()
            flash("Error: This email address is already registered.")
            return redirect('/register')

        # OpenCV Image Capture: Grab a single frame right at form submission
        camera = cv2.VideoCapture(0)
        success, frame = camera.read()
        photo_path = ""
        if success:
            filename = f"{c_id}_{int(datetime.now().timestamp())}.jpg"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            cv2.imwrite(photo_path, frame)  # Save image file locally
        camera.release()

        try:
            cursor.execute('''
                INSERT INTO Candidate (candidate_id, name, email, password, photo_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (c_id, name, email, password, photo_path))
            conn.commit()
            flash("Registration & OpenCV Photo Capture Successful! Please login.")
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            flash("Error: Candidate ID already exists.")
            return redirect('/register')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Candidate WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            session['candidate_id'] = user['candidate_id']
            session['name'] = user['name']
            session['email'] = user['email']
            return redirect('/dashboard')
        else:
            flash("Error: Invalid credentials.")
            return redirect('/login')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'candidate_id' not in session:
        return redirect('/login')
        
    # Look up the current active exam session status for this specific candidate
    conn = get_db_connection()
    current_session = conn.execute(
        'SELECT * FROM Session WHERE candidate_id = ? ORDER BY start_time DESC LIMIT 1', 
        (session['candidate_id'],)
    ).fetchone()
    conn.close()
    
    current_status = current_session['status'] if current_session else "Not Started"
    return render_template('dashboard.html', name=session['name'], email=session['email'], status=current_status)

@app.route('/update_session/<action>')
def update_session(action):
    if 'candidate_id' not in session:
        return redirect('/login')
        
    c_id = session['candidate_id']
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Locate any existing tracking record
    existing = cursor.execute(
        'SELECT * FROM Session WHERE candidate_id = ? ORDER BY start_time DESC LIMIT 1', (c_id,)
    ).fetchone()

    if action == 'start':
        s_id = str(uuid.uuid4())[:8] # Generate simple clean session ID hash
        cursor.execute('INSERT INTO Session (session_id, candidate_id, start_time, status) VALUES (?, ?, ?, ?)', 
                       (s_id, c_id, now_str, 'Ongoing'))
        
        # Insert Event Log
        evt_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO event_logs (event_id, candidate_id, event_type, timestamp, remarks) VALUES (?, ?, ?, ?, ?)',
                       (evt_id, c_id, 'Exam Started', now_str, 'The candidate initiated the testing environment session.'))
        flash("Exam session started successfully.")
        
    elif action == 'pause' and existing:
        cursor.execute('UPDATE Session SET status = ? WHERE session_id = ?', ('Paused', existing['session_id']))
        
        # Insert Event Log
        evt_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO event_logs (event_id, candidate_id, event_type, timestamp, remarks) VALUES (?, ?, ?, ?, ?)',
                       (evt_id, c_id, 'Exam Paused', now_str, 'The assessment dashboard state tracker was paused.'))
        flash("Exam session paused.")
        
    elif action == 'resume' and existing:
        cursor.execute('UPDATE Session SET status = ? WHERE session_id = ?', ('Ongoing', existing['session_id']))
        
        # Insert Event Log
        evt_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO event_logs (event_id, candidate_id, event_type, timestamp, remarks) VALUES (?, ?, ?, ?, ?)',
                       (evt_id, c_id, 'Exam Resumed', now_str, 'The candidate returned and re-engaged the exam framework.'))
        flash("Exam session resumed.")
        
    elif action == 'end' and existing:
        cursor.execute('UPDATE Session SET status = ?, end_time = ? WHERE session_id = ?', ('Completed', now_str, existing['session_id']))
        
        # Insert Event Log
        evt_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO event_logs (event_id, candidate_id, event_type, timestamp, remarks) VALUES (?, ?, ?, ?, ?)',
                       (evt_id, c_id, 'Exam Submitted', now_str, 'Session systematically concluded and committed.'))
        flash("Exam session completed and saved.")

    conn.commit()
    conn.close()
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)

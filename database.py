import sqlite3

DB_NAME = "face_monitor.db"

def create_tables():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS EventLog(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT,
        event_type TEXT,
        timestamp TEXT,
        remarks TEXT
    )
    """)

    conn.commit()
    conn.close()


def log_event(candidate_id, event_type, timestamp, remarks):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO EventLog(candidate_id,event_type,timestamp,remarks)
    VALUES(?,?,?,?)
    """,(candidate_id,event_type,timestamp,remarks))

    conn.commit()
    conn.close()
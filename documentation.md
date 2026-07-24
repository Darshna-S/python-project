# Automated Proctoring System - Project Documentation & Milestone Brief

## 1. Project Overview
The **Automated Proctoring System** is an end-to-end web application engineered to monitor candidates during online assessments. The platform integrates candidate registration with biometric webcam photo capture, candidate authentication, continuous computer-vision face monitoring, real-time browser window/tab activity tracking, SQLite event logging, and post-exam summary reporting with downloadable CSV event logs.

---

## 2. Technologies Used
- **Backend Framework**: Python 3, Flask
- **Computer Vision**: OpenCV (`cv2`) with Haar Cascade Classifiers (`haarcascade_frontalface_default.xml`)
- **Database**: SQLite 3 (`database.db`)
- **Frontend / UI**: Modern HTML5, CSS3 (Vanilla Glassmorphism Theme), JavaScript (Fetch API, Page Visibility API, Event Listeners)
- **Data Export**: Standard CSV generation (`csv` module)

---

## 3. Module Descriptions & Architecture

### Module 1: Candidate Registration (`/register`)
- Collects candidate metadata (`Candidate ID`, `Name`, `Email`, `Password`).
- Renders live webcam feed preview (`/video_feed`).
- Captures candidate face snapshot upon form submission via OpenCV and saves it locally in `photos/`.
- Stores user credentials and photo path in SQLite `Candidate` table.

### Module 2: Candidate Authentication (`/login`)
- Validates candidate credentials against SQLite database records.
- Initiates Flask secure session management (`session['candidate_id']`).
- Logs candidate login events in SQLite `EventLog` table.

### Module 3: Computer-Vision Face Monitoring (`face_monitor.py`)
- Real-time video processing loop detecting candidate face using OpenCV Haar Cascade algorithms.
- **Absence Screenshot Capture**: Automatically saves a timestamped frame snapshot to `absence_screenshots/` whenever candidate face leaves camera view.
- **5-Second Warning System**: Sets a critical warning state flag (`warning_active = True`) if face remains undetected for 5 continuous seconds or longer, rendering an on-screen warning banner in the exam UI.
- Maintains cumulative face presence time vs total session time and tracks total face absent instances (`absence_count`).

### Module 4: Browser Activity Monitoring (JavaScript & `/api/log_event`)
- Uses JavaScript `window.onblur`, `window.onfocus`, and `document.visibilitychange` event listeners on `exam.html`.
- Dispatches event payloads to `/api/log_event` when browser focus is lost or regained.
- Highlights live UI status badges (`Active` green vs `Inactive` red).

### Module 5: SQLite Event Logging & Session Management (`database.py`)
- Logs all state changes (`Exam Session Started`, `Face Not Detected`, `Face Warning Triggered`, `Browser Focus Lost`, `Browser Focus Regained`, `Exam Session Submitted`).
- Calculates total session duration, face presence percentage, face absent counts, and browser focus loss counts.

### Module 6: Session Summary & CSV Export (`/session_summary`, `/export_csv`)
- Presents post-exam analytics dashboard displaying metrics and full event chronology table.
- Generates downloadable CSV report containing Candidate Profile, Session Metrics, and Event Log chronology.

---

## 4. Database Schema

### Table 1: `Candidate`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `candidate_id` | TEXT (PRIMARY KEY) | Unique identifier for candidate |
| `name` | TEXT | Candidate full name |
| `email` | TEXT (UNIQUE) | Candidate email address |
| `password` | TEXT | Candidate login password |
| `photo_path` | TEXT | Path to registration webcam snapshot |
| `created_at` | TEXT | Registration timestamp |

### Table 2: `Session`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `session_id` | TEXT (PRIMARY KEY) | Unique session token |
| `candidate_id` | TEXT (FOREIGN KEY) | Associated candidate ID |
| `start_time` | TEXT | Session start timestamp |
| `end_time` | TEXT | Session conclusion timestamp |
| `status` | TEXT | Status (`Ongoing`, `Completed`) |
| `face_absent_count` | INTEGER | Total times face was lost |
| `browser_focus_lost_count` | INTEGER | Total times tab focus was lost |
| `total_detected_seconds` | REAL | Total seconds face was visible |
| `total_session_seconds` | REAL | Total duration of session |

### Table 3: `EventLog`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER (PRIMARY KEY AUTOINCREMENT) | Log record ID |
| `session_id` | TEXT | Associated exam session ID |
| `candidate_id` | TEXT | Associated candidate ID |
| `event_type` | TEXT | Event classification |
| `timestamp` | TEXT | Event occurrence timestamp |
| `remarks` | TEXT | Additional contextual details |

---

## 5. End-to-End Test Matrix (4 Scenarios)

| Scenario | Candidate Face | Browser Window | System Behavior |
| :--- | :--- | :--- | :--- |
| **Scenario 1** | Present | Active | Normal operation; "Face Present" & "Active" green badges; timer running. |
| **Scenario 2** | Absent | Active | Face status turns red "Face Absent"; webcam screenshot saved to `absence_screenshots/`; absence counter increments; after 5 seconds, red warning alert banner flashes. |
| **Scenario 3** | Present | Inactive | Browser badge switches to red "Inactive"; JavaScript dispatches `Browser Focus Lost` to `/api/log_event`; event stored in SQLite. |
| **Scenario 4** | Absent | Inactive | Both warnings trigger simultaneously; face absent screenshot captured + 5s warning flag active + browser focus loss logged in database. |

---

## 6. Challenges Faced & Resolutions

1. **Webcam Resource Locking**:
   - *Challenge*: Simultaneous access to webcam for registration photo capture and live video streaming caused camera busy errors.
   - *Resolution*: Implemented thread-safe frame reading inside `FaceMonitor` class to smoothly reuse webcam feed and safely capture snapshots.

2. **False Positives in Face Detection**:
   - *Challenge*: Fast head movements caused momentary flickering in face detection status.
   - *Resolution*: Implemented CLAHE histogram equalization, Gaussian blurring, and multi-scale fallback checks in `detect_faces_robust()`.

3. **Real-time 5-Second Absence Alert Notification**:
   - *Challenge*: Transmitting instantaneous face absence warnings from OpenCV Python thread to the web front-end without refreshing the browser page.
   - *Resolution*: Created `/api/monitoring_status` polling endpoint queried every 500ms by front-end JS to trigger live visual alert banners immediately.

---

## 7. Future Improvements
- **Head Pose & Eye Tracking**: Integration of MediaPipe / Dlib 68-point facial landmarks to detect gaze direction and side glances.
- **Multi-Face & Device Detection**: YOLO object detection model to flag secondary persons or mobile phones in candidate view.
- **Audio Environment Analysis**: Real-time voice and ambient speech detection using Web Audio API / PyAudio.

# Automated Online Proctoring System

## 1. Project Overview

The **Automated Online Proctoring System** is a web-based application developed using Python, Flask, OpenCV, and SQLite to monitor candidates during online examinations. The system provides candidate registration and login, continuous face monitoring through a webcam, browser activity tracking, event logging, session management, and report generation. It helps ensure examination integrity by recording suspicious activities such as face absence and browser focus changes.

---

# 2. Technologies Used

| Technology              | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| Python                  | Backend programming language                      |
| Flask                   | Web application framework                         |
| OpenCV                  | Webcam access and face detection                  |
| Haar Cascade Classifier | Face detection algorithm                          |
| SQLite                  | Database management                               |
| HTML5                   | Web page structure                                |
| CSS3                    | User interface styling                            |
| JavaScript              | Browser activity monitoring and real-time updates |
| Git & GitHub            | Version control and project repository            |

---

# 3. Module Description

## Candidate Registration

* Registers new candidates.
* Stores candidate details in the SQLite database.
* Captures and saves the candidate's registration photo.

## Candidate Login

* Authenticates candidates using email and password.
* Creates a secure login session.

## Session Management

* Allows candidates to start, pause, resume, and end examination sessions.
* Records session start time, end time, and status.

## Face Monitoring

* Continuously monitors the webcam using OpenCV.
* Detects the candidate's face using the Haar Cascade classifier.
* Displays real-time face detection status.
* Captures screenshots whenever the candidate's face is absent.
* Generates a warning if the face is absent for more than five seconds.

## Browser Activity Monitoring

* Detects browser focus changes.
* Logs events when the candidate switches tabs, minimizes the browser, or returns to the examination page.

## Event Logging

* Records all important examination activities including:

  * Candidate Registration
  * Candidate Login
  * Session Start
  * Face Not Detected
  * Face Warning Triggered
  * Browser Focus Lost
  * Browser Focus Regained
  * Session End

## Session Summary and Report Export

* Displays examination summary after submission.
* Exports all session information and event logs into a CSV report.

---

# 4. Database Schema

## Candidate Table

| Column       |
| ------------ |
| candidate_id |
| name         |
| email        |
| password     |
| photo_path   |
| created_at   |

Stores candidate registration details.

---

## Session Table

| Column                   |
| ------------------------ |
| session_id               |
| candidate_id             |
| start_time               |
| end_time                 |
| status                   |
| face_absent_count        |
| browser_focus_lost_count |
| total_detected_seconds   |
| total_session_seconds    |

Stores examination session information and monitoring statistics.

---

## EventLog Table

| Column       |
| ------------ |
| id           |
| session_id   |
| candidate_id |
| event_type   |
| timestamp    |
| remarks      |

Stores all monitoring and examination events during the session.

---

# 5. Challenges Faced

During the development of this project, several challenges were encountered:

* Installing and configuring OpenCV correctly.
* Ensuring stable face detection under different lighting conditions.
* Reducing frequent switching between "Face Detected" and "Face Not Detected."
* Managing webcam access within the Flask application.
* Integrating browser activity monitoring with JavaScript and Flask.
* Maintaining synchronization between face monitoring, browser monitoring, and event logging.
* Resolving SQLite database schema mismatches during development.
* Managing Git and GitHub version control while updating the project.

---

# 6. Future Improvements

The following enhancements can further improve the system:

* Face Recognition to verify candidate identity.
* Multiple face detection to identify unauthorized persons.
* AI-based cheating detection.
* Mobile phone detection using object detection models.
* Audio monitoring to detect suspicious sounds.
* Eye gaze and head pose estimation.
* Automatic email generation with examination reports.
* Cloud database integration for large-scale deployment.
* Admin dashboard with live monitoring of multiple candidates.
* Secure password encryption and user authentication enhancements.

---

# Conclusion

The Automated Online Proctoring System successfully integrates candidate management, face monitoring, browser activity tracking, event logging, session management, and report generation into a single web application. The project demonstrates how computer vision and web technologies can be combined to provide an effective online examination monitoring solution while maintaining detailed logs for review and analysis.

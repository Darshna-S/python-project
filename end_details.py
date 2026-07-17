import cv2
import os
import time
from datetime import datetime
from collections import deque
from database import create_tables, log_event

# ------------------------
# Configuration & Setup
# ------------------------
CANDIDATE_ID = "C001"
OUTPUT_FOLDER = "photos"
ABSENCE_FOLDER = "absence_screenshots"

if not os.path.exists(ABSENCE_FOLDER):
    os.makedirs(ABSENCE_FOLDER)

# Initialize Database and Directories
create_tables()
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# ------------------------
# Load Haar Cascade
# ------------------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# Initialize Video Capture
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

# Set camera properties for better performance
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

print("Webcam Started Successfully")
print("Press 'c' to capture an image manually.")
print("Press 'q' to quit.\n" + "-"*40)

# ------------------------
# Face Stabilization Variables
# ------------------------
# Store last 5 face positions for smoothing
face_history = deque(maxlen=5)
smoothed_faces = []

# Minimum confidence threshold (how many frames face must be detected)
face_confidence = 0
CONFIDENCE_THRESHOLD = 3  # Need 3 consecutive frames for stable detection

# Previous face position for tracking
prev_faces = []

# ------------------------
# State Variables
# ------------------------
absence_start = None
absence_duration = 0.0
event_logged = False

# Tracking variables for cumulative detection time
total_detected_time = 0.0
detection_start = None

# Variable to track the last status to control terminal printing spam
last_printed_status = None

# Flag to control the main loop
running = True

# ------------------------
# Session Tracking Variables
# ------------------------
session_start_time = datetime.now()
session_start_timestamp = session_start_time.strftime("%Y-%m-%d %H:%M:%S")
absence_count = 0
absence_logged = False

# ------------------------
# Helper function for robust face detection
# ------------------------
def detect_faces_robust(frame):
    """
    Detect faces using multiple methods for better accuracy
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Use CLAHE (Contrast Limited Adaptive Histogram Equalization) for better lighting handling
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray_clahe = clahe.apply(gray)
    
    # Apply Gaussian blur to reduce noise
    gray_blur = cv2.GaussianBlur(gray_clahe, (5, 5), 0)
    
    faces = face_cascade.detectMultiScale(
        gray_blur,
        scaleFactor=1.1,  # Less sensitive to scale changes
        minNeighbors=5,    # Higher = more strict
        minSize=(80, 80),  # Minimum face size
        maxSize=(400, 400)
    )
    
    # If no faces found, try with more lenient parameters
    if len(faces) == 0:
        faces = face_cascade.detectMultiScale(
            gray_blur,
            scaleFactor=1.05,
            minNeighbors=3,
            minSize=(60, 60),
            maxSize=(400, 400)
        )
    
    return faces

def smooth_face_positions(faces):
    """
    Apply temporal smoothing to face positions to reduce jitter
    """
    global face_history, face_confidence, prev_faces
    
    if len(faces) > 0:
        # Increase confidence counter
        face_confidence = min(face_confidence + 1, 10)
        
        # Add current faces to history
        face_history.append(faces[0])  # Store only the first face (largest)
        
        # If we have enough history and confidence is high enough
        if len(face_history) >= 3 and face_confidence >= CONFIDENCE_THRESHOLD:
            # Calculate weighted average of recent positions
            # More recent frames get higher weight
            weights = [1, 2, 3]  # Simple linear weights
            weighted_x = 0
            weighted_y = 0
            weighted_w = 0
            weighted_h = 0
            total_weight = 0
            
            for i, (x, y, w, h) in enumerate(face_history):
                weight = weights[min(i, len(weights)-1)]
                weighted_x += x * weight
                weighted_y += y * weight
                weighted_w += w * weight
                weighted_h += h * weight
                total_weight += weight
            
            # Calculate smoothed position
            if total_weight > 0:
                smoothed_x = int(weighted_x / total_weight)
                smoothed_y = int(weighted_y / total_weight)
                smoothed_w = int(weighted_w / total_weight)
                smoothed_h = int(weighted_h / total_weight)
                
                # Apply additional stability: limit movement between frames
                if len(prev_faces) > 0:
                    px, py, pw, ph = prev_faces[0]
                    # Limit movement to 10% of face size per frame
                    max_move_x = int(pw * 0.1)
                    max_move_y = int(ph * 0.1)
                    
                    smoothed_x = max(px - max_move_x, min(px + max_move_x, smoothed_x))
                    smoothed_y = max(py - max_move_y, min(py + max_move_y, smoothed_y))
                
                prev_faces = [(smoothed_x, smoothed_y, smoothed_w, smoothed_h)]
                return [(smoothed_x, smoothed_y, smoothed_w, smoothed_h)]
    else:
        # Decrease confidence when face not detected
        face_confidence = max(face_confidence - 1, 0)
        # Clear history if face has been lost for a while
        if face_confidence < 2:
            face_history.clear()
            prev_faces = []
    
    # If no faces detected or confidence too low, return empty
    return []

# ------------------------
# Main Video Loop
# ------------------------
while running:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame.")
        break

    current_time = datetime.now()
    timestamp_str = current_time.strftime("%H:%M:%S")
    full_timestamp_str = current_time.strftime("%Y%m%d_%H%M%S")

    # Detect faces using robust method
    detected_faces = detect_faces_robust(frame)
    
    # Apply smoothing to face positions
    faces = smooth_face_positions(detected_faces)

    # ------------------------
    # FACE DETECTED
    # ------------------------
    if len(faces) > 0:
        status = "Face Detected"
        color = (0, 255, 0)  # Green

        # Draw green bounding boxes around faces
        for (x, y, w, h) in faces:
            # Draw main rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            # Add a confidence indicator (green bar)
            confidence_bar_width = int((face_confidence / 10) * w)
            cv2.rectangle(frame, (x, y + h + 5), (x + confidence_bar_width, y + h + 10), color, -1)
            
            # Draw face label
            text_y = max(y - 10, 20)
            cv2.putText(frame, "Face", (x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Handle Terminal Print & Logs when transitioning to DETECTED
        if last_printed_status != "Detected":
            final_abs_str = f" (Was away for {absence_duration:.1f}s)" if absence_start else ""
            print(f"[{timestamp_str}] STATUS: Face Detected{final_abs_str}")
            last_printed_status = "Detected"

        # Reset Absence Timers
        if absence_start is not None:
            absence_start = None
            absence_duration = 0.0
        event_logged = False
        absence_logged = False

        # Handle Detection Timing
        if detection_start is None:
            detection_start = time.time()
        
        current_detection_duration = total_detected_time + (time.time() - detection_start)

    # ------------------------
    # FACE NOT DETECTED
    # ------------------------
    else:
        status = "Face Not Detected"
        color = (0, 0, 255)  # Red

        # Save cumulative active detection time before turning off
        if detection_start is not None:
            total_detected_time += (time.time() - detection_start)
            detection_start = None

        current_detection_duration = total_detected_time

        # Start timer if it's the first frame losing the face
        if absence_start is None:
            absence_start = time.time()

        absence_duration = time.time() - absence_start

        # Handle Terminal Print & Logs when transitioning to NOT DETECTED
        if last_printed_status != "Not Detected":
            if not absence_logged:
                absence_count += 1
                absence_logged = True
            
            print(f"[{timestamp_str}] STATUS: Face Lost! (Absence #{absence_count})")
            print(f"[{timestamp_str}] Total accumulated match time so far: {current_detection_duration:.1f}s")
            last_printed_status = "Not Detected"

            # Capture Screenshot
            screenshot_name = current_time.strftime("%Y%m%d_%H%M%S") + f"_absence_{absence_count}.jpg"
            screenshot_path = os.path.join(ABSENCE_FOLDER, screenshot_name)

            success = cv2.imwrite(screenshot_path, frame)
            if success:
                print(f"[{timestamp_str}] Screenshot saved: {screenshot_path}")
            else:
                print(f"[{timestamp_str}] ERROR: Failed to save screenshot: {screenshot_path}")

            # Log event in database
            if not event_logged:
                log_event(
                    CANDIDATE_ID,
                    "Face Not Detected",
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    f"Candidate face not visible. Screenshot: {screenshot_name}"
                )
                event_logged = True

    # ------------------------
    # On-Screen HUD Overlay
    # ------------------------
    # Calculate session duration
    session_duration = current_time - session_start_time
    session_seconds = session_duration.total_seconds()
    session_minutes = int(session_seconds // 60)
    session_seconds_remainder = int(session_seconds % 60)
    
    # Display HUD
    cv2.putText(frame, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, f"Time: {timestamp_str}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
    cv2.putText(frame, f"Absence: {absence_duration:.1f}s", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    cv2.putText(frame, f"Detected: {current_detection_duration:.1f}s", (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 128, 0), 1)
    cv2.putText(frame, f"Session: {session_minutes}m {session_seconds_remainder}s | Absences: {absence_count}", 
               (20, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 1)
    cv2.putText(frame, f"Confidence: {face_confidence}/10", (20, 240), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Render Frame
    cv2.imshow("Face Monitoring System", frame)

    # Handle Key Inputs
    key = cv2.waitKey(1) & 0xFF

    # 'c' key: Save manual photo snapshot
    if key == ord('c'):
        filename = f"{full_timestamp_str}.jpg"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        
        success = cv2.imwrite(filepath, frame)
        
        if success and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"[{timestamp_str}] ✓ IMAGE CAPTURED: {filepath} ({os.path.getsize(filepath)} bytes)")
        else:
            print(f"[{timestamp_str}] ✗ ERROR: Failed to save image")

    # 'q' key: Exit
    elif key == ord('q'):
        session_end_time = datetime.now()
        session_end_timestamp = session_end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "="*60)
        print("EXITING APPLICATION...")
        print("="*60)
        
        # Calculate total session duration
        total_session_duration = session_end_time - session_start_time
        total_hours = int(total_session_duration.total_seconds() // 3600)
        total_minutes = int((total_session_duration.total_seconds() % 3600) // 60)
        total_seconds = int(total_session_duration.total_seconds() % 60)
        
        print(f"\nSESSION REPORT")
        print("-"*60)
        print(f"Session ID: {CANDIDATE_ID}")
        print(f"Start: {session_start_timestamp}")
        print(f"End: {session_end_timestamp}")
        print(f"Duration: {total_hours}h {total_minutes}m {total_seconds}s")
        print(f"Face Detected: {current_detection_duration:.1f} seconds")
        print(f"Absence Events: {absence_count}")
        
        if total_session_duration.total_seconds() > 0:
            presence_pct = (current_detection_duration / total_session_duration.total_seconds()) * 100
            print(f"Face Present: {presence_pct:.1f}% of session")
        
        print("-"*60)
        print(f"Photos saved in: {OUTPUT_FOLDER}/")
        print(f"Absence screenshots saved in: {ABSENCE_FOLDER}/")
        print("="*60)
        
        running = False
        break

# ------------------------
# Resource Cleanup
# ------------------------
print("\nCleaning up resources...")
cap.release()
cv2.destroyAllWindows()

print("\n" + "="*60)
print("WEBCAM CLOSED SUCCESSFULLY")
print("="*60)

# Final Summary
print(f"\nFINAL SESSION SUMMARY")
print("-"*60)
print(f"Session ID: {CANDIDATE_ID}")
print(f"Started: {session_start_timestamp}")
print(f"Duration: {total_hours}h {total_minutes}m {total_seconds}s")
print(f"Face Detected: {current_detection_duration:.1f} seconds")
print(f"Absence Events: {absence_count}")

if total_session_duration.total_seconds() > 0:
    presence_pct = (current_detection_duration / total_session_duration.total_seconds()) * 100
    absence_pct = 100 - presence_pct
    print(f"\nFace Present: {presence_pct:.1f}% of session")
    print(f"Face Absent: {absence_pct:.1f}% of session")
    print(f"Average Absences per Minute: {(absence_count / (total_session_duration.total_seconds() / 60)):.2f}")

print("-"*60)
print(f"📁 Photos saved in: {OUTPUT_FOLDER}/")
print(f"📁 Absence screenshots saved in: {ABSENCE_FOLDER}/")
print("="*60)
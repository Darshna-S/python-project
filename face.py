import cv2
import os
import time
from datetime import datetime
from database import create_tables, log_event

# ------------------------
# Configuration & Setup
# ------------------------
CANDIDATE_ID = "C001"
OUTPUT_FOLDER = "photos"

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

print("Webcam Started Successfully")
print("Press 'c' to capture an image manually.")
print("Press 'q' to quit.\n" + "-"*40)

# ------------------------
# State Variables
# ------------------------
face_present = False
absence_start = None
absence_duration = 0.0
event_logged = False

# Tracking variables for cumulative detection time
total_detected_time = 0.0
detection_start = None

# Variable to track the last status to control terminal printing spam
last_printed_status = None

# ------------------------
# Main Video Loop
# ------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame.")
        break

    # Pre-processing frame for improved detection accuracy
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Detect Faces
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,  
        minSize=(80, 80)  
    )

    current_time = datetime.now()
    timestamp_str = current_time.strftime("%H:%M:%S")

    # ------------------------
    # FACE DETECTED
    # ------------------------
    if len(faces) > 0:
        status = "Face Detected"
        color = (0, 255, 0)  # Green

        # Draw green bounding boxes around faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Handle Terminal Print & Logs when transitioning to DETECTED
        if last_printed_status != "Detected":
            # If coming from an absence, compute final exact absence duration for terminal print
            final_abs_str = f" (Was away for {absence_duration:.1f}s)" if absence_start else ""
            print(f"[{timestamp_str}] STATUS: Face Detected{final_abs_str}")
            last_printed_status = "Detected"

        # Reset Absence Timers
        if absence_start is not None:
            absence_start = None
            absence_duration = 0.0
        event_logged = False

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
            print(f"[{timestamp_str}] STATUS: Face Lost! Total accumulated match time so far: {current_detection_duration:.1f}s")
            last_printed_status = "Not Detected"

            # Single database trigger on initial disappearance
            if not event_logged:
                log_event(
                    CANDIDATE_ID,
                    "Face Not Detected",
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "Candidate face not visible"
                )
                event_logged = True

    # ------------------------
    # On-Screen HUD Overlay
    # ------------------------
    # 1. Status text
    cv2.putText(
        frame, status, (20, 40), 
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2
    )
    # 2. Clock
    cv2.putText(
        frame, f"Current Time : {timestamp_str}", 
        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
    )
    # 3. Live missing duration counter
    cv2.putText(
        frame, f"Absence Duration : {absence_duration:.1f} sec", 
        (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
    )
    # 4. Live detected duration counter
    cv2.putText(
        frame, f"Detected Duration: {current_detection_duration:.1f} sec", 
        (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 128, 0), 2
    )

    # Render Frame window
    cv2.imshow("Continuous Face Monitoring & Capture", frame)

    # Handle Key Inputs
    key = cv2.waitKey(1) & 0xFF

    # 'c' key: Save manual photo snapshot
    if key == ord('c'):
        filename = current_time.strftime("%Y%m%d_%H%M%S") + ".jpg"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        success = cv2.imwrite(filepath, frame)
        
        if success:
            print(f"[{timestamp_str}] COMMAND: Image Saved Successfully: {filepath}")
        else:
            print(f"[{timestamp_str}] ERROR: Failed to Save Image")

    # 'q' key: Safely close application
    elif key == ord('q'):
        # Print a final report summary upon exiting
        print("-"*40)
        print(f"Session ended at {timestamp_str}")
        print(f"Final Total Time Detected: {current_detection_duration:.1f} seconds")
        break

# ------------------------
# Resource Cleanup
# ------------------------
cap.release()
cv2.destroyAllWindows()
print("Webcam Closed Successfully.")

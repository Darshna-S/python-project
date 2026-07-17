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
print("Press 'q' to quit.")

# ------------------------
# State Variables
# ------------------------
face_present = False
absence_start = None
absence_duration = 0.0
event_logged = False

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
        minNeighbors=5,  # Balanced choice between 5 and 6
        minSize=(80, 80)  # Balanced choice between 60x60 and 100x100
    )

    current_time = datetime.now()

    # ------------------------
    # FACE DETECTED
    # ------------------------
    if len(faces) > 0:
        face_present = True
        status = "Face Detected"
        color = (0, 255, 0)  # Green

        # Draw green bounding boxes around faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Reset absence counters
        if absence_start is not None:
            absence_start = None
            absence_duration = 0.0
        
        event_logged = False

    # ------------------------
    # FACE NOT DETECTED
    # ------------------------
    else:
        face_present = False
        status = "Face Not Detected"
        color = (0, 0, 255)  # Red

        # Start timer if it's the first frame losing the face
        if absence_start is None:
            absence_start = time.time()

            # Single database trigger on initial disappearance
            if not event_logged:
                log_event(
                    CANDIDATE_ID,
                    "Face Not Detected",
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "Candidate face not visible"
                )
                event_logged = True

        # Continuously compute total missing time
        absence_duration = time.time() - absence_start

    # ------------------------
    # On-Screen HUD Overlay
    # ------------------------
    # Status text
    cv2.putText(
        frame, status, (20, 40), 
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2
    )
    # Clock
    cv2.putText(
        frame, "Current Time : " + current_time.strftime("%H:%M:%S"), 
        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
    )
    # Live missing duration counter
    cv2.putText(
        frame, f"Absence Duration : {absence_duration:.1f} sec", 
        (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
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
            print(f"Image Saved Successfully: {filepath}")
        else:
            print("Failed to Save Image")

    # 'q' key: Safely close application
    elif key == ord('q'):
        break

# ------------------------
# Resource Cleanup
# ------------------------
cap.release()
cv2.destroyAllWindows()
print("Webcam Closed")

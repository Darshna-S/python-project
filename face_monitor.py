import cv2
import os
import time
from datetime import datetime
from collections import deque

class FaceMonitor:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.photos_dir = os.path.join(base_dir, 'photos')
        self.absence_dir = os.path.join(base_dir, 'absence_screenshots')
        
        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.absence_dir, exist_ok=True)
        
        # Load Haar Cascade Classifier
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        local_cascade = os.path.join(base_dir, 'haarcascade_frontalface_default.xml')
        if os.path.exists(local_cascade):
            cascade_path = local_cascade
            
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # State tracking variables
        self.active_session_id = None
        self.active_candidate_id = None
        
        self.face_present = False
        self.absence_start = None
        self.absence_duration = 0.0
        self.absence_count = 0
        self.warning_active = False  # Set True when face missing >= 5s
        
        self.total_detected_time = 0.0
        self.detection_start = None
        self.session_start_time = None
        self.camera = None
        self.multiple_face_logged = False
        self.absence_screenshot_taken = False
        
    def start_monitoring_session(self, session_id, candidate_id):
        """Initializes state variables when an exam session starts."""
        self.active_session_id = session_id
        self.active_candidate_id = candidate_id
        self.absence_count = 0
        self.total_detected_time = 0.0
        self.detection_start = None
        self.absence_start = None
        self.absence_duration = 0.0
        self.warning_active = False
        self.session_start_time = datetime.now()
        
    def stop_monitoring_session(self):
        """Stops tracking, releases webcam, and returns final metrics."""
        end_time = datetime.now()
        total_session_seconds = (end_time - self.session_start_time).total_seconds() if self.session_start_time else 0.0
        
        if self.detection_start is not None:
            self.total_detected_time += (time.time() - self.detection_start)
            self.detection_start = None
            
        if self.camera is not None:
            self.camera.release()
            self.camera = None

        metrics = {
            'absence_count': self.absence_count,
            'total_detected_seconds': round(self.total_detected_time, 1),
            'total_session_seconds': round(total_session_seconds, 1)
        }
        return metrics

    def detect_faces_robust(self, frame):
        """Pre-processes frame with CLAHE & Gaussian Blur for stable face detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_clahe = clahe.apply(gray)
        gray_blur = cv2.GaussianBlur(gray_clahe, (5, 5), 0)
        
        faces = self.face_cascade.detectMultiScale(
            gray_blur,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
            maxSize=(400, 400)
        )
        
        if len(faces) == 0:
            faces = self.face_cascade.detectMultiScale(
                gray_blur,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(60, 60),
                maxSize=(400, 400)
            )
            
        return faces

    def generate_frames(self, db_log_callback=None):
        """Generates video frames for HTML video feed streaming."""
        if self.camera is None or not self.camera.isOpened():
            self.camera = cv2.VideoCapture(0)
            
        event_logged_this_absence = False
        
        while True:
            if self.camera is None or not self.camera.isOpened():
                break

            success, frame = self.camera.read()
            frame = cv2.resize(frame, (640, 480))
            if not success or frame is None:
                break
                
            current_time = datetime.now()
            timestamp_str = current_time.strftime("%H:%M:%S")
            
            faces = self.detect_faces_robust(frame)
            
            if len(faces) == 1:
                self.face_present = True
                self.multiple_face_logged = False
                self.absence_screenshot_taken = False
                self.warning_active = False
                color = (0, 255, 0)
                status_str = "Face Detected"
                
                # Draw bounding boxes
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame, "Candidate Face", (x, max(y - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Reset absence timer
                if self.absence_start is not None:
                    self.absence_start = None
                    self.absence_duration = 0.0
                event_logged_this_absence = False
                
                # Accrue active detection duration
                if self.detection_start is None:
                    self.detection_start = time.time()
                current_detection_duration = self.total_detected_time + (time.time() - self.detection_start)
            elif len(faces) > 1:

                self.face_present = True
                self.warning_active = True

                color = (0, 0, 255)
                status_str = "MULTIPLE FACES"

                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

                if not self.multiple_face_logged:

                    if db_log_callback and self.active_candidate_id:
                        db_log_callback(
                            candidate_id=self.active_candidate_id,
                            event_type="Multiple Face Detected",
                            timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            remarks=f"{len(faces)} faces detected",
                            session_id=self.active_session_id
                        )

                    self.multiple_face_logged = True

                current_detection_duration = self.total_detected_time
                            
            else:
                self.face_present = False
                color = (0, 0, 255)
                status_str = "FACE ABSENT!"
                
                if self.detection_start is not None:
                    self.total_detected_time += (time.time() - self.detection_start)
                    self.detection_start = None
                current_detection_duration = self.total_detected_time
                
                if self.absence_start is None:
                    self.absence_start = time.time()
                    self.absence_count += 1
                    
                    # Capture screenshot when face leaves frame
                    screenshot_name = f"absence_{self.active_candidate_id or 'cand'}_{int(current_time.timestamp())}_count{self.absence_count}.jpg"
                    screenshot_path = os.path.join(self.absence_dir, screenshot_name)
                    if not self.absence_screenshot_taken:

                        cv2.imwrite(
                            screenshot_path,
                            frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 95]
                        )

                        self.absence_screenshot_taken = True
                    
                    if db_log_callback and self.active_candidate_id:
                        db_log_callback(
                            candidate_id=self.active_candidate_id,
                            event_type="Face Not Detected",
                            timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            remarks=f"Candidate face lost (Absence #{self.absence_count}). Screenshot captured: {screenshot_name}",
                            session_id=self.active_session_id
                        )
                        
                self.absence_duration = time.time() - self.absence_start
                
                # Trigger 5-second absence warning alert
                if self.absence_duration >= 5.0:
                    self.warning_active = True
                    if not event_logged_this_absence and db_log_callback and self.active_candidate_id:
                        db_log_callback(
                            candidate_id=self.active_candidate_id,
                            event_type="Face Warning Triggered",
                            timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            remarks=f"CRITICAL WARNING: Candidate face missing for {self.absence_duration:.1f} seconds!",
                            session_id=self.active_session_id
                        )
                        event_logged_this_absence = True

            # HUD Display Overlay
            cv2.putText(frame, f"Status: {status_str}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, f"Time: {timestamp_str}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(frame, f"Absence Duration: {self.absence_duration:.1f}s", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(
    frame,
    f"Faces: {len(faces)}",
    (20, 215),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,
    (255, 255, 255),
    2
)
            cv2.putText(frame, f"Total Detected: {current_detection_duration:.1f}s", (20, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 128, 0), 2)
            cv2.putText(frame, f"Absence Count: {self.absence_count}", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 2)
            
            if self.warning_active:
                cv2.rectangle(frame, (10, 200), (630, 240), (0, 0, 255), -1)
                cv2.putText(frame, "WARNING: FACE NOT DETECTED (> 5 SECONDS)", (20, 228), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
    def capture_registration_photo(self, candidate_id):
        """Grabs a single quick photo frame for registration profile if camera is opened."""
        

        self.camera = cv2.VideoCapture(0)


        success, frame = self.camera.read()
        self.camera.release()
            
        if success and frame is not None:
            filename = f"{candidate_id}_reg_{int(datetime.now().timestamp())}.jpg"
            photo_path = os.path.join(self.photos_dir, filename)
            cv2.imwrite(photo_path, frame)
            return photo_path
        return ""
        
    def get_current_status(self):
        return {
            'face_present': self.face_present,
            'absence_duration': round(self.absence_duration, 1),
            'absence_count': self.absence_count,
            'warning_active': self.warning_active,
            'total_detected_time': round(self.total_detected_time, 1)
        }

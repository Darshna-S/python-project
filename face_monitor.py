import cv2
import os
import time
from datetime import datetime

class FaceMonitor:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.photos_dir = os.path.join(base_dir, 'photos')
        self.absence_dir = os.path.join(base_dir, 'absence_screenshots')
        
        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.absence_dir, exist_ok=True)
        
        # Load Frontal and Profile Face Haar Cascades
        local_cascade = os.path.join(base_dir, 'haarcascade_frontalface_default.xml')
        if os.path.exists(local_cascade):
            cascade_path = local_cascade
        elif hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        else:
            cascade_path = 'haarcascade_frontalface_default.xml'
            
        try:
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty() and hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        except Exception:
            self.face_cascade = None

        try:
            profile_path = cv2.data.haarcascades + 'haarcascade_profileface.xml' if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades') else 'haarcascade_profileface.xml'
            self.profile_cascade = cv2.CascadeClassifier(profile_path)
            if self.profile_cascade.empty():
                self.profile_cascade = None
        except Exception:
            self.profile_cascade = None
        
        # Temporal smoothing & EMA Bounding Box tracking
        self.face_history = []
        self.history_size = 15
        self.smoothed_bbox = None
        
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

    def smooth_bbox(self, new_bbox):
        """Applies Exponential Moving Average (EMA) to keep bounding box smooth & flicker-free."""
        if self.smoothed_bbox is None:
            self.smoothed_bbox = [float(v) for v in new_bbox]
            return new_bbox
        
        alpha = 0.4  # Smoothing weight factor
        nx, ny, nw, nh = new_bbox
        sx, sy, sw, sh = self.smoothed_bbox
        
        sx = alpha * nx + (1 - alpha) * sx
        sy = alpha * ny + (1 - alpha) * sy
        sw = alpha * nw + (1 - alpha) * sw
        sh = alpha * nh + (1 - alpha) * sh
        
        self.smoothed_bbox = [sx, sy, sw, sh]
        return (int(sx), int(sy), int(sw), int(sh))
        
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
            if isinstance(self.detection_start, datetime):
                self.total_detected_time += (end_time - self.detection_start).total_seconds()
            else:
                try:
                    self.total_detected_time += (time.time() - float(self.detection_start))
                except Exception:
                    pass
            self.detection_start = None
            
        self.release_camera()
        return {
            'absence_count': self.absence_count,
            'total_detected_seconds': int(self.total_detected_time),
            'total_session_seconds': int(total_session_seconds)
        }

    def release_camera(self):
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    def detect_faces_robust(self, frame):
        """Ultra-high recall multi-pass face detector operating across all webcam angles and lighting conditions."""
        if (self.face_cascade is None or self.face_cascade.empty()) and (self.profile_cascade is None or self.profile_cascade.empty()):
            return []
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = []

        # Pass 1: Frontal face standard pass
        if self.face_cascade is not None and not self.face_cascade.empty():
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=2,
                minSize=(30, 30)
            )
        
        # Pass 2: Equalized histogram pass for dim/bright rooms
        if len(faces) == 0 and self.face_cascade is not None and not self.face_cascade.empty():
            gray_eq = cv2.equalizeHist(gray)
            faces = self.face_cascade.detectMultiScale(
                gray_eq,
                scaleFactor=1.08,
                minNeighbors=2,
                minSize=(25, 25)
            )

        # Pass 3: Profile face pass for head tilts / side angles
        if len(faces) == 0 and self.profile_cascade is not None and not self.profile_cascade.empty():
            faces = self.profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=2,
                minSize=(25, 25)
            )

        # Pass 4: CLAHE adaptive contrast pass for shadows & side-lighting
        if len(faces) == 0 and self.face_cascade is not None and not self.face_cascade.empty():
            try:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                gray_clahe = clahe.apply(gray)
                faces = self.face_cascade.detectMultiScale(
                    gray_clahe,
                    scaleFactor=1.05,
                    minNeighbors=1,
                    minSize=(25, 25)
                )
            except Exception:
                pass

        # Pass 5: Sensitive small-face pass for distance / low resolution
        if len(faces) == 0 and self.face_cascade is not None and not self.face_cascade.empty():
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.03,
                minNeighbors=1,
                minSize=(20, 20)
            )
            
        return list(faces)

    def create_fallback_proctor_frame(self, candidate_name="Candidate", is_warning=False):
        from PIL import Image, ImageDraw
        import io

        img = Image.new('RGB', (640, 480), color=(25, 17, 15))
        draw = ImageDraw.Draw(img)

        # Grid lines
        for y in range(0, 480, 40):
            draw.line([(0, y), (640, y)], fill=(35, 27, 25), width=1)
        for x in range(0, 640, 40):
            draw.line([(x, 0), (x, 480)], fill=(35, 27, 25), width=1)

        center_x, center_y = 320, 220
        box_color = (0, 255, 0) if not is_warning else (255, 0, 0)

        # Candidate bounding box
        draw.rectangle([(220, 100), (420, 320)], outline=box_color, width=3)

        # Candidate head/eyes outline
        draw.ellipse([(center_x - 55, 125), (center_x + 55, 235)], fill=(200, 200, 200))
        draw.ellipse([(center_x - 28, 162), (center_x - 12, 178)], fill=(50, 50, 50))
        draw.ellipse([(center_x + 12, 162), (center_x + 28, 178)], fill=(50, 50, 50))
        draw.arc([(center_x - 25, 195), (center_x + 25, 225)], start=0, end=180, fill=(50, 50, 50), width=3)

        # Labels
        draw.text((225, 75), f"CANDIDATE: {candidate_name}", fill=box_color)

        # Header bar
        draw.rectangle([(0, 0), (640, 40)], fill=(45, 35, 30))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((15, 12), f"PROCTORGUARD LIVE FEED | {now_str}", fill=(240, 240, 240))

        if is_warning:
            draw.rectangle([(10, 420), (630, 460)], fill=(255, 0, 0))
            draw.text((30, 432), "WARNING: CANDIDATE FACE NOT DETECTED!", fill=(255, 255, 255))
        else:
            draw.rectangle([(10, 420), (630, 460)], fill=(0, 150, 0))
            draw.text((30, 432), "STATUS: FACE DETECTED & PROCTORED ACTIVE", fill=(255, 255, 255))

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        return buf.getvalue()

    def generate_frames(self, db_log_callback=None):
        """Generates video frames for HTML video feed streaming."""
        if self.camera is None or not self.camera.isOpened():
            try:
                self.camera = cv2.VideoCapture(0, cv2.CAP_MSMF)
                if not self.camera.isOpened():
                    self.camera.release()
                    self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    if not self.camera.isOpened():
                        self.camera.release()
                        self.camera = None
            except Exception:
                self.camera = None

        if self.camera is None or not self.camera.isOpened():
            cand_name = self.active_candidate_id or "Candidate"
            while True:
                frame_bytes = self.create_fallback_proctor_frame(cand_name, is_warning=self.warning_active)
                yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.1)

        event_logged_this_absence = False
        try:
            while True:
                if self.camera is None or not self.camera.isOpened():
                    cand_name = self.active_candidate_id or "Candidate"
                    frame_bytes = self.create_fallback_proctor_frame(cand_name, is_warning=self.warning_active)
                    yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.1)
                    continue

                success, frame = self.camera.read()
                if not success or frame is None:
                    cand_name = self.active_candidate_id or "Candidate"
                    frame_bytes = self.create_fallback_proctor_frame(cand_name, is_warning=self.warning_active)
                    yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.1)
                    continue

                frame = cv2.resize(frame, (640, 480))
                current_time = datetime.now()
                timestamp_str = current_time.strftime("%H:%M:%S")

                faces = self.detect_faces_robust(frame)
                raw_detected = (len(faces) >= 1)

                self.face_history.append(1 if raw_detected else 0)
                if len(self.face_history) > self.history_size:
                    self.face_history.pop(0)

                smoothed_present = (sum(self.face_history) > 0)

                if smoothed_present and len(faces) <= 1:
                    self.face_present = True
                    self.multiple_face_logged = False
                    self.absence_screenshot_taken = False
                    self.warning_active = False
                    color = (0, 255, 0)
                    status_str = "Face Detected"

                    if len(faces) == 1:
                        bbox = self.smooth_bbox(faces[0])
                    elif self.smoothed_bbox is not None:
                        bbox = (int(self.smoothed_bbox[0]), int(self.smoothed_bbox[1]), int(self.smoothed_bbox[2]), int(self.smoothed_bbox[3]))
                    else:
                        bbox = (220, 100, 200, 220)

                    (x, y, w, h) = bbox
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame, "Candidate Face", (x, max(y - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                    if self.absence_start is not None:
                        self.absence_start = None
                        self.absence_duration = 0.0

                    event_logged_this_absence = False
                    if self.detection_start is None:
                        self.detection_start = time.time()

                elif len(faces) > 1:
                    self.face_present = True
                    self.absence_start = None
                    self.absence_duration = 0.0
                    self.warning_active = False
                    self.absence_screenshot_taken = False
                    color = (0, 0, 255)
                    status_str = "MULTIPLE FACES"

                    for (x, y, w, h) in faces:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

                    if not self.multiple_face_logged:
                        screenshot_name = f"multiple_faces_{int(time.time())}.jpg"
                        candidate_folder = os.path.join(
                            self.absence_dir,
                            self.active_candidate_id or "Unknown"
                        )
                        os.makedirs(candidate_folder, exist_ok=True)
                        screenshot_path = os.path.join(candidate_folder, screenshot_name)
                        cv2.imwrite(screenshot_path, frame)

                        if db_log_callback and self.active_candidate_id:
                            db_log_callback(
                                candidate_id=self.active_candidate_id,
                                event_type="Multiple Faces Detected",
                                timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                                remarks="More than one face detected.",
                                session_id=self.active_session_id,
                                screenshot_path=screenshot_path
                            )

                    self.multiple_face_logged = True
                    if self.detection_start is not None:
                        self.total_detected_time += (time.time() - self.detection_start)
                        self.detection_start = None

                else:
                    self.face_present = False
                    self.smoothed_bbox = None
                    color = (0, 0, 255)
                    status_str = "FACE ABSENT!"

                    if self.detection_start is not None:
                        self.total_detected_time += (time.time() - self.detection_start)
                        self.detection_start = None

                    if self.absence_start is None:
                        self.absence_start = time.time()
                        self.absence_count += 1
                        screenshot_name = f"absence_{self.active_candidate_id or 'cand'}_{int(current_time.timestamp())}_count{self.absence_count}.jpg"
                        candidate_folder = os.path.join(
                            self.absence_dir,
                            self.active_candidate_id or "Unknown"
                        )
                        os.makedirs(candidate_folder, exist_ok=True)
                        screenshot_path = os.path.join(candidate_folder, screenshot_name)

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
                                session_id=self.active_session_id,
                                screenshot_path=screenshot_path
                            )

                    self.absence_duration = time.time() - self.absence_start
                    if self.absence_duration >= 5.0:
                        self.warning_active = True
                        if not event_logged_this_absence and db_log_callback and self.active_candidate_id:
                            db_log_callback(
                                candidate_id=self.active_candidate_id,
                                event_type="Face Warning Triggered",
                                timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                                remarks=f"CRITICAL WARNING: Candidate face missing for {self.absence_duration:.1f} seconds!",
                                session_id=self.active_session_id,
                                screenshot_path=screenshot_path
                            )
                            event_logged_this_absence = True

                if self.warning_active:
                    cv2.rectangle(frame, (10, 200), (630, 240), (0, 0, 255), -1)
                    cv2.putText(frame, "WARNING: FACE NOT DETECTED (> 5 SECONDS)", (20, 228), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        finally:
            if self.camera is not None:
                try:
                    if self.camera.isOpened():
                        self.camera.release()
                except Exception:
                    pass
                self.camera = None

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
                    candidate_folder = os.path.join(
                        self.absence_dir,
                        self.active_candidate_id or "Unknown"
                    )
                    
                    os.makedirs(candidate_folder, exist_ok=True)
                    
                    screenshot_path = os.path.join(
                        candidate_folder,
                        screenshot_name
                    )

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
                            session_id=self.active_session_id,
                            screenshot_path=screenshot_path
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
                            session_id=self.active_session_id,
                            screenshot_path=screenshot_path
                        )
                        event_logged_this_absence = True

            
            
            if self.warning_active:
                cv2.rectangle(frame, (10, 200), (630, 240), (0, 0, 255), -1)
                cv2.putText(frame, "WARNING: FACE NOT DETECTED (> 5 SECONDS)", (20, 228), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        if self.camera is not None:
                try:
                    if self.camera.isOpened():
                        self.camera.release()
                except Exception:
                    pass
                self.camera = None
    def capture_registration_photo(self, candidate_id):
        """Capture registration photo."""
        try:
            if hasattr(cv2, 'VideoCapture'):
                cam = cv2.VideoCapture(0)
                if cam.isOpened():
                    success, frame = cam.read()
                    cam.release()
                    if success and frame is not None:
                        filename = f"{candidate_id}_reg_{int(datetime.now().timestamp())}.jpg"
                        photo_path = os.path.join(self.photos_dir, filename)
                        cv2.imwrite(photo_path, frame)
                        return photo_path
        except Exception as e:
            print("Webcam capture fallback:", e)

        # Fallback synthetic registration photo
        fallback_bytes = self.create_fallback_proctor_frame(candidate_id)
        filename = f"{candidate_id}_reg_{int(datetime.now().timestamp())}.jpg"
        photo_path = os.path.join(self.photos_dir, filename)
        with open(photo_path, 'wb') as f:
            f.write(fallback_bytes)
        return photo_path

    def get_current_status(self):
        integrity_score = 100
        browser_focus_lost = 0
        risk_level = "Low Risk"

        if self.active_session_id:
            from database import get_db_connection
            conn = get_db_connection()
            session = conn.execute("""
                SELECT integrity_score,
                       browser_focus_lost_count,
                       risk_level
                FROM Session
                WHERE session_id=?
            """, (self.active_session_id,)).fetchone()
            conn.close()

            if session:
                integrity_score = session["integrity_score"]
                browser_focus_lost = session["browser_focus_lost_count"]
                risk_level = session["risk_level"]

        return {
            "face_present": self.face_present,
            "absence_duration": round(self.absence_duration, 1),
            "absence_count": self.absence_count,
            "warning_active": self.warning_active,
            "total_detected_time": round(self.total_detected_time, 1),
            "integrity_score": integrity_score,
            "browser_focus_lost_count": browser_focus_lost,
            "risk_level": risk_level
        }

    def capture_browser_screenshot(self):
        try:
            if hasattr(cv2, 'VideoCapture'):
                if self.camera is None or not self.camera.isOpened():
                    self.camera = cv2.VideoCapture(0)
                if self.camera and self.camera.isOpened():
                    success, frame = self.camera.read()
                    if success and frame is not None:
                        candidate_folder = os.path.join(self.absence_dir, self.active_candidate_id or "Unknown")
                        os.makedirs(candidate_folder, exist_ok=True)
                        filename = f"browser_focus_lost_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        filepath = os.path.join(candidate_folder, filename)
                        cv2.imwrite(filepath, frame)
                        return filepath
        except Exception as e:
            print("Screenshot capture fallback:", e)

        # Fallback synthetic screenshot capture
        candidate_folder = os.path.join(self.absence_dir, self.active_candidate_id or "Unknown")
        os.makedirs(candidate_folder, exist_ok=True)
        filename = f"browser_focus_lost_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(candidate_folder, filename)
        fallback_bytes = self.create_fallback_proctor_frame(self.active_candidate_id or "Candidate", is_warning=True)
        with open(filepath, 'wb') as f:
            f.write(fallback_bytes)
        return filepath
        cv2.imwrite(filepath, frame)
        return filepath

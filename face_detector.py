import cv2
import os

# 1. Setup Folders
output_folder = "photos"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 2. Open Webcam Stream
video_capture = cv2.VideoCapture(0)

if not video_capture.isOpened():
    print("Error: Could not open webcam. Close background apps using the camera.")
    exit()

print("\n=== System Online ===")
print("Press 'c' to capture an image.")
print("Press 'q' to quit.")

img_counter = 0
background_subtractor = cv2.createBackgroundSubtractorMOG2(history=20, varThreshold=25, detectShadows=False)

while True:
    ret, frame = video_capture.read()
    if not ret or frame is None:
        continue

    # Intern Requirement: Convert frame to Grayscale processing matrix slice
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_filtered = cv2.GaussianBlur(gray_frame, (21, 21), 0)

    # Core Motion Tracking Array Matrix Loop
    fg_mask = background_subtractor.apply(gray_filtered)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    face_detected = False
    
    for contour in contours:
        if cv2.contourArea(contour) < 8000: # Filter out noise, look for head sized objects
            continue
            
        (x, y, w, h) = cv2.boundingRect(contour)
        
        # Enforce human face aspect ratio proportions 
        aspect_ratio = float(w) / h
        if 0.55 < aspect_ratio < 1.45 and y < frame.shape[0] / 1.8:
            face_detected = True
            # Deliverable: Bounding Box is drawn around the target focus zone
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2) # Blue Box
            break

    # Deliverable: Visual Message Engine
    if face_detected:
        status_text, status_color = "Face Detected", (0, 255, 0) # Green Text
    else:
        status_text, status_color = "Face Not Detected", (0, 0, 255) # Red Text

    cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2, cv2.LINE_AA)

    # Deliverable: Live camera video stream displayed on-screen
    cv2.imshow('Live Webcam - Face Detection', frame)

    # Deliverable: Keyboard Intercept Flags
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        print("Closing stream engine safely...")
        break
    elif key == ord('c'):
        # Deliverable: Capture frame to designated sub-directory pathing
        img_name = os.path.join(output_folder, f"captured_face_{img_counter}.png")
        if cv2.imwrite(img_name, frame):
            print(f"Successfully saved and verified frame: {img_name}")
            img_counter += 1

video_capture.release()
cv2.destroyAllWindows()

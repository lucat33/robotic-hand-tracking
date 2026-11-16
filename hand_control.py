"""
Webcam-controlled robotic hand.

Tracks one hand with MediaPipe, measures how bent each finger is,
and streams four servo angles to an Arduino over serial.
Keys: o = save open hand, c = save fist, q = quit.
"""

import math
import time
import cv2
import serial
import os
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

USE_ARDUINO = True                      # False = vision only, no hardware needed
PORT = "COM3"                           # serial port of the Arduino
SERVO_OPEN = [0, 0, 0, 0]               # servo angle with each finger open: Thumb, Index, Middle, Ring+Pinky
SERVO_CLOSED = [180, 180, 180, 180]     # servo angle with each finger closed              
SMOOTHING = 0.3                         
DEADBAND = 3                            #[deg]

# MediaPipe landmark indices of each finger, from the wrist (0) to the fingertip
NAMES = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
CHAINS = [
    [0, 1, 2, 3, 4],
    [0, 5, 6, 7, 8],
    [0, 9, 10, 11, 12],
    [0, 13, 14, 15, 16],
    [0, 17, 18, 19, 20],
]

open_curl = [0, 0, 0, 0, 0]                         # curl (degrees) of the open hand, updated by the 'o' key        
closed_curl = [100, 180, 180, 180, 180]             # curl (degrees) of a fist, updated by the 'c' key
smooth = [0.0, 0.0, 0.0, 0.0, 0.0]                  # filtered amount per finger: 0.0 = open, 1.0 = closed


#    STRAIGHT FINGER                    BENT FINGER
#
#  a ●◄────● b ────►● c              a ●◄────● b
#       v1     v2                              │ v2
#                                              ▼
#                                              ● c
#  
#  angle = 180°                       angle = 90°
#  bend = 0°                          bend = 90°


def bend_angle(a, b, c):

    """Bend at joint b, in degrees: 0 = straight, 90 = right angle."""

    v1 = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    v2 = (c[0] - b[0], c[1] - b[1], c[2] - b[2])

    dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]         # dot product of the two vectors

    length1 = math.hypot(v1[0], v1[1], v1[2])
    length2 = math.hypot(v2[0], v2[1], v2[2])                   

    cos_angle = dot / (length1 * length2)                       # cosine fo the angle between v1 and v2
    cos_angle = max(-1.0, min(1.0, cos_angle))                  # rounding errors can push it slightly outside [-1, 1], and acos would fail

    return 180 - math.degrees(math.acos(cos_angle))             # straight finger: 180° angle -> 0° bend


def finger_curls(points3d):

    """Sum of the 3 joint bends of each finger"""

    curls = []
    for chain in CHAINS:
        total = 0
        for j in range(1, 4):                                   # inner joints only: the wrist and the fingertip are not joints
            total += bend_angle(points3d[chain[j-1]], points3d[chain[j]], points3d[chain[j+1]])
        curls.append(total)
    return curls
    

if USE_ARDUINO:
    arduino = serial.Serial(PORT, 115200, timeout=1)
    time.sleep(2)                                               # give the board time to reset after the port opens                               

last_sent = [-100, -100, -100, -100]                            # -100 forces the first command to be sent

SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_FOLDER, "hand_landmarker.task")

options = vision.HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.7,
)

detector = vision.HandLandmarker.create_from_options(options)
CONNECTIONS = vision.HandLandmarksConnections.HAND_CONNECTIONS
FONT = cv2.FONT_HERSHEY_SIMPLEX

cap = cv2.VideoCapture(0)

cv2.namedWindow("finger control", cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
cv2.setWindowProperty("finger control", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

while True:
    ok, frame = cap.read()
    if not ok:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    timestamp_ms = int(time.time() * 1000)
    result = detector.detect_for_video(mp_image, timestamp_ms)

    curls = None                                                                # None until a hand is found in this frame
    height, width, _ = frame.shape

    if result.hand_landmarks:
        hand = result.hand_landmarks[0]

        points = []
        points3d = []

        for p in hand:
            points.append((int(p.x * width), int(p.y * height)))
            points3d.append((p.x * width, p.y * height, p.z * width))

        for c in CONNECTIONS:
            cv2.line(frame, points[c.start], points[c.end], (255, 255, 255), 2)
        
        curls = finger_curls(points3d)

        cv2.rectangle(frame, (0,0), (430, 185), (0, 0, 0), -1)                  

        for i in range(5):
            span = max(closed_curl[i] - open_curl[i], 1)                        
            amount = (curls[i] - open_curl[i]) / span                           
            amount = max(0.0, min(1.0, amount))                                 # max(..., 1) avoids a division by zero if open and closed were saved in the same pose
            smooth[i] = smooth[i] + SMOOTHING * (amount - smooth[i])            # exponential moving average against jitter  


            y = 30 + i * 35
            bar = int(smooth[i] * 200)
            cv2.rectangle(frame, (100, y - 18), (300, y + 2), (255, 255, 255), 1)                           
            cv2.rectangle(frame, (100, y - 18), (100 + bar, y + 2), (0, 200, 255), -1)                      
            cv2.putText(frame, NAMES[i], (10, y), FONT, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"{int(curls[i])}", (375, y), FONT, 0.6, (150, 150, 150), 2)

        hand_amount = [
            smooth[0],
            smooth[1],
            smooth[2],
            (smooth[3] + smooth[4]) / 2,                                        # 5 fingers -> 4 servos: ring and pinky share one servo
        ]

        angles = []
        for s in range(4):
            angle = SERVO_OPEN[s] + hand_amount[s] * (SERVO_CLOSED[s] - SERVO_OPEN[s])                      # linear interpolation between the calibrated servo angles
            angles.append(int(angle))

        cv2.putText(frame, f"Servo: {angles}", (10, 215), FONT, 0.6, (0, 255, 0), 2)

        changed = False
        for s in range(4):
            if abs(angles[s] - last_sent[s]) >= DEADBAND:
                changed = True

        if changed:
            if USE_ARDUINO:
                message = f"{angles[0]},{angles[1]},{angles[2]},{angles[3]}\n"
                arduino.write(message.encode())
            last_sent = angles
    
    else:

        # no hand: send nothing, so the robot holds its position

        cv2.putText(frame, "NO HAND", (10, 40), FONT, 1.2, (0, 0, 255), 3)

    cv2.rectangle(frame, (0, height - 40), (420, height), (0, 0, 0), -1)
    cv2.putText(frame, "o = open hand   c = fist   q = quit", (10, height - 15),
                FONT, 0.6, (255, 255, 0), 2)
    cv2.imshow("finger control", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    if key == ord('o') and curls:                                               
        open_curl = curls.copy()                                                
        print("Open hand saved:", [int(v) for v in open_curl])
    if key == ord('c') and curls:
        closed_curl = curls.copy()
        print("Fist saved:", [int(v) for v in closed_curl])

cap.release()
cv2.destroyAllWindows()
detector.close()

if USE_ARDUINO:
    arduino.write(b"0,0,0,0\n")
    time.sleep(0.5)
    arduino.close()
print("All fingers back to 0, bye!")
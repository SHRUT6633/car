#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — LOCALHOST LIVE CAMERA STREAMER WITH AUTO-SCANNER & RETRY ENGINE
======================================================================================
  1. Auto-scans all camera backends (Picamera2, GStreamer, V4L2 devices 0..10, USB)
  2. Continuously retries until a LIVE camera feed IS RECEIVING!
  3. Once valid video frames are confirmed, launches the localhost web server on port 8080.
======================================================================================
"""
import os
import sys
import time
import json
import cv2
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Color ANSI formatting
COLOR_GREEN  = "\033[1;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED    = "\033[1;31m"
COLOR_CYAN   = "\033[1;36m"
COLOR_RESET  = "\033[0m"

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

latest_jpg = None
lock = threading.Lock()
active_cap = None
use_picam2 = False
picam2_obj = None

def find_active_camera():
    """Continuously scans all camera sources until a valid live frame is received."""
    global active_cap, use_picam2, picam2_obj
    
    print(f"\n{COLOR_CYAN}[CAM SCANNER] Starting Camera Pre-Check & Auto-Scanner...{COLOR_RESET}")
    scan_attempt = 1
    
    while True:
        print(f"{COLOR_YELLOW}[SCAN #{scan_attempt}] Searching for active camera feed...{COLOR_RESET}")
        
        # 1. Try Picamera2
        try:
            from picamera2 import Picamera2
            print(f"  --> Testing Picamera2 (Native Pi CSI)...")
            p2 = Picamera2()
            cfg = p2.create_preview_configuration(main={"size": (640, 480)})
            p2.configure(cfg)
            p2.start()
            time.sleep(0.3)
            test_frame = p2.capture_array()
            if test_frame is not None and test_frame.size > 0:
                print(f"{COLOR_GREEN}[SUCCESS] Connected to Picamera2 (Native Pi CSI Camera)!{COLOR_RESET}")
                use_picam2 = True
                picam2_obj = p2
                return
            p2.stop()
        except Exception as e:
            pass

        # 2. Try GStreamer libcamera pipelines
        gst_pipelines = [
            "libcamerasrc ! video/x-raw, width=640, height=480, framerate=30/1 ! videoconvert ! videoscale ! appsink drop=true",
            "v4l2src device=/dev/video0 ! video/x-raw, width=640, height=480 ! videoconvert ! appsink drop=true"
        ]
        for gst_str in gst_pipelines:
            try:
                print(f"  --> Testing GStreamer pipeline...")
                cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"{COLOR_GREEN}[SUCCESS] Connected via GStreamer libcamera pipeline!{COLOR_RESET}")
                        active_cap = cap
                        return
                    cap.release()
            except Exception:
                pass

        # 3. Try V4L2 / USB device indices (0..10)
        for idx in [0, 1, 2, 4, 10]:
            try:
                print(f"  --> Testing V4L2 device /dev/video{idx}...")
                cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(idx)
                    
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"{COLOR_GREEN}[SUCCESS] Connected to /dev/video{idx}!{COLOR_RESET}")
                        active_cap = cap
                        return
                    cap.release()
            except Exception:
                pass

        print(f"{COLOR_RED}[WARNING] No active camera feed received on scan #{scan_attempt}. Retrying in 2s...{COLOR_RESET}")
        time.sleep(2.0)
        scan_attempt += 1

def video_processor_thread():
    global latest_jpg
    from layers.layer4_perception import ThreadedCameraManager
    
    cam_mgr = ThreadedCameraManager(config)
    print(f"{COLOR_GREEN}[PERCEPTION ENGINE] Video perception thread running @ 30 FPS...{COLOR_RESET}")
    
    while True:
        frame = None
        if use_picam2 and picam2_obj:
            try:
                frame_rgb = picam2_obj.capture_array()
                frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            except Exception:
                frame = None
        elif active_cap and active_cap.isOpened():
            ret, frame = active_cap.read()
            if not ret:
                frame = None

        if frame is None:
            time.sleep(0.03)
            continue
            
        perc = cam_mgr.process_frame(frame)
        debug_frame = frame.copy()
        
        # Draw bounding boxes & telemetry on video feed
        if perc.get("red_pillar"):
            r = perc["red_pillar"]
            x, y, w, h = r['bbox']
            cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
            cv2.putText(debug_frame, f"RED: {r['distance_est_mm']}mm", (x, max(20, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        
        if perc.get("green_pillar"):
            g = perc["green_pillar"]
            x, y, w, h = g['bbox']
            cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(debug_frame, f"GREEN: {g['distance_est_mm']}mm", (x, max(20, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        if perc.get("magenta_block"):
            m = perc["magenta_block"]
            x, y, w, h = m['bbox']
            cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (255, 0, 255), 3)
            cv2.putText(debug_frame, f"MAGENTA: {m['distance_est_mm']}mm", (x, max(20, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

        ret_jpeg, jpeg = cv2.imencode('.jpg', debug_frame)
        if ret_jpeg:
            with lock:
                latest_jpg = jpeg.tobytes()
                
        time.sleep(0.03)

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>WRO 2026 — Localhost Camera Stream</title>
                <style>
                    body { background: #0f172a; color: #f8fafc; font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 20px; }
                    h1 { color: #38bdf8; margin-bottom: 5px; }
                    .tag { background: #0284c7; padding: 5px 12px; border-radius: 20px; font-weight: bold; margin: 5px; display: inline-block; font-size: 14px; }
                    .container { margin-top: 15px; display: inline-block; background: #1e293b; padding: 15px; border-radius: 12px; border: 2px solid #38bdf8; }
                    img { border-radius: 8px; width: 640px; height: 480px; max-width: 100%; }
                </style>
            </head>
            <body>
                <h1>WRO 2026 Camera Perception Stream</h1>
                <div class="tag">Status: CAMERA FEED OK</div>
                <div class="tag">Resolution: 640x480</div>
                <div class="tag">FPS: 30</div>
                <br>
                <div class="container">
                    <img src="/stream" />
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                with lock:
                    if latest_jpg is None:
                        time.sleep(0.05)
                        continue
                    frame_data = latest_jpg
                try:
                    self.wfile.write(b"--jpgboundary\r\n")
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', str(len(frame_data)))
                    self.end_headers()
                    self.wfile.write(frame_data)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.033)
                except Exception:
                    break

def main():
    # Pre-check: Continuously find & confirm valid camera feed BEFORE starting server
    find_active_camera()
    
    # Start video processing thread
    t = threading.Thread(target=video_processor_thread, daemon=True)
    t.start()
    
    port = 8080
    server = HTTPServer(('0.0.0.0', port), WebHandler)
    print("\n=======================================================================")
    print(f"  {COLOR_GREEN}LOCALHOST CAMERA STREAM ACTIVE: http://localhost:{port}{COLOR_RESET}")
    print(f"  Open http://<PI_IP_ADDRESS>:{port} in your PC browser!")
    print("=======================================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LOCALHOST CAM] Stopping server...")
        if active_cap:
            active_cap.release()
        if picam2_obj:
            picam2_obj.stop()

if __name__ == '__main__':
    main()

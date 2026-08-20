#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — LOCALHOST LIVE CAMERA STREAMER (Native Picamera2 / OV5647 Driver)
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

COLOR_GREEN  = "\033[1;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED    = "\033[1;31m"
COLOR_CYAN   = "\033[1;36m"
COLOR_RESET  = "\033[0m"

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

latest_jpg = None
lock = threading.Lock()
picam2_obj = None

def init_native_camera():
    global picam2_obj
    print(f"\n{COLOR_CYAN}[CAM DRIVER] Initializing Native Picamera2 (OV5647)...{COLOR_RESET}")
    
    # 1. Try Picamera2 native libcamera API
    try:
        from picamera2 import Picamera2
        p2 = Picamera2()
        cfg = p2.create_preview_configuration(main={"size": (640, 480)})
        p2.configure(cfg)
        p2.start()
        time.sleep(0.5)
        print(f"{COLOR_GREEN}[SUCCESS] Connected to OV5647 CSI Camera via Picamera2!{COLOR_RESET}")
        picam2_obj = p2
        return True
    except Exception as e:
        print(f"{COLOR_YELLOW}[WARNING] Picamera2 direct init: {e}. Trying V4L2 fallback...{COLOR_RESET}")

    # 2. V4L2 Fallback
    for idx in [0, 1, 2, 4]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"{COLOR_GREEN}[SUCCESS] Connected to /dev/video{idx} via V4L2!{COLOR_RESET}")
                picam2_obj = cap
                return True
            cap.release()
            
    print(f"{COLOR_RED}[ERROR] Could not capture frame from OV5647. Use: libcamerify python3 utils/camera_stream.py{COLOR_RESET}")
    return False

def video_processor_thread():
    global latest_jpg
    from layers.layer4_perception import ThreadedCameraManager
    cam_mgr = ThreadedCameraManager(config)
    
    while True:
        frame = None
        if picam2_obj:
            if hasattr(picam2_obj, 'capture_array'):
                try:
                    rgb_frame = picam2_obj.capture_array()
                    frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                except Exception:
                    frame = None
            elif hasattr(picam2_obj, 'read'):
                ret, frame = picam2_obj.read()
                if not ret:
                    frame = None

        if frame is None:
            time.sleep(0.03)
            continue
            
        perc = cam_mgr.process_frame(frame)
        debug_frame = frame.copy()
        
        # Draw detected pillars & telemetry
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
                <div class="tag">Sensor: OV5647 (30 FPS)</div>
                <div class="tag">Resolution: 640x480</div>
                <div class="tag">Status: LIVE</div>
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
    if not init_native_camera():
        sys.exit(1)
        
    t = threading.Thread(target=video_processor_thread, daemon=True)
    t.start()
    
    port = 8080
    server = HTTPServer(('0.0.0.0', port), WebHandler)
    print("\n=======================================================================")
    print(f"  {COLOR_GREEN}LOCALHOST CAMERA STREAM ACTIVE: http://localhost:{port}{COLOR_RESET}")
    print(f"  Open http://<PI_IP_ADDRESS>:{port} in Edge on your PC!")
    print("=======================================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LOCALHOST CAM] Stopping server...")
        if picam2_obj and hasattr(picam2_obj, 'stop'):
            picam2_obj.stop()

if __name__ == '__main__':
    main()

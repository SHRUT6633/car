#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — LOCALHOST LIVE CAMERA & PERCEPTION WEB SERVER (Port 8080)
======================================================================================
  Starts an HTTP MJPEG video streaming server on localhost:8080.
  Open http://localhost:8080 in Chromium browser on your Raspberry Pi desktop,
  or http://<PI_IP_ADDRESS>:8080 on any PC/phone connected to your WiFi network!
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
from layers.layer4_perception import ThreadedCameraManager

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

cam_manager = ThreadedCameraManager(config)
latest_jpg = None
lock = threading.Lock()

def video_processor_thread():
    global latest_jpg
    print("[LOCALHOST CAM] Perception processing active...")
    while True:
        if not cam_manager.cap or not cam_manager.cap.isOpened():
            time.sleep(0.05)
            continue
            
        ret, frame = cam_manager.cap.read()
        if not ret or frame is None:
            time.sleep(0.03)
            continue
            
        perc = cam_manager.process_frame(frame)
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
                <div class="tag">http://localhost:8080</div>
                <div class="tag">FPS: 30</div>
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
    t = threading.Thread(target=video_processor_thread, daemon=True)
    t.start()
    
    port = 8080
    server = HTTPServer(('0.0.0.0', port), WebHandler)
    print("\n=======================================================================")
    print(f"  LOCALHOST CAMERA STREAM READY: http://localhost:{port}")
    print(f"  Open http://localhost:{port} in Chromium browser on Raspberry Pi!")
    print("=======================================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LOCALHOST CAM] Stopping server...")
        cam_manager.stop()

if __name__ == '__main__':
    main()

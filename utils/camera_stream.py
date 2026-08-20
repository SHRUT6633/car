#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — LIVE CAMERA STREAM & DIAGNOSTIC WEB / TERMINAL DASHBOARD
======================================================================================
  Starts a lightweight HTTP MJPEG video stream on port 8080.
  Open http://<RASPBERRY_PI_IP>:8080 in any web browser (PC or phone) to view:
   1. Live Camera Feed with Object Detection Overlays (Red/Green Pillars)
   2. Live HSV Perception Mask Thresholding
   3. Terminal ASCII Art Frame Preview
======================================================================================
"""
import os
import sys
import time
import json
import cv2
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import threading

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from layers.layer4_perception import ColorPerceptionPipeline

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

pipeline = ColorPerceptionPipeline(config)
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

latest_frame_jpg = None
frame_lock = threading.Lock()

def ascii_preview(frame_bgr, width=60, height=20):
    """Renders a low-res ASCII representation of the camera frame for terminal."""
    chars = " .:-=+*#%@"
    resized = cv2.resize(frame_bgr, (width, height))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    lines = []
    for row in gray:
        line = "".join([chars[min(int(pixel / 25.5), 9)] for pixel in row])
        lines.append(line)
    return "\n".join(lines)

def capture_worker():
    global latest_frame_jpg
    print("[CAM STREAM] Starting camera acquisition loop...")
    while True:
        ret, frame = camera.read()
        if not ret:
            time.sleep(0.03)
            continue
        
        # Run perception pipeline
        results, debug_frame = pipeline.process(frame)
        
        # Draw status overlay
        cv2.putText(debug_frame, f"Pillars Detected: {len(results['pillars'])}", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        for p in results['pillars']:
            color_bgr = (0, 0, 255) if p['color'] == 'RED' else (0, 255, 0)
            cv2.rectangle(debug_frame, (p['bbox'][0], p['bbox'][1]),
                          (p['bbox'][0] + p['bbox'][2], p['bbox'][1] + p['bbox'][3]), color_bgr, 2)
            cv2.putText(debug_frame, f"{p['color']} ({p['distance_cm']}cm)",
                        (p['bbox'][0], max(10, p['bbox'][1] - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)
            
        ret_jpeg, jpeg = cv2.imencode('.jpg', debug_frame)
        if ret_jpeg:
            with frame_lock:
                latest_frame_jpg = jpeg.tobytes()
                
        time.sleep(0.03)

class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>WRO 2026 — Live Camera & Perception Stream</title>
                <style>
                    body { background: #0f172a; color: #f8fafc; font-family: monospace; text-align: center; margin: 0; padding: 20px; }
                    h1 { color: #38bdf8; }
                    .card { background: #1e293b; border-radius: 12px; padding: 20px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
                    img { border-radius: 8px; border: 2px solid #38bdf8; max-width: 100%; height: auto; }
                    .badge { background: #0284c7; padding: 6px 12px; border-radius: 20px; font-weight: bold; margin: 5px; display: inline-block; }
                </style>
            </head>
            <body>
                <h1>WRO 2026 Camera Perception Feed</h1>
                <div class="badge">Port: 8080</div>
                <div class="badge">Resolution: 640x480</div>
                <div class="badge">Target FPS: 30</div>
                <br><br>
                <div class="card">
                    <img src="/mjpg" />
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/mjpg':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                with frame_lock:
                    if latest_frame_jpg is None:
                        time.sleep(0.05)
                        continue
                    frame = latest_frame_jpg
                try:
                    self.wfile.write(b"--jpgboundary\r\n")
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.033)
                except Exception:
                    break

def main():
    t = threading.Thread(target=capture_worker, daemon=True)
    t.start()
    
    port = 8080
    server = HTTPServer(('0.0.0.0', port), StreamHandler)
    print(f"\n=======================================================")
    print(f"  CAMERA STREAM ACTIVE: http://<PI_IP_ADDRESS>:{port}")
    print(f"=======================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[CAM STREAM] Stopping server...")
        camera.release()

if __name__ == '__main__':
    main()

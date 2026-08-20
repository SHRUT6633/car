#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — PRODUCTION LIVE CAMERA & PERCEPTION WEB SERVER (Port 8080)
======================================================================================
  Clean, production-grade HTTP MJPEG streaming server.
  Serves on 0.0.0.0:8080:
   - Access on Pi desktop:  http://localhost:8080
   - Access on PC/Phone:    http://<PI_IP_ADDRESS>:8080
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

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from layers.layer4_perception import ThreadedCameraManager

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

camera_mgr = ThreadedCameraManager(config)
latest_jpeg_bytes = None
stream_lock = threading.Lock()

def perception_render_loop():
    global latest_jpeg_bytes
    print("[CAM SERVER] Production perception rendering loop started.")
    
    while True:
        frame = camera_mgr.get_frame()
        perception_data = camera_mgr.process_frame()
        
        if frame is None:
            # Generate diagnostic frame if hardware camera is initializing or offline
            debug_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(debug_frame, "WRO 2026 PERCEPTION ENGINE", (100, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            cam_status = "INITIALIZING / SEARCHING FOR CAMERA..." if not camera_mgr.is_ready() else "WAITING FOR FRAME..."
            cv2.putText(debug_frame, cam_status, (80, 250),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            cv2.putText(debug_frame, f"Server: http://localhost:8080", (160, 320),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        else:
            debug_frame = frame.copy()
            
            # Draw detected pillars & telemetry
            if perception_data.get("red_pillar"):
                r = perception_data["red_pillar"]
                x, y, w, h = r['bbox']
                cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
                cv2.putText(debug_frame, f"RED: {r['distance_est_mm']}mm", (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                            
            if perception_data.get("green_pillar"):
                g = perception_data["green_pillar"]
                x, y, w, h = g['bbox']
                cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                cv2.putText(debug_frame, f"GREEN: {g['distance_est_mm']}mm", (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            if perception_data.get("magenta_block"):
                m = perception_data["magenta_block"]
                x, y, w, h = m['bbox']
                cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (255, 0, 255), 3)
                cv2.putText(debug_frame, f"MAGENTA: {m['distance_est_mm']}mm", (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

        # Draw header overlay
        cv2.putText(debug_frame, "WRO 2026 LIVE PERCEPTION", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        ret_jpeg, jpeg = cv2.imencode('.jpg', debug_frame)
        if ret_jpeg:
            with stream_lock:
                latest_jpeg_bytes = jpeg.tobytes()
                
        time.sleep(0.033) # ~30 FPS

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

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
                    body { background: #0f172a; color: #f8fafc; font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 20px; }
                    h1 { color: #38bdf8; margin-bottom: 5px; }
                    .badge { background: #0284c7; padding: 6px 14px; border-radius: 20px; font-weight: bold; margin: 5px; display: inline-block; font-size: 14px; }
                    .card { margin-top: 15px; display: inline-block; background: #1e293b; padding: 15px; border-radius: 12px; border: 2px solid #38bdf8; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
                    img { border-radius: 8px; width: 640px; height: 480px; max-width: 100%; }
                </style>
            </head>
            <body>
                <h1>WRO 2026 Camera Perception Stream</h1>
                <div class="badge">Port 8080</div>
                <div class="badge">FPS: 30</div>
                <div class="badge">Status: RUNNING</div>
                <br>
                <div class="card">
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
                with stream_lock:
                    if latest_jpeg_bytes is None:
                        time.sleep(0.05)
                        continue
                    frame_data = latest_jpeg_bytes
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
    render_thread = threading.Thread(target=perception_render_loop, daemon=True)
    render_thread.start()
    
    port = 8080
    server = ThreadingHTTPServer(('0.0.0.0', port), StreamHandler)
    print("\n=======================================================================")
    print("  WRO 2026 PRODUCTION CAMERA STREAM SERVER READY")
    print(f"  Local Access:   http://localhost:{port}")
    print(f"  Network Access: http://<PI_IP_ADDRESS>:{port}")
    print("=======================================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[CAM SERVER] Shutting down...")
        camera_mgr.stop()

if __name__ == '__main__':
    main()

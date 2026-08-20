#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — STANDALONE CAMERA & HSV COLOR PERCEPTION TESTER
======================================================================================
  Run this script to test your Raspberry Pi CSI / USB Camera independently:
    python3 test_camera.py

  It will:
   1. Initialize Picamera2 / OpenCV camera
   2. Print live color detection telemetry to terminal
   3. Serve live web camera preview on http://localhost:8080
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

sys.path.insert(0, os.path.dirname(__file__))
from layers.layer4_perception import ThreadedCameraManager

# Colors
COLOR_GREEN  = "\033[1;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED    = "\033[1;31m"
COLOR_CYAN   = "\033[1;36m"
COLOR_MAGENTA= "\033[1;35m"
COLOR_RESET  = "\033[0m"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "robot_config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

print("=" * 70)
print("   WRO 2026  ·  STANDALONE CAMERA PERCEPTION TESTER           ")
print("=" * 70)

print(f"{COLOR_CYAN}[TEST] Initializing Perception Layer...{COLOR_RESET}")
camera_mgr = ThreadedCameraManager(config)
time.sleep(1.0)

if not camera_mgr.is_ready():
    print(f"{COLOR_RED}[WARNING] Camera hardware initialization report: NOT READY!{COLOR_RESET}")
    print(f"{COLOR_YELLOW}[INFO] Will attempt software stream capture and web server fallback.{COLOR_RESET}")
else:
    print(f"{COLOR_GREEN}[SUCCESS] Camera Layer Initialized & Active!{COLOR_RESET}")

latest_jpeg_bytes = None
stream_lock = threading.Lock()

def test_telemetry_loop():
    global latest_jpeg_bytes
    frame_count = 0
    start_time = time.time()
    
    print(f"{COLOR_CYAN}[TEST] Starting Perception Telemetry Loop...{COLOR_RESET}\n")
    
    while True:
        frame = camera_mgr.get_frame()
        perception_data = camera_mgr.process_frame()
        frame_count += 1
        
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0.0
        
        red_info = "NONE"
        if perception_data.get("red_pillar"):
            r = perception_data["red_pillar"]
            red_info = f"{r['distance_est_mm']}mm (X:{r['center_x']})"
            
        green_info = "NONE"
        if perception_data.get("green_pillar"):
            g = perception_data["green_pillar"]
            green_info = f"{g['distance_est_mm']}mm (X:{g['center_x']})"

        magenta_info = "NONE"
        if perception_data.get("magenta_block"):
            m = perception_data["magenta_block"]
            magenta_info = f"{m['distance_est_mm']}mm"

        # Log to terminal every 15 frames (~0.5s)
        if frame_count % 15 == 0:
            status = "OK" if frame is not None else "WAITING"
            print(f"[{time.strftime('%H:%M:%S')}] Frame #{frame_count:04d} | Status: {status} | FPS: {fps:.1f} | "
                  f"Red: {COLOR_RED}{red_info}{COLOR_RESET} | Green: {COLOR_GREEN}{green_info}{COLOR_RESET} | Magenta: {COLOR_MAGENTA}{magenta_info}{COLOR_RESET}")

        if frame is None:
            debug_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(debug_frame, "CAMERA INITIALIZING / WAITING...", (80, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        else:
            debug_frame = frame.copy()
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

        cv2.putText(debug_frame, f"FPS: {fps:.1f}", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        ret_jpeg, jpeg = cv2.imencode('.jpg', debug_frame)
        if ret_jpeg:
            with stream_lock:
                latest_jpeg_bytes = jpeg.tobytes()
                
        time.sleep(0.033)

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
                <title>WRO 2026 — Camera Test Stream</title>
                <style>
                    body { background: #0f172a; color: #f8fafc; font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 20px; }
                    h1 { color: #38bdf8; margin-bottom: 5px; }
                    .badge { background: #0284c7; padding: 6px 14px; border-radius: 20px; font-weight: bold; margin: 5px; display: inline-block; font-size: 14px; }
                    .card { margin-top: 15px; display: inline-block; background: #1e293b; padding: 15px; border-radius: 12px; border: 2px solid #38bdf8; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
                    img { border-radius: 8px; width: 640px; height: 480px; max-width: 100%; }
                </style>
            </head>
            <body>
                <h1>WRO 2026 Camera Test Stream</h1>
                <div class="badge">Port 8080</div>
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
    t = threading.Thread(target=test_telemetry_loop, daemon=True)
    t.start()
    
    server = None
    active_port = 8080
    for try_port in [8080, 8081, 8082, 8085]:
        try:
            server = ThreadingHTTPServer(('0.0.0.0', try_port), StreamHandler)
            active_port = try_port
            break
        except OSError:
            pass

    print("\n=======================================================================")
    print(f"  {COLOR_GREEN}CAMERA TEST WEB SERVER ACTIVE: http://localhost:{active_port}{COLOR_RESET}")
    print(f"  Open http://<PI_IP_ADDRESS>:{active_port} in Edge on your PC!")
    print("=======================================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[TEST] Stopping camera tester...")
        camera_mgr.stop()

if __name__ == '__main__':
    main()

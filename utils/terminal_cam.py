#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — TERMINAL ASCII GUI LIVE CAMERA & PERCEPTION ENGINE
======================================================================================
  Renders a LIVE full-color ANSI / ASCII camera preview directly inside your
  SSH PowerShell / Linux terminal window!
  
  Shows:
   1. Live video frame rendered in terminal ANSI color blocks
   2. Detected Red Pillars (RED text/box), Green Pillars (GREEN text/box)
   3. Pillar Distances (mm) and centroid positions
   4. Frame rate & perception telemetry
======================================================================================
"""
import os
import sys
import time
import json
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from layers.layer4_perception import ThreadedCameraManager

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

# ANSI Color Codes
COLOR_RESET   = "\033[0m"
COLOR_RED     = "\033[1;31m"
COLOR_GREEN   = "\033[1;32m"
COLOR_YELLOW  = "\033[1;33m"
COLOR_CYAN    = "\033[1;36m"
COLOR_WHITE   = "\033[1;37m"
CLEAR_SCREEN  = "\033[H\033[J"

def frame_to_ascii(frame_bgr, width=72, height=22):
    """Converts a BGR image frame to ANSI 24-bit truecolor terminal string."""
    resized = cv2.resize(frame_bgr, (width, height))
    ascii_chars = " .:-=+*#%@"
    output_lines = []
    
    for y in range(height):
        line = ""
        for x in range(width):
            b, g, r = resized[y, x]
            gray = int(0.299 * r + 0.587 * g + 0.114 * b)
            char = ascii_chars[min(int(gray / 25.5), 9)]
            line += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
        output_lines.append(line)
        
    return "\n".join(output_lines)

def main():
    print("[TERMINAL CAM] Initializing Camera Engine...")
    cam = ThreadedCameraManager(config)
    time.sleep(0.5)
    
    if not cam.is_ready():
        print("\033[1;31m[ERROR] Camera hardware not responding!\033[0m")
        cam.stop()
        sys.exit(1)
        
    print("\033[2J") # Clear terminal
    
    try:
        while True:
            if not cam.cap or not cam.cap.isOpened():
                time.sleep(0.05)
                continue
                
            ret, frame = cam.cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue
                
            perc = cam.process_frame(frame)
            
            # Draw overlay indicator onto frame
            debug_frame = frame.copy()
            if perc.get("red_pillar"):
                r = perc["red_pillar"]
                cv2.rectangle(debug_frame, (r['bbox'][0], r['bbox'][1]),
                              (r['bbox'][0] + r['bbox'][2], r['bbox'][1] + r['bbox'][3]), (0, 0, 255), 3)
            if perc.get("green_pillar"):
                g = perc["green_pillar"]
                cv2.rectangle(debug_frame, (g['bbox'][0], g['bbox'][1]),
                              (g['bbox'][0] + g['bbox'][2], g['bbox'][1] + g['bbox'][3]), (0, 255, 0), 3)
            
            # Render ASCII Frame
            ascii_img = frame_to_ascii(debug_frame, width=72, height=22)
            
            # Extract detected pillar data
            red_str = "NONE"
            if perc.get("red_pillar"):
                r = perc["red_pillar"]
                red_str = f"{COLOR_RED}RED @ {r['distance_est_mm']}mm (X:{r['center_x']}){COLOR_RESET}"
                
            green_str = "NONE"
            if perc.get("green_pillar"):
                g = perc["green_pillar"]
                green_str = f"{COLOR_GREEN}GREEN @ {g['distance_est_mm']}mm (X:{g['center_x']}){COLOR_RESET}"
                
            mag_str = "NONE"
            if perc.get("magenta_block"):
                m = perc["magenta_block"]
                mag_str = f"\033[1;35mMAGENTA @ {m['distance_est_mm']}mm{COLOR_RESET}"
                
            # Build GUI Header Box
            gui = f"{CLEAR_SCREEN}"
            gui += f"{COLOR_CYAN}╔══════════════════════════════════════════════════════════════════════════╗{COLOR_RESET}\n"
            gui += f"{COLOR_CYAN}║    WRO 2026 · LIVE TERMINAL CAMERA PERCEPTION GUI VIEW                   ║{COLOR_RESET}\n"
            gui += f"{COLOR_CYAN}╠══════════════════════════════════════════════════════════════════════════╣{COLOR_RESET}\n"
            gui += f"  Red Pillar:     {red_str}\n"
            gui += f"  Green Pillar:   {green_str}\n"
            gui += f"  Magenta Block:  {mag_str}\n"
            gui += f"{COLOR_CYAN}╠══════════════════════════════════════════════════════════════════════════╣{COLOR_RESET}\n"
            gui += f"{ascii_img}\n"
            gui += f"{COLOR_CYAN}╚══════════════════════════════════════════════════════════════════════════╝{COLOR_RESET}\n"
            gui += f"{COLOR_YELLOW}Press Ctrl+C to exit terminal viewer{COLOR_RESET}\n"
            
            sys.stdout.write(gui)
            sys.stdout.flush()
            time.sleep(0.04)
            
    except KeyboardInterrupt:
        print("\n\033[1;33m[TERMINAL CAM] Exiting viewer...\033[0m")
        cam.stop()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
======================================================================================
  WRO 2026 — TERMINAL ASCII GUI LIVE CAMERA & PERCEPTION ENGINE (Flicker-Free)
======================================================================================
"""
import os
import sys
import time
import json
import shutil
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from layers.layer4_perception import ThreadedCameraManager

with open("config/robot_config.json", "r") as f:
    config = json.load(f)

COLOR_RESET   = "\033[0m"
COLOR_RED     = "\033[1;31m"
COLOR_GREEN   = "\033[1;32m"
COLOR_YELLOW  = "\033[1;33m"
COLOR_CYAN    = "\033[1;36m"
COLOR_MAGENTA = "\033[1;35m"
CURSOR_HOME   = "\033[H"

def frame_to_ascii(frame_bgr, width=54, height=14):
    """Converts a BGR image frame to ANSI truecolor block strings."""
    resized = cv2.resize(frame_bgr, (width, height))
    ascii_chars = " .:-=+*#%@"
    output_lines = []
    
    for y in range(height):
        line = "  "
        for x in range(width):
            b, g, r = resized[y, x]
            gray = int(0.299 * r + 0.587 * g + 0.114 * b)
            char = ascii_chars[min(int(gray / 25.5), 9)]
            line += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
        output_lines.append(line)
        
    return "\n".join(output_lines)

def main():
    print("[TERMINAL CAM] Initializing Camera...")
    cam = ThreadedCameraManager(config)
    time.sleep(0.5)
    
    # Clear screen once on start
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    
    try:
        while True:
            frame = cam.get_frame()
            perc = cam.process_frame()
            
            if frame is None:
                debug_frame = np.zeros((240, 320, 3), dtype=np.uint8)
                cv2.putText(debug_frame, "SEARCHING CAMERA...", (40, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            else:
                debug_frame = frame.copy()
                if perc.get("red_pillar"):
                    r = perc["red_pillar"]
                    cv2.rectangle(debug_frame, (r['bbox'][0], r['bbox'][1]),
                                  (r['bbox'][0] + r['bbox'][2], r['bbox'][1] + r['bbox'][3]), (0, 0, 255), 4)
                if perc.get("green_pillar"):
                    g = perc["green_pillar"]
                    cv2.rectangle(debug_frame, (g['bbox'][0], g['bbox'][1]),
                                  (g['bbox'][0] + g['bbox'][2], g['bbox'][1] + g['bbox'][3]), (0, 255, 0), 4)
            
            # Get terminal dimensions
            term_cols, term_lines = shutil.get_terminal_size((80, 24))
            cam_w = min(60, term_cols - 4)
            cam_h = min(14, term_lines - 8)
            
            # Render ASCII Frame
            ascii_img = frame_to_ascii(debug_frame, width=cam_w, height=cam_h)
            
            # Target Data Strings
            red_str = "NONE     "
            if perc.get("red_pillar"):
                r = perc["red_pillar"]
                red_str = f"{COLOR_RED}RED @ {r['distance_est_mm']}mm (X:{r['center_x']}){COLOR_RESET}  "
                
            green_str = "NONE     "
            if perc.get("green_pillar"):
                g = perc["green_pillar"]
                green_str = f"{COLOR_GREEN}GREEN @ {g['distance_est_mm']}mm (X:{g['center_x']}){COLOR_RESET}  "
                
            # Build Compact GUI
            gui = f"{CURSOR_HOME}"
            gui += f"{COLOR_CYAN}── WRO 2026 LIVE TERMINAL CAMERA PERCEPTION GUI ──{COLOR_RESET}\n"
            gui += f"  Red:   {red_str}\n"
            gui += f"  Green: {green_str}\n"
            gui += f"─────────────────────────────────────────────────\n"
            gui += f"{ascii_img}\n"
            gui += f"─────────────────────────────────────────────────\n"
            gui += f"{COLOR_YELLOW}Press Ctrl+C to exit{COLOR_RESET}\n"
            
            sys.stdout.write(gui)
            sys.stdout.flush()
            time.sleep(0.04)
            
    except KeyboardInterrupt:
        print("\n\033[1;33m[TERMINAL CAM] Exiting viewer...\033[0m")
        cam.stop()

if __name__ == '__main__':
    main()

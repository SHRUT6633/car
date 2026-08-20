import time
import logging
import threading
import math
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("[LAYER 4] OpenCV not available.")

try:
    from picamera2 import Picamera2
    PICAM2_AVAILABLE = True
except ImportError:
    PICAM2_AVAILABLE = False

class ThreadedCameraManager:
    """
    Layer 4: Async Multi-Threaded Camera Ingestion & Perception Engine
    Spawns background thread to continuously capture frames at 30 FPS.
    Applies high-precision HSV thresholding and contour shape filtering (circularity and aspect ratio)
    to detect red/green pillars and magenta parking lot limiters.
    """
    def __init__(self, config: dict):
        self.config = config
        self.cam_config = config.get("camera", {})
        
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread = None

        self.cap = None
        self.latest_perception = {
            "red_pillar": None,
            "green_pillar": None,
            "magenta_block": None,
            "blue_marker": False,
            "frame_processed": False,
            "camera_ok": False
        }

        if CV2_AVAILABLE:
            self._init_camera()
            self.start_thread()

    def _init_camera(self):
        try:
            # 0. Try Picamera2 (Native Raspberry Pi OS libcamera interface)
            if PICAM2_AVAILABLE:
                try:
                    self.picam2 = Picamera2()
                    config = self.picam2.create_preview_configuration(main={"size": (640, 480)})
                    self.picam2.configure(config)
                    self.picam2.start()
                    logging.info("[LAYER 4] Picamera2 Native Stream Active.")
                    self.latest_perception["camera_ok"] = True
                    return
                except Exception as p_err:
                    logging.warning(f"[LAYER 4] Picamera2 init warning: {p_err}")
                    self.picam2 = None

            # 1. Try GStreamer libcamera pipeline
            gstreamer_pipelines = [
                "libcamerasrc ! video/x-raw, width=640, height=480, framerate=30/1 ! videoconvert ! videoscale ! appsink drop=true",
                "v4l2src device=/dev/video0 ! video/x-raw, width=640, height=480 ! videoconvert ! appsink drop=true"
            ]
            for gst_str in gstreamer_pipelines:
                try:
                    cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
                    if cap.isOpened():
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            self.cap = cap
                            logging.info("[LAYER 4] OpenCV GStreamer libcamera stream active.")
                            self.latest_perception["camera_ok"] = True
                            return
                        else:
                            cap.release()
                except Exception:
                    pass

            # 2. Try V4L2 device indices
            device_idx = self.cam_config.get("device_index", 0)
            indices_to_try = [device_idx, 0, 1, 2, 4, 10]
            indices_to_try = list(dict.fromkeys(indices_to_try))
            
            for idx in indices_to_try:
                cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(idx)
                    
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        self.cap = cap
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cam_config.get("frame_width", 640))
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_config.get("frame_height", 480))
                        self.cap.set(cv2.CAP_PROP_FPS, self.cam_config.get("fps", 30))
                        logging.info(f"[LAYER 4] OpenCV Camera Ingestion Active on device index {idx}.")
                        self.latest_perception["camera_ok"] = True
                        return
                    else:
                        cap.release()
            logging.warning("[LAYER 4] Could not find an active camera stream on indices 0..10.")
        except Exception as e:
            logging.error(f"[LAYER 4] Camera Init Error: {e}")

    def start_thread(self):
        has_picam2 = hasattr(self, 'picam2') and self.picam2 is not None
        has_cap = self.cap and self.cap.isOpened()
        if has_picam2 or has_cap:
            self.running = True
            self.worker_thread = threading.Thread(target=self._async_camera_loop, daemon=True)
            self.worker_thread.start()
            logging.info("[LAYER 4] Async Perception Thread Spawned.")

    def _async_camera_loop(self):
        """Background Thread: Image processing loop @ 30 FPS."""
        while self.running:
            frame = None
            if hasattr(self, 'picam2') and self.picam2 is not None:
                try:
                    frame_rgb = self.picam2.capture_array()
                    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                except Exception:
                    frame = None
            elif self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    frame = None

            if frame is None:
                time.sleep(0.02)
                continue

            perception_res = self._process_frame_internal(frame)
            perception_res["camera_ok"] = True

            with self.lock:
                self.latest_frame = frame.copy()
                self.latest_perception = perception_res

            time.sleep(0.01)

    def get_frame(self):
        """Thread-safe access to latest raw camera frame."""
        with self.lock:
            return self.latest_frame.copy() if hasattr(self, 'latest_frame') and self.latest_frame is not None else None

    def _process_frame_internal(self, frame) -> dict:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        img_h, img_w = frame.shape[:2]

        # 1. Red Pillars
        r1_low = np.array(self.cam_config.get("hsv_red1", {}).get("low", [0, 120, 70]))
        r1_high = np.array(self.cam_config.get("hsv_red1", {}).get("high", [10, 255, 255]))
        r2_low = np.array(self.cam_config.get("hsv_red2", {}).get("low", [170, 120, 70]))
        r2_high = np.array(self.cam_config.get("hsv_red2", {}).get("high", [180, 255, 255]))

        mask_r1 = cv2.inRange(hsv, r1_low, r1_high)
        mask_r2 = cv2.inRange(hsv, r2_low, r2_high)
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)
        red_res = self._find_target_contour(mask_red, img_w, img_h, target_type="pillar")

        # 2. Green Pillars
        g_low = np.array(self.cam_config.get("hsv_green", {}).get("low", [36, 100, 80]))
        g_high = np.array(self.cam_config.get("hsv_green", {}).get("high", [85, 255, 255]))
        mask_green = cv2.inRange(hsv, g_low, g_high)
        green_res = self._find_target_contour(mask_green, img_w, img_h, target_type="pillar")

        # 3. Magenta Stop/Parking Blocks (RGB 255,0,255 -> HSV H: 140-170)
        m_low = np.array(self.cam_config.get("hsv_magenta", {}).get("low", [140, 100, 50]))
        m_high = np.array(self.cam_config.get("hsv_magenta", {}).get("high", [170, 255, 255]))
        mask_magenta = cv2.inRange(hsv, m_low, m_high)
        magenta_res = self._find_target_contour(mask_magenta, img_w, img_h, target_type="block")

        # 4. Blue Stop-and-Go Marker
        b_low = np.array(self.cam_config.get("hsv_blue", {}).get("low", [95, 120, 80]))
        b_high = np.array(self.cam_config.get("hsv_blue", {}).get("high", [130, 255, 255]))
        mask_blue = cv2.inRange(hsv[int(img_h * 0.7):, :], b_low, b_high)
        blue_marker = (cv2.countNonZero(mask_blue) > 800)

        return {
            "red_pillar": red_res,
            "green_pillar": green_res,
            "magenta_block": magenta_res,
            "blue_marker": blue_marker,
            "frame_processed": True
        }

    def _find_target_contour(self, mask, img_w, img_h, target_type="pillar") -> dict:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
            
        valid_candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 300:
                continue
                
            x, y, w, h = cv2.boundingRect(c)
            perimeter = cv2.arcLength(c, True)
            
            # Calculate shape metrics
            circularity = (4.0 * math.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0
            aspect_ratio = float(w) / float(h) if h > 0 else 9999.0
            
            # Perform strict shape filtering
            if target_type == "pillar":
                # Pillars are round cylinders, projected as narrow tall shapes.
                # Circularity is moderately high, aspect ratio should be tall (aspect_ratio < 1.3)
                if circularity >= 0.35 and aspect_ratio < 1.3:
                    valid_candidates.append((c, area, x, y, w, h))
            elif target_type == "block":
                # Parking blocks are flat horizontal wood limiters.
                # Circularity is low, aspect ratio should be wider (aspect_ratio > 1.2)
                if aspect_ratio > 1.1:
                    valid_candidates.append((c, area, x, y, w, h))
                    
        if not valid_candidates:
            return None
            
        # Select largest candidate
        largest = max(valid_candidates, key=lambda x: x[1])
        c, area, x, y, w, h = largest
        
        cx = x + (w // 2)
        
        # Focal length calibration distance estimation (mm)
        # d = (FocalLength * RealObjectDimension) / PixelDimension
        focal_length = self.cam_config.get("focal_length_px", 600.0)
        
        if target_type == "pillar":
            # Pillar is 150mm tall (or wide)
            dist_est_mm = (focal_length * 150.0) / float(h) if h > 0 else 9999.0
        else:
            # Magenta block is 200mm long
            dist_est_mm = (focal_length * 200.0) / float(w) if w > 0 else 9999.0

        return {
            "center_x": cx,
            "normalized_x": (cx - (img_w / 2.0)) / (img_w / 2.0),
            "area": area,
            "bbox": (x, y, w, h),
            "distance_est_mm": round(dist_est_mm, 1)
        }

    def process_frame(self, frame=None) -> dict:
        """Instant lock-free access to latest background perception data."""
        with self.lock:
            return dict(self.latest_perception)

    def is_ready(self) -> bool:
        """Returns True if the camera initialized successfully."""
        with self.lock:
            return self.latest_perception.get("camera_ok", False)

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

class PerceptionLayer(ThreadedCameraManager):
    """Layer 4 Interface backwards compatibility alias."""
    pass

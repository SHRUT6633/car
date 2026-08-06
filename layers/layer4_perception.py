import numpy as np
import logging

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("[LAYER 4] OpenCV not available. Mocking visual perception.")

class PerceptionLayer:
    """
    Layer 4: Environment Perception
    Detects Red/Green Pillars, Blue Stop-and-Go floor markers, and Free Space corridor bounds.
    """
    def __init__(self, config: dict):
        self.config = config
        self.cam_config = config.get("camera", {})

    def process_frame(self, frame=None) -> dict:
        result = {
            "red_pillar": None,    # {"center_x": int, "area": int, "distance_est_mm": float}
            "green_pillar": None,  # {"center_x": int, "area": int, "distance_est_mm": float}
            "blue_marker": False,  # Stop-and-go marker boolean
            "frame_processed": False
        }

        if not CV2_AVAILABLE or frame is None:
            return result

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        img_h, img_w = frame.shape[:2]

        # 1. Detect Red Pillars
        r1_low = np.array(self.cam_config.get("hsv_red1", {}).get("low", [0, 120, 70]))
        r1_high = np.array(self.cam_config.get("hsv_red1", {}).get("high", [10, 255, 255]))
        r2_low = np.array(self.cam_config.get("hsv_red2", {}).get("low", [170, 120, 70]))
        r2_high = np.array(self.cam_config.get("hsv_red2", {}).get("high", [180, 255, 255]))

        mask_r1 = cv2.inRange(hsv, r1_low, r1_high)
        mask_r2 = cv2.inRange(hsv, r2_low, r2_high)
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)
        result["red_pillar"] = self._find_largest_contour(mask_red, img_w, img_h)

        # 2. Detect Green Pillars
        g_low = np.array(self.cam_config.get("hsv_green", {}).get("low", [36, 100, 80]))
        g_high = np.array(self.cam_config.get("hsv_green", {}).get("high", [85, 255, 255]))
        mask_green = cv2.inRange(hsv, g_low, g_high)
        result["green_pillar"] = self._find_largest_contour(mask_green, img_w, img_h)

        # 3. Detect Blue Stop-and-Go Marker (Bottom 30% region of interest)
        b_low = np.array(self.cam_config.get("hsv_blue", {}).get("low", [95, 120, 80]))
        b_high = np.array(self.cam_config.get("hsv_blue", {}).get("high", [130, 255, 255]))
        mask_blue = cv2.inRange(hsv[int(img_h * 0.7):, :], b_low, b_high)
        blue_pixels = cv2.countNonZero(mask_blue)
        if blue_pixels > 800:
            result["blue_marker"] = True

        result["frame_processed"] = True
        return result

    def _find_largest_contour(self, mask, img_w, img_h) -> dict:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < 300:  # Min noise threshold
            return None
        
        x, y, w, h = cv2.boundingRect(largest)
        cx = x + (w // 2)
        # Approximate distance via height geometry
        dist_est_mm = (img_h * 150.0) / float(h) if h > 0 else 9999.0

        return {
            "center_x": cx,
            "normalized_x": (cx - (img_w / 2.0)) / (img_w / 2.0), # [-1.0 to 1.0]
            "area": area,
            "bbox": (x, y, w, h),
            "distance_est_mm": round(dist_est_mm, 1)
        }

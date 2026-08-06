import time
import logging

class MissionManagerLayer:
    """
    Layer 6: Mission Manager & State Machine
    Handles mission progression, lap count, and implements the WRO 2026 Rule 6 Surprise Rules Adapter.
    """
    def __init__(self, config: dict):
        self.config = config
        self.surprise_cfg = config.get("surprise_rules", {})

        # State Machine States
        self.state = "INIT"
        self.lap_count = 0
        self.max_laps = 3
        self.lap_start_time = time.time()
        
        # Stop and Go Timer
        self.stop_and_go_triggered = False
        self.stop_start_time = 0.0

        # Surprise Rule Parameters
        self.sign_logic = self.surprise_cfg.get("SIGN_LOGIC", "NORMAL")  # NORMAL or REVERSED
        self.direction = self.surprise_cfg.get("DRIVING_DIRECTION", "CCW")
        self.narrow_mode = self.surprise_cfg.get("NARROW_TRACK_MODE", False)
        self.emergency_dist = self.surprise_cfg.get("EMERGENCY_BRAKE_DIST_MM", 180)

        logging.info(f"[LAYER 6] Mission Manager Loaded. Sign Logic: {self.sign_logic} | Direction: {self.direction} | Narrow Mode: {self.narrow_mode}")

    def update_state(self, perception: dict, sensors: dict, localization: dict) -> dict:
        front_dist = sensors.get("front_mm", 1000.0)
        blue_marker = perception.get("blue_marker", False)
        red_pillar = perception.get("red_pillar", None)
        green_pillar = perception.get("green_pillar", None)

        # 1. Emergency Braking Rule Check (Judge moving obstacle test)
        if front_dist > 0 and front_dist < self.emergency_dist and self.state != "EMERGENCY_BRAKE":
            logging.warning(f"[LAYER 6] EMERGENCY BRAKE TRIGGERED! Obstacle at {front_dist} mm.")
            self.state = "EMERGENCY_BRAKE"

        # 2. State Machine Transitions
        if self.state == "INIT":
            self.state = "RUNNING"
            self.lap_start_time = time.time()

        elif self.state == "RUNNING":
            # Check Stop-and-Go Blue Marker
            if blue_marker and self.surprise_cfg.get("STOP_AND_GO_ENABLED", True) and not self.stop_and_go_triggered:
                logging.info("[LAYER 6] Blue Stop-and-Go Marker detected! Initiating 3.0s pause.")
                self.state = "STOP_AND_GO"
                self.stop_start_time = time.time()
                self.stop_and_go_triggered = True

            elif red_pillar is not None or green_pillar is not None:
                self.state = "AVOIDING_PILLAR"

        elif self.state == "STOP_AND_GO":
            elapsed = time.time() - self.stop_start_time
            if elapsed >= self.surprise_cfg.get("STOP_DURATION_SEC", 3.0):
                logging.info("[LAYER 6] Stop-and-Go complete. Resuming lap.")
                self.state = "RUNNING"

        elif self.state == "AVOIDING_PILLAR":
            if red_pillar is None and green_pillar is None:
                self.state = "RUNNING"

        elif self.state == "EMERGENCY_BRAKE":
            if front_dist > self.emergency_dist + 100:
                logging.info("[LAYER 6] Emergency obstacle cleared. Resuming.")
                self.state = "RUNNING"

        # 3. Determine Pillar Avoidance Offset Direction based on SIGN_LOGIC
        avoidance_offset = 0.0 # [-1.0 (Left offset) to +1.0 (Right offset)]
        
        # Rule Logic:
        # NORMAL: Green -> Pass on Left (offset to Right), Red -> Pass on Right (offset to Left)
        # REVERSED (Surprise Rule): Green -> Pass on Right, Red -> Pass on Left
        is_reversed = (self.sign_logic.upper() == "REVERSED")

        if green_pillar is not None:
            norm_x = green_pillar["normalized_x"]
            # Pass Green
            avoidance_offset = -0.6 if is_reversed else 0.6

        elif red_pillar is not None:
            norm_x = red_pillar["normalized_x"]
            # Pass Red
            avoidance_offset = 0.6 if is_reversed else -0.6

        return {
            "state": self.state,
            "lap_count": self.lap_count,
            "avoidance_offset": avoidance_offset,
            "sign_logic": self.sign_logic,
            "narrow_mode": self.narrow_mode,
            "emergency_stop": (self.state == "EMERGENCY_BRAKE" or self.state == "STOP_AND_GO")
        }

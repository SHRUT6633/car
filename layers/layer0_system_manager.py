import time
import json
import logging
import threading
import os

class SystemManager:
    """
    Layer 0: System Manager
    Provides global scheduling, logging, configuration management, health monitoring,
    and performance diagnostic metrics.
    """
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self._setup_logger()
        
        self.running = False
        self.lock = threading.Lock()
        
        # Diagnostics & Health Metrics
        self.loop_counts = 0
        self.start_time = time.time()
        self.last_loop_time = time.time()
        self.loop_latencies = []
        self.health_status = {
            "sensors_ok": True,
            "camera_ok": True,
            "serial_ok": True,
            "battery_voltage": 11.1
        }

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        with open(self.config_path, "r") as f:
            return json.load(f)

    def reload_config(self):
        with self.lock:
            self.config = self._load_config()
            logging.info("[LAYER 0] Configuration reloaded dynamically.")

    def _setup_logger(self):
        log_level_str = self.config.get("system", {}).get("log_level", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] Layer %(module)s: %(message)s",
            datefmt="%H:%M:%S"
        )
        logging.info("[LAYER 0] System Manager Logging Initialized.")

    def update_performance(self):
        now = time.time()
        latency = (now - self.last_loop_time) * 1000.0  # ms
        self.last_loop_time = now
        self.loop_counts += 1
        
        self.loop_latencies.append(latency)
        if len(self.loop_latencies) > 100:
            self.loop_latencies.pop(0)

    def get_fps(self) -> float:
        elapsed = time.time() - self.start_time
        return self.loop_counts / elapsed if elapsed > 0 else 0.0

    def get_average_latency_ms(self) -> float:
        return sum(self.loop_latencies) / len(self.loop_latencies) if self.loop_latencies else 0.0

    def set_sensor_health(self, is_ok: bool):
        with self.lock:
            self.health_status["sensors_ok"] = is_ok

    def is_healthy(self) -> bool:
        with self.lock:
            return all(self.health_status.values())

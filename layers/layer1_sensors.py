import time
import logging

try:
    import board
    import busio
    from digitalio import DigitalInOut, Direction
    import adafruit_vl53l1x
    import adafruit_vl53l0x
    from mpu6050 import mpu6050
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError):
    HARDWARE_AVAILABLE = False
    logging.warning("[LAYER 1] Hardware libraries not loaded.")


class SensorLayer:
    """
    Layer 1: Sensor Calibration & Filtering (Strict Real Hardware Mode)
    Executes robust power-off I2C reset to eliminate address 0x29 bus contention.
    Applies median filtering and EMA smoothing to genuine live sensor feeds.
    """
    def __init__(self, config: dict):
        self.config = config
        self.hardware_active = HARDWARE_AVAILABLE

        self.FRONT_ADDR = 0x30
        self.LEFT_ADDR  = 0x31
        self.RIGHT_ADDR = 0x32

        self.POWER_DELAY = 0.250
        self.ADDRESS_DELAY = 0.100

        self.front_sensor = None
        self.left_sensor = None
        self.right_sensor = None
        self.mpu = None

        # Filter buffers
        self.front_history = []
        self.left_history = []
        self.right_history = []
        self.filter_window = 5
        self.ema_alpha = 0.35

        self.front_dist_mm = -1.0
        self.left_dist_mm = -1.0
        self.right_dist_mm = -1.0
        self.accel = {'x': 0.0, 'y': 0.0, 'z': 9.81}
        self.gyro  = {'x': 0.0, 'y': 0.0, 'z': 0.0}

        if self.hardware_active:
            self._init_hardware_sensors()
        else:
            raise RuntimeError("CRITICAL ERROR: Real hardware sensors required! Hardware libraries or I2C bus not available.")

    def _init_hardware_sensors(self):
        """Robust sequential I2C reset and re-addressing sequence."""
        try:
            logging.info("[LAYER 1] Initializing I2C Bus & XSHUT Reset...")
            i2c = busio.I2C(board.SCL, board.SDA)

            front_pin = DigitalInOut(board.D22)
            left_pin  = DigitalInOut(board.D17)
            right_pin = DigitalInOut(board.D27)

            # 1. HARD RESET: Power OFF all 3 VL53 sensors to clear 0x29 bus contention
            for p in (front_pin, left_pin, right_pin):
                p.direction = Direction.OUTPUT
                p.value = False

            time.sleep(self.POWER_DELAY)

            # 2. Sequential Power-On & Re-Addressing

            # A. FRONT VL53L1X
            front_pin.value = True
            time.sleep(self.POWER_DELAY)
            f_init = adafruit_vl53l1x.VL53L1X(i2c, address=0x29)
            f_init.set_address(self.FRONT_ADDR)
            time.sleep(self.ADDRESS_DELAY)

            # B. LEFT VL53L0X
            left_pin.value = True
            time.sleep(self.POWER_DELAY)
            l_init = adafruit_vl53l0x.VL53L0X(i2c, address=0x29)
            l_init.set_address(self.LEFT_ADDR)
            time.sleep(self.ADDRESS_DELAY)

            # C. RIGHT VL53L0X
            right_pin.value = True
            time.sleep(self.POWER_DELAY)
            r_init = adafruit_vl53l0x.VL53L0X(i2c, address=0x29)
            r_init.set_address(self.RIGHT_ADDR)
            time.sleep(self.ADDRESS_DELAY)

            logging.info("[LAYER 1] I2C Addresses assigned: Front 0x30, Left 0x31, Right 0x32.")

            # Bind sensor objects at their NEW re-assigned addresses
            self.front_sensor = adafruit_vl53l1x.VL53L1X(i2c, address=self.FRONT_ADDR)
            self.left_sensor  = adafruit_vl53l0x.VL53L0X(i2c, address=self.LEFT_ADDR)
            self.right_sensor = adafruit_vl53l0x.VL53L0X(i2c, address=self.RIGHT_ADDR)

            self.front_sensor.distance_mode = 1 # Short distance mode
            self.front_sensor.start_ranging()

            self.mpu = mpu6050(0x68)
            logging.info("[LAYER 1] All Physical Hardware Sensors Online & Streaming Real-Time!")
        except Exception as e:
            logging.error(f"[LAYER 1] Hardware Init Failure: {e}")
            raise e

    def _median_filter(self, val: float, history: list) -> float:
        if val <= 0 or val > 4000:
            return history[-1] if history else -1.0
        history.append(val)
        if len(history) > self.filter_window:
            history.pop(0)
        sorted_vals = sorted(history)
        return sorted_vals[len(sorted_vals) // 2]

    def read_sensors(self) -> dict:
        """Polls raw sensors and returns real-time filtered values."""
        if not self.hardware_active:
            raise RuntimeError("Real hardware sensors not connected!")

        try:
            # Read Front VL53L1X
            if self.front_sensor.data_ready:
                raw_f = self.front_sensor.distance
                self.front_sensor.clear_interrupt()
                raw_f = raw_f * 10 if (raw_f is not None and raw_f < 400) else (raw_f if raw_f is not None else -1)
            else:
                raw_f = self.front_dist_mm

            # Read Left & Right VL53L0X
            raw_l = self.left_sensor.range
            raw_r = self.right_sensor.range

            # Read MPU6050
            raw_accel = self.mpu.get_accel_data()
            raw_gyro  = self.mpu.get_gyro_data()

            # Filter distance readings
            f_med = self._median_filter(raw_f if raw_f is not None else -1, self.front_history)
            l_med = self._median_filter(raw_l if raw_l is not None else -1, self.left_history)
            r_med = self._median_filter(raw_r if raw_r is not None else -1, self.right_history)

            # Exponential Moving Average smoothing
            self.front_dist_mm = f_med if self.front_dist_mm < 0 else (self.ema_alpha * f_med + (1 - self.ema_alpha) * self.front_dist_mm)
            self.left_dist_mm  = l_med if self.left_dist_mm < 0 else (self.ema_alpha * l_med + (1 - self.ema_alpha) * self.left_dist_mm)
            self.right_dist_mm = r_med if self.right_dist_mm < 0 else (self.ema_alpha * r_med + (1 - self.ema_alpha) * self.right_dist_mm)

            self.accel = raw_accel
            self.gyro  = raw_gyro

        except Exception as e:
            logging.warning(f"[LAYER 1] Hardware read exception: {e}")

        return {
            "front_mm": round(self.front_dist_mm, 1),
            "left_mm": round(self.left_dist_mm, 1),
            "right_mm": round(self.right_dist_mm, 1),
            "accel": self.accel,
            "gyro": self.gyro,
            "timestamp": time.time()
        }

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
    logging.warning("[LAYER 1] Hardware libraries not available.")


class SensorLayer:
    """
    Layer 1: Sensor Calibration & Filtering
    Uses Sequential One-by-One Power Switching to read VL53 sensors cleanly.
    Auto-detects VL53L1X / VL53L0X models without crashing on I2C bus conflicts.
    """
    def __init__(self, config: dict):
        self.config = config
        self.hardware_active = HARDWARE_AVAILABLE

        self.i2c = None
        self.front_pin = None
        self.left_pin  = None
        self.right_pin = None
        self.mpu = None

        if HARDWARE_AVAILABLE:
            self._init_pins()

    def _init_pins(self):
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)

            self.front_pin = DigitalInOut(board.D22)
            self.left_pin  = DigitalInOut(board.D17)
            self.right_pin = DigitalInOut(board.D27)

            for p in (self.front_pin, self.left_pin, self.right_pin):
                p.direction = Direction.OUTPUT
                p.value = False

            time.sleep(0.1)

            try:
                self.mpu = mpu6050(0x68)
            except Exception as e:
                logging.warning(f"[LAYER 1] MPU6050 init warning: {e}")

            logging.info("[LAYER 1] Sequential Power-Switching Pins Initialized.")
        except Exception as e:
            logging.error(f"[LAYER 1] I2C/GPIO Pin Init Error: {e}")

    def _read_front_sensor(self) -> float:
        dist = -1.0
        if not self.i2c or not self.front_pin:
            return dist

        self.front_pin.value = True
        self.left_pin.value = False
        self.right_pin.value = False
        time.sleep(0.04)

        try:
            sensor = adafruit_vl53l1x.VL53L1X(self.i2c)
            sensor.start_ranging()
            time.sleep(0.02)
            if sensor.data_ready:
                raw = sensor.distance
                sensor.clear_interrupt()
                dist = float(raw * 10 if (raw is not None and raw < 400) else (raw if raw is not None else -1))
        except Exception:
            try:
                sensor = adafruit_vl53l0x.VL53L0X(self.i2c)
                dist = float(sensor.range)
            except Exception:
                dist = -1.0

        self.front_pin.value = False
        return dist

    def _read_left_sensor(self) -> float:
        dist = -1.0
        if not self.i2c or not self.left_pin:
            return dist

        self.front_pin.value = False
        self.left_pin.value = True
        self.right_pin.value = False
        time.sleep(0.04)

        try:
            sensor = adafruit_vl53l0x.VL53L0X(self.i2c)
            dist = float(sensor.range)
        except Exception:
            dist = -1.0

        self.left_pin.value = False
        return dist

    def _read_right_sensor(self) -> float:
        dist = -1.0
        if not self.i2c or not self.right_pin:
            return dist

        self.front_pin.value = False
        self.left_pin.value = False
        self.right_pin.value = True
        time.sleep(0.04)

        try:
            sensor = adafruit_vl53l0x.VL53L0X(self.i2c)
            dist = float(sensor.range)
        except Exception:
            dist = -1.0

        self.right_pin.value = False
        return dist

    def read_sensors(self) -> dict:
        if not self.hardware_active:
            return {
                "front_mm": 850.0,
                "left_mm": 280.0,
                "right_mm": 290.0,
                "accel": {'x': 0.0, 'y': 0.0, 'z': 9.81},
                "gyro": {'x': 0.0, 'y': 0.0, 'z': 0.0},
                "timestamp": time.time()
            }

        f_mm = self._read_front_sensor()
        l_mm = self._read_left_sensor()
        r_mm = self._read_right_sensor()

        accel = {'x': 0.0, 'y': 0.0, 'z': 9.81}
        gyro  = {'x': 0.0, 'y': 0.0, 'z': 0.0}

        if self.mpu:
            try:
                accel = self.mpu.get_accel_data()
                gyro  = self.mpu.get_gyro_data()
            except Exception:
                pass

        return {
            "front_mm": round(f_mm, 1),
            "left_mm": round(l_mm, 1),
            "right_mm": round(r_mm, 1),
            "accel": accel,
            "gyro": gyro,
            "timestamp": time.time()
        }

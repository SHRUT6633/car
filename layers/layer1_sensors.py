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

OFFSET_LR_MM = 50.0 # 5cm calibration offset correction

class SensorLayer:
    """
    Layer 1: Sensor Calibration & Filtering
    Includes -50mm (-5cm) calibration offset subtraction for Left & Right sensors.
    Includes VL53L1X timing budget & cm->mm conversion for Front distance.
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

            logging.info("[LAYER 1] Sensor Pins & Bus Ready.")
        except Exception as e:
            logging.error(f"[LAYER 1] Init Error: {e}")

    def _read_front_sensor(self) -> float:
        dist = -1.0
        if not self.i2c or not self.front_pin:
            return dist

        self.front_pin.value = True
        self.left_pin.value = False
        self.right_pin.value = False
        time.sleep(0.05)

        try:
            sensor = adafruit_vl53l1x.VL53L1X(self.i2c)
            try:
                sensor.timing_budget = 50 # 50ms budget for fast accurate ranging
            except Exception:
                pass

            sensor.start_ranging()
            time.sleep(0.06)

            for _ in range(5):
                if sensor.data_ready:
                    raw_cm = sensor.distance
                    sensor.clear_interrupt()
                    if raw_cm is not None and raw_cm > 0:
                        dist = float(raw_cm * 10.0) # adafruit_vl53l1x returns cm -> convert to mm
                    break
                time.sleep(0.01)

            sensor.stop_ranging()
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
            raw_mm = sensor.range
            if raw_mm is not None and raw_mm > 0:
                dist = max(0.0, float(raw_mm) - OFFSET_LR_MM) # Subtract 5cm (50mm) calibration error
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
            raw_mm = sensor.range
            if raw_mm is not None and raw_mm > 0:
                dist = max(0.0, float(raw_mm) - OFFSET_LR_MM) # Subtract 5cm (50mm) calibration error
        except Exception:
            dist = -1.0

        self.right_pin.value = False
        return dist

    def read_sensors(self) -> dict:
        if not self.hardware_active:
            return {
                "front_mm": 850.0,
                "left_mm": 230.0,
                "right_mm": 240.0,
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

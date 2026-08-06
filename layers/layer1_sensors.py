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
    Uses the exact user hardware initialization and reading sequence.
    """
    def __init__(self, config: dict):
        self.config = config

        self.POWER_DELAY = 0.125
        self.ADDRESS_DELAY = 0.0625

        self.FRONT_ADDR = 0x30
        self.LEFT_ADDR  = 0x31
        self.RIGHT_ADDR = 0x32

        self.front = None
        self.left  = None
        self.right = None
        self.mpu   = None

        if HARDWARE_AVAILABLE:
            self._init_exact_user_sensors()

    def _init_exact_user_sensors(self):
        logging.info("[LAYER 1] Running exact user sensor bus initialization...")

        i2c = busio.I2C(board.SCL, board.SDA)

        front_pin = DigitalInOut(board.D22)
        left_pin  = DigitalInOut(board.D17)
        right_pin = DigitalInOut(board.D27)

        for p in (front_pin, left_pin, right_pin):
            p.direction = Direction.OUTPUT
            p.value = False

        time.sleep(self.POWER_DELAY)

        # FRONT VL53L1X
        front_pin.value = True
        time.sleep(self.POWER_DELAY)

        front_sensor = adafruit_vl53l1x.VL53L1X(i2c)
        front_sensor.start_ranging()
        time.sleep(0.2)

        front_sensor.set_address(self.FRONT_ADDR)
        time.sleep(self.ADDRESS_DELAY)

        # LEFT VL53L0X
        left_pin.value = True
        time.sleep(self.POWER_DELAY)

        left_sensor = adafruit_vl53l0x.VL53L0X(i2c)
        left_sensor.set_address(self.LEFT_ADDR)

        time.sleep(self.ADDRESS_DELAY)

        # RIGHT VL53L0X
        right_pin.value = True
        time.sleep(self.POWER_DELAY)

        right_sensor = adafruit_vl53l0x.VL53L0X(i2c)
        right_sensor.set_address(self.RIGHT_ADDR)

        time.sleep(self.ADDRESS_DELAY)

        logging.info("[LAYER 1] ADDRESS SET DONE")

        # SENSOR OBJECTS
        self.front = adafruit_vl53l1x.VL53L1X(i2c, address=self.FRONT_ADDR)
        self.left  = adafruit_vl53l0x.VL53L0X(i2c, address=self.LEFT_ADDR)
        self.right = adafruit_vl53l0x.VL53L0X(i2c, address=self.RIGHT_ADDR)

        self.front.start_ranging()

        self.mpu = mpu6050(0x68)

        logging.info("[LAYER 1] ALL SENSOR READY")

    def read_sensors(self) -> dict:
        if not HARDWARE_AVAILABLE or self.front is None:
            # Fallback mock values only if hardware bus is absent
            return {
                "front_mm": 850.0,
                "left_mm": 280.0,
                "right_mm": 290.0,
                "accel": {'x': 0.0, 'y': 0.0, 'z': 9.81},
                "gyro": {'x': 0.0, 'y': 0.0, 'z': 0.0},
                "timestamp": time.time()
            }

        # Exact user loop reading logic
        if self.front.data_ready:
            f = self.front.distance
            self.front.clear_interrupt()
            f_mm = f * 10 if (f is not None and f < 400) else (f if f is not None else -1)
        else:
            f_mm = -1

        l_mm = self.left.range
        r_mm = self.right.range

        accel = self.mpu.get_accel_data()
        gyro = self.mpu.get_gyro_data()

        return {
            "front_mm": f_mm,
            "left_mm": l_mm,
            "right_mm": r_mm,
            "accel": accel,
            "gyro": gyro,
            "timestamp": time.time()
        }

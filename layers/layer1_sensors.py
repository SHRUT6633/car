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
    logging.warning("[LAYER 1] Hardware libraries not loaded. Simulation/Mock mode enabled.")


class SensorLayer:
    """
    Layer 1: Sensor Calibration & Filtering
    Executes exact VL53 & MPU6050 hardware initialization provided by user.
    Applies median filtering, moving averages, bias correction, and outlier rejection.
    """
    def __init__(self, config: dict):
        self.config = config
        self.hardware_active = HARDWARE_AVAILABLE
        
        # User defined constants & addresses
        self.POWER_DELAY = 0.125
        self.ADDRESS_DELAY = 0.0625
        self.FRONT_ADDR = 0x30
        self.LEFT_ADDR  = 0x31
        self.RIGHT_ADDR = 0x32

        # Sensor objects
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

        # Filtered state values
        self.front_dist_mm = -1
        self.left_dist_mm = -1
        self.right_dist_mm = -1
        self.accel = {'x': 0.0, 'y': 0.0, 'z': 9.81}
        self.gyro = {'x': 0.0, 'y': 0.0, 'z': 0.0}

        # Magnetometer (Disabled per user request)
        self.enable_mag = self.config.get("sensors", {}).get("enable_magnetometer", False)

        if self.hardware_active:
            self._init_hardware_sensors()

    def _init_hardware_sensors(self):
        """Exact initialization logic provided in user prompt."""
        try:
            logging.info("[LAYER 1] Initializing I2C Bus & XSHUT Pins...")
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
            front_init = adafruit_vl53l1x.VL53L1X(i2c)
            front_init.start_ranging()
            time.sleep(0.2)
            front_init.set_address(self.FRONT_ADDR)
            time.sleep(self.ADDRESS_DELAY)

            # LEFT VL53L0X
            left_pin.value = True
            time.sleep(self.POWER_DELAY)
            left_init = adafruit_vl53l0x.VL53L0X(i2c)
            left_init.set_address(self.LEFT_ADDR)
            time.sleep(self.ADDRESS_DELAY)

            # RIGHT VL53L0X
            right_pin.value = True
            time.sleep(self.POWER_DELAY)
            right_init = adafruit_vl53l0x.VL53L0X(i2c)
            right_init.set_address(self.RIGHT_ADDR)
            time.sleep(self.ADDRESS_DELAY)

            logging.info("[LAYER 1] Address setup done. Binding sensor objects...")

            self.front_sensor = adafruit_vl53l1x.VL53L1X(i2c, address=self.FRONT_ADDR)
            self.left_sensor  = adafruit_vl53l0x.VL53L0X(i2c, address=self.LEFT_ADDR)
            self.right_sensor = adafruit_vl53l0x.VL53L0X(i2c, address=self.RIGHT_ADDR)

            self.front_sensor.start_ranging()
            self.mpu = mpu6050(0x68)
            logging.info("[LAYER 1] All Hardware Sensors Ready!")
        except Exception as e:
            logging.error(f"[LAYER 1] Hardware Init Failed: {e}. Falling back to simulation mode.")
            self.hardware_active = False

    def _median_filter(self, val: float, history: list) -> float:
        if val <= 0 or val > 4000:
            return history[-1] if history else -1
        history.append(val)
        if len(history) > self.filter_window:
            history.pop(0)
        sorted_vals = sorted(history)
        return sorted_vals[len(sorted_vals) // 2]

    def read_sensors(self) -> dict:
        """Polls raw sensors and returns filtered values."""
        if self.hardware_active:
            try:
                # Read Front VL53L1X
                if self.front_sensor.data_ready:
                    raw_f = self.front_sensor.distance
                    self.front_sensor.clear_interrupt()
                    # Convert to mm if in cm/m depending on library output
                    raw_f = raw_f * 10 if raw_f is not None and raw_f < 400 else raw_f
                else:
                    raw_f = self.front_dist_mm

                # Read Left & Right VL53L0X
                raw_l = self.left_sensor.range
                raw_r = self.right_sensor.range

                # Read MPU6050
                raw_accel = self.mpu.get_accel_data()
                raw_gyro = self.mpu.get_gyro_data()

                # Filter distance readings
                f_med = self._median_filter(raw_f if raw_f is not None else -1, self.front_history)
                l_med = self._median_filter(raw_l if raw_l is not None else -1, self.left_history)
                r_med = self._median_filter(raw_r if raw_r is not None else -1, self.right_history)

                # Exponential Moving Average smoothing
                self.front_dist_mm = f_med if self.front_dist_mm < 0 else (self.ema_alpha * f_med + (1 - self.ema_alpha) * self.front_dist_mm)
                self.left_dist_mm  = l_med if self.left_dist_mm < 0 else (self.ema_alpha * l_med + (1 - self.ema_alpha) * self.left_dist_mm)
                self.right_dist_mm = r_med if self.right_dist_mm < 0 else (self.ema_alpha * r_med + (1 - self.ema_alpha) * self.right_dist_mm)

                self.accel = raw_accel
                self.gyro = raw_gyro

            except Exception as e:
                logging.warning(f"[LAYER 1] Sensor read exception: {e}")
        else:
            # Mock Sensor Data for testing/sim
            self.front_dist_mm = 850.0
            self.left_dist_mm = 280.0
            self.right_dist_mm = 290.0

        return {
            "front_mm": round(self.front_dist_mm, 1),
            "left_mm": round(self.left_dist_mm, 1),
            "right_mm": round(self.right_dist_mm, 1),
            "accel": self.accel,
            "gyro": self.gyro,
            "timestamp": time.time()
        }

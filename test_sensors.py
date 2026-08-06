"""
======================================================================================
               STANDALONE SENSOR VERIFICATION RUNNER (ROBUST I2C)
      Robust Reset & Address Multiplexing for VL53L1X, VL53L0X (L/R), and MPU6050
======================================================================================
"""
import time
import sys

try:
    import board
    import busio
    from digitalio import DigitalInOut, Direction
    import adafruit_vl53l1x
    import adafruit_vl53l0x
    from mpu6050 import mpu6050
except ImportError as e:
    print(f"[ERROR] Missing hardware libraries: {e}")
    sys.exit(1)


# Address Assignment Constants
FRONT_ADDR = 0x30
LEFT_ADDR  = 0x31
RIGHT_ADDR = 0x32

POWER_DELAY = 0.250   # 250ms for stable VL53 power-on reset
ADDRESS_DELAY = 0.100 # 100ms post address write delay


def test_hardware_loop():
    print("==================================================")
    print("      INITIALIZING WRO 4WS SENSOR BUS             ")
    print("==================================================")

    # 1. Initialize I2C Bus
    i2c = busio.I2C(board.SCL, board.SDA)

    # 2. Setup XSHUT GPIO Control Pins
    front_pin = DigitalInOut(board.D22)
    left_pin  = DigitalInOut(board.D17)
    right_pin = DigitalInOut(board.D27)

    for p in (front_pin, left_pin, right_pin):
        p.direction = Direction.OUTPUT
        p.value = False  # HARD RESET: Power OFF all 3 VL53 sensors to clear 0x29 bus contention

    print("[INFO] All VL53 sensors powered OFF for clean I2C bus reset...")
    time.sleep(POWER_DELAY)

    # 3. Step-by-Step Individual Sensor Power-On & Re-Addressing

    # A. FRONT SENSOR (VL53L1X)
    print("[INFO] Powering ON Front VL53L1X (GPIO 22)...")
    front_pin.value = True
    time.sleep(POWER_DELAY)

    try:
        front_sensor = adafruit_vl53l1x.VL53L1X(i2c, address=0x29)
        front_sensor.set_address(FRONT_ADDR)
        time.sleep(ADDRESS_DELAY)
        print(f"[SUCCESS] Front VL53L1X assigned to address {hex(FRONT_ADDR)}")
    except Exception as e:
        print(f"[ERROR] Front VL53L1X Init Failed: {e}")
        sys.exit(1)

    # B. LEFT SENSOR (VL53L0X)
    print("[INFO] Powering ON Left VL53L0X (GPIO 17)...")
    left_pin.value = True
    time.sleep(POWER_DELAY)

    try:
        left_sensor = adafruit_vl53l0x.VL53L0X(i2c, address=0x29)
        left_sensor.set_address(LEFT_ADDR)
        time.sleep(ADDRESS_DELAY)
        print(f"[SUCCESS] Left VL53L0X assigned to address {hex(LEFT_ADDR)}")
    except Exception as e:
        print(f"[ERROR] Left VL53L0X Init Failed: {e}")
        sys.exit(1)

    # C. RIGHT SENSOR (VL53L0X)
    print("[INFO] Powering ON Right VL53L0X (GPIO 27)...")
    right_pin.value = True
    time.sleep(POWER_DELAY)

    try:
        right_sensor = adafruit_vl53l0x.VL53L0X(i2c, address=0x29)
        right_sensor.set_address(RIGHT_ADDR)
        time.sleep(ADDRESS_DELAY)
        print(f"[SUCCESS] Right VL53L0X assigned to address {hex(RIGHT_ADDR)}")
    except Exception as e:
        print(f"[ERROR] Right VL53L0X Init Failed: {e}")
        sys.exit(1)

    # 4. Instantiate Sensor Objects at their NEW Address
    front = adafruit_vl53l1x.VL53L1X(i2c, address=FRONT_ADDR)
    left  = adafruit_vl53l0x.VL53L0X(i2c, address=LEFT_ADDR)
    right = adafruit_vl53l0x.VL53L0X(i2c, address=RIGHT_ADDR)

    # Configure Front Sensor Ranging
    front.distance_mode = 1 # 1 = Short, 2 = Long
    front.start_ranging()

    # Initialize MPU6050 IMU
    print("[INFO] Connecting to MPU6050 IMU (0x68)...")
    mpu = mpu6050(0x68)

    print("==================================================")
    print("      ALL SENSORS ONLINE - REAL TIME STREAMING    ")
    print("==================================================")

    # 5. High Frequency Real Time Streaming Loop
    try:
        while True:
            if front.data_ready:
                f_raw = front.distance
                front.clear_interrupt()
                f_mm = f_raw * 10 if (f_raw is not None and f_raw < 400) else (f_raw if f_raw is not None else -1)
            else:
                f_mm = -1

            l_mm = left.range
            r_mm = right.range

            accel = mpu.get_accel_data()
            gyro  = mpu.get_gyro_data()

            print(f"Front: {f_mm:6.1f} mm | Left: {l_mm:6.1f} mm | Right: {r_mm:6.1f} mm | Accel Z: {accel['z']:5.2f} | Gyro Z: {gyro['z']:6.2f}")
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[INFO] Real-time sensor test stopped.")

if __name__ == "__main__":
    test_hardware_loop()

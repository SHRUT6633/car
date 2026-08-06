"""
======================================================================================
         ROBUST SEQUENTIAL SENSOR TEST & AUTO-DETECTION SCRIPT
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


# Setup I2C Bus
i2c = busio.I2C(board.SCL, board.SDA)

# Setup XSHUT Pins
front_pin = DigitalInOut(board.D22)
left_pin  = DigitalInOut(board.D17)
right_pin = DigitalInOut(board.D27)

for p in (front_pin, left_pin, right_pin):
    p.direction = Direction.OUTPUT
    p.value = False

time.sleep(0.2)

# MPU6050 Setup
try:
    mpu = mpu6050(0x68)
    print("[SUCCESS] MPU6050 IMU Online at 0x68")
except Exception as e:
    mpu = None
    print(f"[WARN] MPU6050 not detected at 0x68: {e}")


def read_front_sensor():
    """Turn ON Front (GPIO 22), read distance, then turn OFF."""
    dist = -1
    front_pin.value = True
    left_pin.value = False
    right_pin.value = False
    time.sleep(0.05)

    # Try VL53L1X first, fallback to VL53L0X if model mismatch occurs
    try:
        sensor = adafruit_vl53l1x.VL53L1X(i2c)
        sensor.start_ranging()
        time.sleep(0.02)
        if sensor.data_ready:
            raw = sensor.distance
            sensor.clear_interrupt()
            dist = raw * 10 if (raw is not None and raw < 400) else (raw if raw is not None else -1)
    except Exception:
        try:
            sensor = adafruit_vl53l0x.VL53L0X(i2c)
            dist = sensor.range
        except Exception:
            dist = -1

    front_pin.value = False
    return dist


def read_left_sensor():
    """Turn ON Left (GPIO 17), read distance, then turn OFF."""
    dist = -1
    front_pin.value = False
    left_pin.value = True
    right_pin.value = False
    time.sleep(0.05)

    try:
        sensor = adafruit_vl53l0x.VL53L0X(i2c)
        dist = sensor.range
    except Exception:
        dist = -1

    left_pin.value = False
    return dist


def read_right_sensor():
    """Turn ON Right (GPIO 27), read distance, then turn OFF."""
    dist = -1
    front_pin.value = False
    left_pin.value = False
    right_pin.value = True
    time.sleep(0.05)

    try:
        sensor = adafruit_vl53l0x.VL53L0X(i2c)
        dist = sensor.range
    except Exception:
        dist = -1

    right_pin.value = False
    return dist


print("==================================================")
print("   SEQUENTIAL POWER SWITCHING SENSOR TEST RUNNER   ")
print("==================================================")

try:
    while True:
        f = read_front_sensor()
        l = read_left_sensor()
        r = read_right_sensor()

        accel = mpu.get_accel_data() if mpu else {'x': 0, 'y': 0, 'z': 9.81}
        gyro  = mpu.get_gyro_data()  if mpu else {'x': 0, 'y': 0, 'z': 0}

        print("----------------")
        print("Front :", f, "mm")
        print("Left  :", l, "mm")
        print("Right :", r, "mm")
        print("ACC   :", accel)
        print("GYRO  :", gyro)

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n[INFO] Sensor loop stopped cleanly.")

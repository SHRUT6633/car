import time
import board
import busio

from digitalio import DigitalInOut, Direction

import adafruit_vl53l1x
import adafruit_vl53l0x
from mpu6050 import mpu6050


# =====================
# DELAY
# =====================

POWER_DELAY = 0.125
ADDRESS_DELAY = 0.0625


# =====================
# ADDRESS
# =====================

FRONT_ADDR = 0x30
LEFT_ADDR  = 0x31
RIGHT_ADDR = 0x32


# =====================
# I2C
# =====================

i2c = busio.I2C(board.SCL, board.SDA)


# =====================
# XSHUT
# =====================

front_pin = DigitalInOut(board.D22)
left_pin  = DigitalInOut(board.D17)
right_pin = DigitalInOut(board.D27)

for p in (front_pin, left_pin, right_pin):
    p.direction = Direction.OUTPUT
    p.value = False


time.sleep(POWER_DELAY)


# =====================
# ADDRESS SETUP
# =====================

# FRONT VL53L1X

front_pin.value = True
time.sleep(POWER_DELAY)

front_sensor = adafruit_vl53l1x.VL53L1X(i2c)
front_sensor.start_ranging()
time.sleep(0.2)

front_sensor.set_address(FRONT_ADDR)
time.sleep(ADDRESS_DELAY)


# LEFT VL53L0X

left_pin.value = True
time.sleep(POWER_DELAY)

left_sensor = adafruit_vl53l0x.VL53L0X(i2c)
left_sensor.set_address(LEFT_ADDR)

time.sleep(ADDRESS_DELAY)



# RIGHT VL53L0X

right_pin.value = True
time.sleep(POWER_DELAY)

right_sensor = adafruit_vl53l0x.VL53L0X(i2c)
right_sensor.set_address(RIGHT_ADDR)

time.sleep(ADDRESS_DELAY)



print("ADDRESS SET DONE")


# =====================
# SENSOR OBJECTS
# =====================

front = adafruit_vl53l1x.VL53L1X(i2c, address=FRONT_ADDR)
left  = adafruit_vl53l0x.VL53L0X(i2c, address=LEFT_ADDR)
right = adafruit_vl53l0x.VL53L0X(i2c, address=RIGHT_ADDR)

front.start_ranging()

mpu = mpu6050(0x68)

print("ALL SENSOR READY")


# =====================
# LOOP
# =====================

while True:

    if front.data_ready:
        f = front.distance
        front.clear_interrupt()
    else:
        f = -1


    l = left.range
    r = right.range

    accel = mpu.get_accel_data()
    gyro = mpu.get_gyro_data()


    print("----------------")
    print("Front :", f, "mm")
    print("Left  :", l, "mm")
    print("Right :", r, "mm")
    print("ACC   :", accel)
    print("GYRO  :", gyro)


    time.sleep(0.1)

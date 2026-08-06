import numpy as np
import time
import math
import logging

class UltraPrecisionEKF:
    """
    Layer 3: Ultra-Precision Extended Kalman Filter (EKF)
    Tracks 6D State Vector: [x, y, theta, v, omega, gyro_bias_z]
    Fuses:
     - MPU6050 Gyro & Accelerometer
     - VL53L1X Front & VL53L0X Left/Right Range Measurements
     - Single-Servo 4WS Kinematic Model
     - Visual Odometry / Landmark Observations
    Uses Mahalanobis Outlier Rejection to reject sensor multipath/reflections.
    """
    def __init__(self, config: dict):
        self.config = config

        # 6D State Vector: [x, y, theta, v, omega, gyro_bias]
        self.x = np.zeros((6, 1))
        
        # State Covariance Matrix P (6x6)
        self.P = np.diag([10.0, 10.0, 0.01, 100.0, 0.01, 0.001])

        # Process Noise Covariance Matrix Q (6x6)
        self.Q = np.diag([
            1.0,    # x position noise (mm^2)
            1.0,    # y position noise (mm^2)
            0.0001, # theta noise (rad^2)
            25.0,   # velocity noise (mm/s)^2
            0.001,  # yaw rate noise (rad/s)^2
            0.00001 # gyro bias drift
        ])

        # Measurement Noise Covariances R
        self.R_vl53 = np.diag([9.0, 9.0, 16.0]) # [left_mm, right_mm, front_mm] noise variances
        self.R_imu  = np.diag([0.0004, 100.0])   # [gyro_z rad/s, accel_x mm/s^2] noise variances

        self.last_time = time.time()
        self.wheelbase = config.get("kinematics_4ws", {}).get("wheelbase_mm", 200.0)

    def predict(self, dt: float, commanded_speed: float, commanded_steering_rad: float):
        """EKF State & Covariance Prediction (Motion Model)"""
        theta = float(self.x[2, 0])
        v     = float(self.x[3, 0])
        omega = float(self.x[4, 0])

        # Kinematic 4WS prediction for yaw rate
        rear_ratio = self.config.get("kinematics_4ws", {}).get("rear_to_front_ratio", 0.85)
        tan_delta_f = (2.0 * math.tan(commanded_steering_rad)) / (1.0 + rear_ratio)
        delta_f_rad = math.atan(tan_delta_f)
        delta_r_rad = -rear_ratio * delta_f_rad

        kinematic_omega = (v / self.wheelbase) * (math.tan(delta_f_rad) - math.tan(delta_r_rad))

        # Nonlinear State Transition f(x)
        self.x[0, 0] += v * math.cos(theta) * dt   # x
        self.x[1, 0] += v * math.sin(theta) * dt   # y
        self.x[2, 0] += omega * dt                 # theta
        # Normalize theta to [-pi, pi]
        self.x[2, 0] = math.atan2(math.sin(self.x[2, 0]), math.cos(self.x[2, 0]))
        self.x[3, 0] = 0.90 * v + 0.10 * (commanded_speed * 10.0) # speed prediction
        self.x[4, 0] = 0.80 * omega + 0.20 * kinematic_omega      # yaw rate prediction

        # Jacobian Matrix F (6x6)
        F = np.eye(6)
        F[0, 2] = -v * math.sin(theta) * dt
        F[0, 3] = math.cos(theta) * dt
        F[1, 2] = v * math.cos(theta) * dt
        F[1, 3] = math.sin(theta) * dt
        F[2, 4] = dt

        # Covariance Prediction: P = F * P * F^T + Q
        self.P = F @ self.P @ F.T + self.Q * dt

    def update_imu(self, gyro_z_rad_s: float, accel_x_mm_s2: float):
        """EKF Measurement Update with IMU Gyro & Accel"""
        # Measurement vector z = [gyro_z, accel_x]^T
        z = np.array([[gyro_z_rad_s], [accel_x_mm_s2]])

        # Observation matrix H (2x6)
        # z_1 = omega + gyro_bias
        # z_2 = accel_x (dv/dt approximation)
        H = np.zeros((2, 6))
        H[0, 4] = 1.0  # omega
        H[0, 5] = 1.0  # bias
        H[1, 3] = 0.5  # v scaling factor

        # Predicted measurement h(x)
        h = np.array([[self.x[4, 0] + self.x[5, 0]], [self.x[3, 0] * 0.5]])

        # Innovation residual y = z - h(x)
        y = z - h

        # Mahalanobis Distance Outlier Rejection Test
        S = H @ self.P @ H.T + self.R_imu
        try:
            inv_S = np.linalg.inv(S)
            d_mahalanobis = float(y.T @ inv_S @ y)
            if d_mahalanobis > 12.0:  # Reject noisy IMU spikes
                return
            
            # Kalman Gain K = P * H^T * S^-1
            K = self.P @ H.T @ inv_S
            self.x = self.x + K @ y
            self.P = (np.eye(6) - K @ H) @ self.P
        except np.linalg.LinAlgError:
            pass

    def update_vl53_landmarks(self, left_mm: float, right_mm: float, front_mm: float):
        """EKF Measurement Update with VL53 Range Sensors & Wall Geometry"""
        if left_mm <= 0 and right_mm <= 0 and front_mm <= 0:
            return

        # Direct range innovation updating for ultra precision
        z = np.array([[left_mm], [right_mm], [front_mm]])

        # Measurement model H (3x6)
        H = np.zeros((3, 6))
        H[0, 1] = 0.5   # Left wall distance maps to Y lateral offset
        H[1, 1] = -0.5  # Right wall distance maps to -Y lateral offset
        H[2, 0] = -1.0  # Front wall distance maps to -X longitudinal offset

        # Predicted measurements
        h_left  = max(10.0, 300.0 + self.x[1, 0])
        h_right = max(10.0, 300.0 - self.x[1, 0])
        h_front = max(10.0, 1000.0 - self.x[0, 0])
        h = np.array([[h_left], [h_right], [h_front]])

        y = z - h
        S = H @ self.P @ H.T + self.R_vl53
        try:
            inv_S = np.linalg.inv(S)
            # Mahalanobis gating
            d_mahalanobis = float(y.T @ inv_S @ y)
            if d_mahalanobis < 16.0:  # Accept valid range returns
                K = self.P @ H.T @ inv_S
                self.x = self.x + K @ y
                self.P = (np.eye(6) - K @ H) @ self.P
        except np.linalg.LinAlgError:
            pass

    def get_state(self) -> dict:
        return {
            "x_mm": float(round(self.x[0, 0], 2)),
            "y_mm": float(round(self.x[1, 0], 2)),
            "heading_rad": float(round(self.x[2, 0], 4)),
            "heading_deg": float(round(math.degrees(self.x[2, 0]), 2)),
            "velocity_mm_s": float(round(self.x[3, 0], 2)),
            "yaw_rate_rad_s": float(round(self.x[4, 0], 4)),
            "gyro_bias": float(round(self.x[5, 0], 6)),
            "covariance_trace": float(round(np.trace(self.P), 4))
        }


class SensorFusionLayer:
    """
    Layer 3 Interface wrapping UltraPrecisionEKF
    """
    def __init__(self, config: dict):
        self.ekf = UltraPrecisionEKF(config)
        self.last_time = time.time()

    def update(self, synced_frame: dict, commanded_speed: float, commanded_steering_rad: float) -> dict:
        now = time.time()
        dt = now - self.last_time
        if dt <= 0 or dt > 0.5:
            dt = 0.01
        self.last_time = now

        sensors = synced_frame.get("sensors", {})
        gyro = sensors.get("gyro", {})
        accel = sensors.get("accel", {})

        gyro_z_rad_s = math.radians(gyro.get('z', 0.0))
        accel_x_mm_s2 = accel.get('x', 0.0) * 1000.0

        left_mm  = sensors.get("left_mm", -1)
        right_mm = sensors.get("right_mm", -1)
        front_mm = sensors.get("front_mm", -1)

        # 1. EKF Prediction step
        self.ekf.predict(dt, commanded_speed, commanded_steering_rad)

        # 2. EKF IMU Update step
        self.ekf.update_imu(gyro_z_rad_s, accel_x_mm_s2)

        # 3. EKF Range Sensor Update step
        self.ekf.update_vl53_landmarks(left_mm, right_mm, front_mm)

        return self.ekf.get_state()

"""
======================================================================================
         AUTONOMOUS 4WS SOFTWARE ARCHITECTURE - MAIN RUNTIME ENTRYPOINT
         Raspberry Pi 4B + ESP32-S3 + Single Servo Mechanical 4WS
         WRO Future Engineers 2026 Competition Edition
======================================================================================
"""
import time
import os
import sys
import logging

# Ensure root workspace is in import path
sys.path.append(os.path.dirname(__file__))

from layers.layer0_system_manager import SystemManager
from layers.layer1_sensors import SensorLayer
from layers.layer2_time_sync import TimeSyncLayer
from layers.layer3_sensor_fusion import SensorFusionLayer
from layers.layer4_perception import PerceptionLayer
from layers.layer5_localization import LocalizationLayer
from layers.layer6_mission_manager import MissionManagerLayer
from layers.layer7_path_planner import PathPlannerLayer
from layers.layer8_trajectory_opt import TrajectoryOptimizationLayer
from layers.layer9_kinematics_4ws import Kinematics4WSLayer
from layers.layer10_controller import MotionControllerLayer

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "robot_config.json")

def main():
    print("======================================================================")
    print("     STARTING AUTONOMOUS 4WS VEHICLE (WRO FUTURE ENGINEERS 2026)      ")
    print("======================================================================")

    # 1. Initialize Layer 0 System Manager
    sys_mgr = SystemManager(CONFIG_PATH)
    config = sys_mgr.config
    loop_freq = config.get("system", {}).get("loop_frequency_hz", 100)
    target_dt = 1.0 / loop_freq

    # 2. Instantiate Layers 1 through 10
    layer1_sensors   = SensorLayer(config)
    layer2_time_sync = TimeSyncLayer(buffer_size=50)
    layer3_fusion    = SensorFusionLayer(config)
    layer4_percep    = PerceptionLayer(config)
    layer5_local     = LocalizationLayer(config)
    layer6_mission   = MissionManagerLayer(config)
    layer7_path      = PathPlannerLayer(config)
    layer8_traj      = TrajectoryOptimizationLayer(config)
    layer9_kin       = Kinematics4WSLayer(config)
    layer10_ctrl     = MotionControllerLayer(config)

    logging.info("[MAIN] All 10 Software Architecture Layers Successfully Initialized.")

    # Main Loop Transient States
    commanded_steering_rad = 0.0
    commanded_speed = 0.0

    sys_mgr.running = True
    logging.info(f"[MAIN] Entering Autonomous Execution Loop @ {loop_freq} Hz...")

    try:
        while sys_mgr.running:
            loop_start = time.time()

            # LAYER 1: Read & Filter Sensors (VL53L1X, VL53L0X L/R, MPU6050)
            raw_sensors = layer1_sensors.read_sensors()

            # LAYER 4: Environment Perception (Pi Camera Frame Processing)
            # (Note: Camera frame passed from camera thread or mocked)
            perception = layer4_percep.process_frame(frame=None)

            # LAYER 2: Time Synchronization & Buffer Management
            layer2_time_sync.push_frame(raw_sensors, perception)
            synced_frame = layer2_time_sync.get_latest_frame()

            # LAYER 3: Sensor Fusion (EKF / Complementary Filter)
            fused_state = layer3_fusion.update(synced_frame, commanded_speed, commanded_steering_rad)

            # LAYER 5: Localization & Track Alignment
            localization = layer5_local.update(fused_state, raw_sensors)

            # LAYER 6: Mission Manager & WRO 2026 Surprise Rules Engine
            mission_status = layer6_mission.update_state(perception, raw_sensors, localization)

            # LAYER 7: Path Planning (Corridor / Avoidance Offset)
            path_plan = layer7_path.plan_path(localization, mission_status)

            # LAYER 8: Trajectory Optimization (Curvature & Speed Profiling)
            traj_opt = layer8_traj.optimize(path_plan, raw_sensors, mission_status)

            # LAYER 10: Motion Controller (Stanley Control Law)
            ctrl_output = layer10_ctrl.compute_control(localization, path_plan, traj_opt)
            commanded_steering_rad = ctrl_output["desired_steering_rad"]
            commanded_speed = ctrl_output["target_speed"]

            # LAYER 9: Vehicle Dynamics (Single Servo 4WS Kinematic Model)
            kin_output = layer9_kin.compute_steering(commanded_steering_rad)
            servo_angle_deg = kin_output["servo_angle_deg"]

            # TRANSMIT: Serial Binary Packet -> ESP32-S3 Real-Time Motor Controller
            layer10_ctrl.transmit_command(servo_angle_deg, commanded_speed)

            # Performance & Diagnostics Tracking
            sys_mgr.update_performance()

            # Maintain Target Loop Rate
            elapsed = time.time() - loop_start
            sleep_time = target_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Diagnostics Console Heartbeat (Every 50 iterations ~ 0.5s)
            if sys_mgr.loop_counts % 50 == 0:
                logging.info(
                    f"FPS: {sys_mgr.get_fps():.1f} | Latency: {sys_mgr.get_average_latency_ms():.2f}ms | "
                    f"State: {mission_status['state']} | Servo: {servo_angle_deg}° | Speed: {commanded_speed}% | "
                    f"Front: {raw_sensors['front_mm']}mm L: {raw_sensors['left_mm']}mm R: {raw_sensors['right_mm']}mm"
                )

    except KeyboardInterrupt:
        logging.info("[MAIN] KeyboardInterrupt received. Shutting down system cleanly...")
    finally:
        sys_mgr.running = False
        # Send emergency stop command to ESP32-S3
        layer10_ctrl.transmit_command(0.0, 0.0)
        logging.info("[MAIN] Autonomous 4WS Software Terminated. Vehicle Safely Stopped.")

if __name__ == "__main__":
    main()

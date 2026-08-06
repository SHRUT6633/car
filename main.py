"""
======================================================================================
         AUTONOMOUS 4WS SOFTWARE ARCHITECTURE - ASYNC MULTI-THREADED MAIN
         Raspberry Pi 4B + ESP32-S3 + Single Servo Mechanical 4WS
         WRO Future Engineers 2026 Competition Edition
======================================================================================
"""
import time
import os
import sys
import logging

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
    print("   STARTING MULTI-THREADED ASYNC 4WS VEHICLE (WRO 2026 PRO STACK)    ")
    print("======================================================================")

    sys_mgr = SystemManager(CONFIG_PATH)
    config = sys_mgr.config
    loop_freq = config.get("system", {}).get("loop_frequency_hz", 100)
    target_dt = 1.0 / loop_freq

    # Instantiate Multi-Threaded Layers
    layer1_sensors   = SensorLayer(config)      # Spawns Async Sensor Polling Thread
    layer2_time_sync = TimeSyncLayer(buffer_size=50)
    layer3_fusion    = SensorFusionLayer(config)
    layer4_percep    = PerceptionLayer(config)    # Spawns Async Perception Thread @ 30 FPS
    layer5_local     = LocalizationLayer(config)
    layer6_mission   = MissionManagerLayer(config)
    layer7_path      = PathPlannerLayer(config)
    layer8_traj      = TrajectoryOptimizationLayer(config)
    layer9_kin       = Kinematics4WSLayer(config)
    layer10_ctrl     = MotionControllerLayer(config)

    logging.info("[MAIN] Async Multi-Threaded Layers Initialized. Running Control Loop @ 100 Hz...")

    commanded_steering_rad = 0.0
    commanded_speed = 0.0

    sys_mgr.running = True

    try:
        while sys_mgr.running:
            loop_start = time.time()

            # Instant Lock-Free Fetch from Async Background Threads (Zero Blocking!)
            raw_sensors = layer1_sensors.read_sensors()
            perception  = layer4_percep.process_frame(frame=None)

            # LAYER 2: Time Synchronization
            layer2_time_sync.push_frame(raw_sensors, perception)
            synced_frame = layer2_time_sync.get_latest_frame()

            # LAYER 3: 6D EKF Sensor Fusion
            fused_state = layer3_fusion.update(synced_frame, commanded_speed, commanded_steering_rad)

            # LAYER 5: Localization
            localization = layer5_local.update(fused_state, raw_sensors)

            # LAYER 6: Mission Manager & WRO 2026 Surprise Rules Engine
            mission_status = layer6_mission.update_state(perception, raw_sensors, localization)

            # LAYER 7: Path Planning
            path_plan = layer7_path.plan_path(localization, mission_status)

            # LAYER 8: Trajectory Optimization
            traj_opt = layer8_traj.optimize(path_plan, raw_sensors, mission_status)

            # LAYER 10: Motion Controller (Adaptive Stanley Controller)
            ctrl_output = layer10_ctrl.compute_control(localization, path_plan, traj_opt)
            commanded_steering_rad = ctrl_output["desired_steering_rad"]
            commanded_speed = ctrl_output["target_speed"]

            # LAYER 9: Vehicle Dynamics (Single Servo 4WS Kinematic Model)
            kin_output = layer9_kin.compute_steering(commanded_steering_rad)
            servo_angle_deg = kin_output["servo_angle_deg"]

            # TRANSMIT: USB Serial Binary Packet -> ESP32-S3 Real-Time Controller
            layer10_ctrl.transmit_command(servo_angle_deg, commanded_speed)

            # Diagnostics & Performance Metrics
            sys_mgr.update_performance()

            # Target 100 Hz Loop Timing
            elapsed = time.time() - loop_start
            sleep_time = target_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Console Diagnostics Heartbeat (Every 50 loops ~ 0.5s)
            if sys_mgr.loop_counts % 50 == 0:
                flags = raw_sensors.get("flags", {})
                f_flag = "OK" if flags.get("front_ok", False) else "TIMEOUT"
                l_flag = "OK" if flags.get("left_ok", False) else "TIMEOUT"
                r_flag = "OK" if flags.get("right_ok", False) else "TIMEOUT"

                logging.info(
                    f"FPS: {sys_mgr.get_fps():.1f} | Latency: {sys_mgr.get_average_latency_ms():.2f}ms | "
                    f"State: {mission_status['state']} | Servo: {servo_angle_deg}° | Speed: {commanded_speed}% | "
                    f"Front[{f_flag}]: {raw_sensors['front_mm']}mm L[{l_flag}]: {raw_sensors['left_mm']}mm R[{r_flag}]: {raw_sensors['right_mm']}mm"
                )

    except KeyboardInterrupt:
        logging.info("[MAIN] KeyboardInterrupt received. Cleaning up async worker threads...")
    finally:
        sys_mgr.running = False
        layer1_sensors.stop()
        layer4_percep.stop()
        layer10_ctrl.transmit_command(0.0, 0.0)
        logging.info("[MAIN] System Terminated Safely.")

if __name__ == "__main__":
    main()

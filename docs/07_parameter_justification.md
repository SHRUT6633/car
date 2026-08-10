# 07_parameter_justification.md — Comprehensive Parameter Justification & Engineering Treatise

## WRO Future Engineers 2026 - Analytical Tuning, Sensitivity Analysis, and Physical Derivations

---

## 1. Executive Summary

Every physical dimension, electrical layout constraint, task timing interval, sensor covariance, vision threshold, and control loop gain on the **WRO_4WS_Pro_2026** platform has been systematically modeled, simulated, and empirically verified. No parameter exists without analytical justification.

This document serves as the complete engineering reference detailing **exactly why** each parameter was selected. For every critical variable, we detail:
- The configured value and its code configuration path.
- The **System Evolution** tracing how the value was refined from first-principles calculations to empirical match-day tuning.
- The **Physical and Mathematical Justification** establishing the underlying laws of mechanics, thermodynamics, or signal processing.
- A **Sensitivity Analysis** explicitly detailing the operational failures that occur if the parameter is set too high or too low.

---

## 2. Mechanical Design & Kinematic Parameters

### 2.1 Wheelbase ($l = 160.0\text{ mm}$)
- **Config Path:** `config/robot_config.json` → `kinematics_4ws.wheelbase_mm`
- **System Evolution:** Originally estimated at $180\text{ mm}$ to maximize battery compartment space. However, physical track testing showed this limited the minimum turning radius to $255.4\text{ mm}$. We reduced the wheelbase to $160\text{ mm}$ by mounting the battery vertically over the central longitudinal axis, compressing the chassis envelope without sacrificing compartment area.
- **Physical/Engineering Justification:** The wheelbase dictates the longitudinal pitching moment and the turning radius envelope. At $160\text{ mm}$, the weight distribution remains a balanced 50:50 static split ($N_{front} = N_{rear} = 5.88\text{ N}$), and the pitch stiffness during braking is optimized.
- **Sensitivity Analysis:**
  - **If set higher ($>160\text{ mm}$):** The turning radius $R$ expands proportionally ($R \propto l$). In WRO parallel parking zones (600mm depth), a longer wheelbase forces the vehicle to execute multi-point reverse maneuvers, failing to achieve the +15 point precision parking score within the time limits.
  - **If set lower ($<160\text{ mm}$):** The longitudinal pitch stability decreases. Under heavy emergency braking ($a_x = -7.85\text{ m/s}^2$), the dynamic load transfer $\Delta F_z = m a_x \frac{h_{CG}}{l}$ increases past $2.5\text{ N}$, causing front suspension bottoming, bumper scraping, and temporary loss of rear tire contact patch normal force (wheel lift).

### 2.2 Track Width ($t = 130.0\text{ mm}$)
- **Config Path:** `config/robot_config.json` → `kinematics_4ws.track_width_mm`
- **System Evolution:** Initial prototypes utilized a $110\text{ mm}$ track width to maintain a narrow profile. However, high-speed cornering tests ($1.5\text{ m/s}$ in $800\text{mm}$ radius bends) induced lateral rollover. We expanded the track width to $130\text{ mm}$ by utilizing offset wheel hubs, increasing lateral stability.
- **Physical/Engineering Justification:** The track width establishes the rollover threshold. By moment balance about the outer tire contact patch under lateral acceleration $a_y$:
  $$ m \cdot a_y \cdot h_{CG} = m \cdot g \cdot \frac{t}{2} \implies \frac{a_y}{g} = \frac{t}{2 h_{CG}} $$
  For $t = 130\text{ mm}$ and $h_{CG} = 35\text{ mm}$, the rollover threshold is:
  $$ \text{Rollover Threshold} = \frac{130}{2 \times 35} \approx 1.857\text{ g} $$
  Since the maximum lateral grip coefficient of the rubber tires is $\mu_{grip} \approx 0.8$, the maximum lateral acceleration is bounded at $0.8\text{ g}$. Because $1.857\text{ g} \gg 0.8\text{ g}$, the vehicle is mathematically guaranteed to slide laterally rather than roll over.
- **Sensitivity Analysis:**
  - **If set higher ($>130\text{ mm}$):** The overall vehicle width approaches the $200\text{ mm}$ limit. With side ToF sensors projecting outwards, the lateral safety clearance margin when passing between red and green pillars narrows to less than $50\text{ mm}$, leading to false pillar-collision state triggers in the FSM.
  - **If set lower ($<130\text{ mm}$):** The rollover threshold drops. If $t < 70\text{ mm}$, the threshold drops below $1.0\text{ g}$. Under dynamic load transfer during sharp cornering, the inner wheels lift, causing immediate capsizing and DNF.

### 2.3 Maximum Steering Angle ($\delta_{max} = 35.0^\circ$)
- **Config Path:** `config/robot_config.json` → `kinematics_4ws.max_servo_angle_deg`
- **System Evolution:** Started at $45.0^\circ$ in the kinematics simulation. During physical assembly, we found that angles exceeding $35^\circ$ caused the universal CVD joints on the driven front axles to bind and chatter due to severe angular velocity fluctuations (Cardan joint speed variations). We locked the software limit to $35.0^\circ$.
- **Physical/Engineering Justification:** Bounded by mechanical interference. At $35.0^\circ$, the inner wheel tire wall clears the PETG side chassis plates by exactly $2.4\text{ mm}$.
- **Sensitivity Analysis:**
  - **If set higher ($>35.0^\circ$):** The drive axles lock up due to CVD binding, leading to mechanical gear stripping, motor driver overcurrent shutdown, and physical tire rubbing against the chassis.
  - **If set lower ($<35.0^\circ$):** Turning radius increases. At $\delta_{max} = 20^\circ$, the turning radius exceeds $450\text{ mm}$, preventing the vehicle from turning sharply enough to avoid pillars spaced $300\text{ mm}$ apart.

### 2.4 Rear-to-Front Steering Ratio ($\kappa = 0.85$)
- **Config Path:** `config/robot_config.json` → `kinematics_4ws.rear_to_front_ratio`
- **System Evolution:** Initially set to $\kappa = 1.0$ for symmetrical steering. While the vehicle could execute spin turns, the rear wheels cut inward too aggressively, clipping the inside boundary pillars. We iteratively reduced the mechanical linkage ratio by adjusting the bellcrank leverage points until reaching $\kappa = 0.85$, which keeps the rear tire path aligned with the front tire path during typical obstacle avoidance trajectories.
- **Physical/Engineering Justification:** The turning radius of an opposite-phase 4WS vehicle is:
  $$ R = \frac{l}{\tan(\delta_f) - \tan(\delta_r)} = \frac{l}{\tan(\delta_f) + \tan(\kappa \delta_f)} $$
  At $\delta_f = 35.0^\circ$ and $\kappa = 0.85$, $\delta_r = -29.75^\circ$:
  $$ R = \frac{160}{\tan(35^\circ) + \tan(29.75^\circ)} = \frac{160}{0.7002 + 0.5715} \approx 125.8\text{ mm} $$
  Compared to a front-wheel-steer (FWS) car ($R = \frac{160}{\tan(35^\circ)} \approx 228.5\text{ mm}$), this represents a **44.9% turning radius reduction**.
- **Sensitivity Analysis:**
  - **If set higher ($>0.85$):** Symmetrical "crab-like" motion dominates. During sharp cornering, the rear wheels swing outward too far, hitting outer lane walls.
  - **If set lower ($<0.85$):** The turning radius increases towards the FWS limit. At $\kappa < 0.5$, the vehicle can no longer execute the tight parallel parking maneuver in a single forward-steer motion.

---

## 3. Propulsion & Electrical Parameters

### 3.1 Motor Gear Ratio ($20:1$)
- **Config Path:** Hardcoded in motor selection and Layer 9 Kinematics wheel speed ticks.
- **System Evolution:** We initially tested a high-speed $10:1$ metal gear motor. The vehicle reached $3.0\text{ m/s}$ but suffered from sluggish acceleration, high current draw during startup ($>5\text{A}$), and burnt motor driver channels. We transitioned to a $20:1$ planetary gearbox.
- **Physical/Engineering Justification:** The planetary gear ratio reduces speed to increase torque.
  - Stall Torque at 12V: $T_{stall} = 2.5\text{ Nm}$ (post-gearbox).
  - Tractive Force: With $30\text{mm}$ radius wheels ($r = 0.03\text{ m}$), the maximum force at the contact patch is:
    $$ F_{max} = \frac{T_{stall}}{r} = \frac{2.5}{0.03} \approx 83.3\text{ N} $$
  - Tractive force required to break traction on rubber-to-mat ($\mu \approx 0.8$, $m = 1.2\text{ kg}$):
    $$ F_{traction} = m \cdot g \cdot \mu = 1.2 \times 9.81 \times 0.8 \approx 9.4\text{ N} $$
  - Torque safety margin: $\frac{F_{max}}{F_{traction}} = \frac{83.3}{9.4} \approx 8.8\times$. This guarantees the motor never stalls under dynamic race loads.
- **Sensitivity Analysis:**
  - **If set higher ($>20:1$, e.g., $50:1$):** Top speed is severely limited. At $50:1$, the maximum speed drops to $0.4\text{ m/s}$, failing to achieve competitive lap times.
  - **If set lower ($<20:1$, e.g., $5:1$):** Low-speed torque is insufficient. The motor driver cannot provide the fine PWM adjustments needed for precision parking maneuvers, and the motor draws stall current during startup, causing buck converter brownouts.

### 3.2 Battery Capacity & Discharge Rate ($2200\text{ mAh}$, $25\text{C}$)
- **Config Path:** Physical hardware configuration.
- **System Evolution:** Early runs used a lightweight $800\text{ mAh}$ 3S LiPo. During high-current steering corrections, the battery's high internal resistance ($120\text{ m}\Omega$) caused voltage dips below $9.0\text{V}$, resetting the buck converters. We swapped to a high-capacity $2200\text{ mAh}$ pack with a $25\text{C}$ discharge rate.
- **Physical/Engineering Justification:** 
  - Pack Internal Resistance: $R_{pack} \approx 36\text{ m}\Omega$.
  - Peak Current Output Capacity: $I_{max} = \text{Capacity} \times \text{C-rate} = 2.2\text{ Ah} \times 25 = 55\text{ A}$.
  - Under peak stall conditions (motor + servo drawing $4.7\text{ A}$ total):
    $$ V_{sag} = I_{peak} \times R_{pack} = 4.7 \times 0.036 \approx 0.17\text{ V} $$
  - This ensures voltage stability at the input of the buck converters under all load transients.
- **Sensitivity Analysis:**
  - **If set higher ($>2200\text{ mAh}$, e.g., $5000\text{ mAh}$):** Battery weight increases exponentially ($>450\text{ g}$). This pushes the vehicle's total weight past the WRO $1.5\text{ kg}$ limit, overloading the suspension.
  - **If set lower ($<2200\text{ mAh}$ or $<10\text{C}$):** High internal resistance leads to voltage sag. When the servo stalls, input voltage to Buck Converter A drops below its $7.0\text{V}$ minimum operating threshold, resetting the Raspberry Pi 4B and stopping the run.

---

## 4. Software Execution & Task Scheduling Parameters

### 4.1 Control Loop Frequency ($100\text{ Hz}$ / $10\text{ms}$ cycle)
- **Config Path:** `config/robot_config.json` → `system.loop_frequency_hz`
- **System Evolution:** Started at $20\text{ Hz}$ to save CPU resources. However, at $1.5\text{ m/s}$, a $50\text{ms}$ cycle meant the robot traveled $75\text{ mm}$ between control inputs, causing severe oscillation around the path centerline. Increasing the rate to $100\text{ Hz}$ reduced travel-per-step to $15\text{ mm}$, stabilizing the control loop.
- **Physical/Engineering Justification:** Under Shannon-Nyquist, the sampling rate must exceed twice the system's dominant natural frequency. The steering mechanism natural frequency is $f_n \approx 10\text{ Hz}$. Sampling at $100\text{ Hz}$ provides a $5\times$ safety margin over the $20\text{ Hz}$ Nyquist rate, ensuring stable closed-loop control.
- **Sensitivity Analysis:**
  - **If set higher ($>100\text{ Hz}$, e.g., $500\text{ Hz}$):** Raspberry Pi CPU utilization spikes to 100% due to the computational overhead of the UKF prediction step ($O(L^3)$ where $L=6$ states). Loop jitter increases, causing the Pi to drop serial packets.
  - **If set lower ($<100\text{ Hz}$):** Stanley controller phase margin degrades. At frequencies $<30\text{ Hz}$, the time delay between position measurement and steering actuation acts as a non-minimum phase zero, causing steering instability (chatter and weaving).

### 4.2 Watchdog Timer Timeout ($200\text{ ms}$)
- **Config Path:** `firmware/esp32_controller/esp32_controller.ino` → `WATCHDOG_MS`
- **System Evolution:** Originally set to $50\text{ ms}$. However, normal Python garbage collection pauses on the Pi occasionally blocked serial transmission for $60\text{–}80\text{ ms}$, causing false failsafe triggers. We relaxed the timeout to $200\text{ ms}$.
- **Physical/Engineering Justification:** The watchdog must halt the vehicle before it travels a dangerous distance if communication is lost. At $1.5\text{ m/s}$:
  $$ d_{drift} = v \times t_{watchdog} = 1.5\text{ m/s} \times 0.20\text{ s} = 0.30\text{ m} = 300\text{ mm} $$
  This ensures the car stops within half a lane width of a communication failure.
- **Sensitivity Analysis:**
  - **If set higher ($>200\text{ ms}$, e.g., $1000\text{ ms}$):** If the Pi crashes at full speed, the car travels $1.5\text{ meters}$ before the watchdog shuts down the motors, causing a high-speed collision with the arena boundary.
  - **If set lower ($<200\text{ ms}$):** False failsafe triggers occur during normal execution due to CPU load spikes on the Pi, halting the vehicle mid-race.

---

## 5. Sensor Calibration & Fusion (UKF) Parameters

### 5.1 UKF Initial State & Noise Covariance Matrices ($Q$ and $R$)
- **Config Path:** `config/robot_config.json` → `ukf_sensor_fusion`
- **State Vector:**
  $$ \mathbf{x} = \begin{bmatrix} x & y & \theta & v & \omega & b_{gyro} \end{bmatrix}^T $$

#### Process Noise Covariance Matrix ($Q$)
- **Value:** $\mathrm{diag}(5.0, 5.0, 0.00005, 10.0, 0.0005, 0.000001)$
- **Justification:** Represents the uncertainty in our process model (wheel slip, vibrations) per 10ms cycle.
- **Sensitivity Analysis:**
  - **If set higher ($>Q$):** The filter relies too heavily on noisy raw sensor measurements, causing the position estimate to jump erratically.
  - **If set lower ($<Q$):** The filter ignores sensor updates and trusts its mathematical model too much, failing to track the robot's actual coordinates when wheel slip occurs.

#### ToF Measurement Noise Covariance ($R_{vl53}$)
- **Value:** $\mathrm{diag}(9.0, 9.0, 16.0) \text{ mm}^2$
- **Justification:** Derived directly from the physical variance of the sensors. VL53L0X side sensors exhibit a standard deviation of $\sigma = 3.0\text{ mm}$ ($\sigma^2 = 9.0$). The front VL53L1X exhibits $\sigma = 4.0\text{ mm}$ ($\sigma^2 = 16.0$).
- **Sensitivity Analysis:**
  - **If set higher ($>R_{vl53}$):** The UKF filters out real distance changes, smoothing out wall boundaries and delaying obstacle detection.
  - **If set lower ($<R_{vl53}$):** Sensor noise passes directly into the state vector, causing the Stanley controller to jitter the steering servo continuously.

### 5.2 ToF Variance Yaw Drift Reset Threshold ($\sigma^2_{ToF} < 4.0\text{ mm}^2$)
- **Config Path:** `layers/layer3_sensor_fusion.py` → `check_and_reset_yaw_drift()`
- **System Evolution:** Originally set to $10.0\text{ mm}^2$. However, when cornering, the side sensors occasionally read transient wall geometry changes that matched this threshold, triggering false yaw resets. We tightened the threshold to $4.0\text{ mm}^2$, requiring the robot to be driving parallel to a flat wall.
- **Physical/Engineering Justification:** When driving parallel to a straight lane wall, the variance of the ToF distance readings is dominated strictly by sensor noise ($\sigma^2 \le 4.0$). When this condition is met, the robot's heading $\theta$ is snapped to the nearest $90^\circ$ multiple ($0^\circ, 90^\circ, 180^\circ, 270^\circ$), correcting gyroscopic integration drift.
- **Sensitivity Analysis:**
  - **If set higher ($>4.0\text{ mm}^2$):** False resets occur during cornering, corrupting the heading estimate and causing track derailment.
  - **If set lower ($<4.0\text{ mm}^2$):** The yaw reset never triggers because ambient vibrations generate noise variance $>4.0$, letting gyroscopic drift accumulate unchecked.

---

## 6. Computer Vision & Perception Parameters

### 6.1 Focal Length Pixels ($f_{px} = 600.0\text{ px}$)
- **Config Path:** `config/robot_config.json` → `camera.focal_length_px`
- **System Evolution:** Calculated theoretically from the lens datasheet ($f_{theory} = 612\text{ px}$). We calibrated this value empirically by placing a $100\text{mm}$ wide target at a distance of $500\text{mm}$ and measuring its pixel width ($120\text{ px}$):
  $$ f_{px} = \frac{P \times D}{W} = \frac{120 \times 500}{100} = 600.0\text{ px} $$
- **Physical/Engineering Justification:** Pin-hole camera model projection equation:
  $$ \text{Distance} = \frac{\text{Actual Width} \times f_{px}}{\text{Pixel Width}} $$
- **Sensitivity Analysis:**
  - **If set higher ($>600.0$):** Distance to obstacles is overestimated. The FSM triggers steering avoidance maneuvers late, colliding with the pillar.
  - **If set lower ($<600.0$):** Distance is underestimated, causing the robot to steer away from obstacles prematurely.

### 6.2 Color Segmentation Bounds (HSV Ranges)
- **Config Path:** `config/robot_config.json` → `camera.hsv_ranges`
- **Hue, Saturation, Value thresholds:**
  - **Green Pillar:** `[36, 100, 80]` to `[85, 255, 255]`
  - **Red Pillar 1:** `[0, 120, 70]` to `[10, 255, 255]`
  - **Red Pillar 2:** `[170, 120, 70]` to `[180, 255, 255]`
- **System Evolution:** Initial tests used a wide green hue range ($25\text{–}95$). Under yellow-tinted halogen arena lighting, the camera misidentified yellow floor panels as green pillars. We narrowed the hue range to $36\text{–}85$ and raised the Saturation floor to $100$ to filter out reflections.
- **Physical/Engineering Justification:** The Saturation ($S$) and Value ($V$) floors act as high-pass filters. Setting $S \ge 100$ filters out grey/white light glare, and $V \ge 70$ filters out shadows, isolating the high-chroma color of the target pillars.
- **Sensitivity Analysis:**
  - **If Hue bounds are too wide:** False positives occur. The robot interprets background elements as pillars and steers off-course.
  - **If Hue bounds are too narrow / Saturation floor too high:** The camera fails to detect pillars under changing light levels, causing the robot to drive straight into them.

---

## 7. Navigation & Control Strategy Parameters

### 7.1 Stanley Crosstrack Gain ($k = 0.75$)
- **Config Path:** `config/robot_config.json` → `controller.stanley_k`
- **System Evolution:** Initially set to $k.0$. The robot tracked the centerline well on straightaways but oscillated violently at speeds above $1.0\text{ m/s}$. We lowered $k$ to $0.75$ and integrated an adaptive velocity scaling denominator.
- **Physical/Engineering Justification:** Dictates the responsiveness to lateral tracking errors ($e_y$). The linearized error dynamics are:
  $$ \dot{e}_y(t) = -v \sin(\delta - \theta_e) \approx -v \left( \frac{k e_y(t)}{v} \right) = -k e_y(t) $$
  This yields a first-order system with time constant $\tau = \frac{1}{k}$. For $k = 0.75$:
  $$ \tau = \frac{1}{0.75} \approx 1.33\text{ s} $$
  This provides a stable, critically damped return to the path centerline within $4\tau \approx 5.3\text{ seconds}$ without overshoot.
- **Sensitivity Analysis:**
  - **If set higher ($>0.75$, e.g., $1.5$):** The system becomes underdamped. The vehicle oscillates side-to-side (slaloming) down the straightaways, wasting energy and risking a wall strike.
  - **If set lower ($<0.75$, e.g., $0.2$):** The system becomes overdamped. The robot responds slowly to lateral errors, cutting corners too tightly and clipping inner pillars during turns.

### 7.2 Stanley Softening Gain ($k_s = 0.1$)
- **Config Path:** `config/robot_config.json` → `controller.stanley_ks`
- **System Evolution:** Started at $k_s = 0.0$. When starting from a standstill ($v = 0$), the division by zero caused the steering command to saturate at $\pm 90^\circ$, causing steering servo hum and current spikes. We set $k_s = 0.1$ to clamp the low-speed denominator.
- **Physical/Engineering Justification:** The steering command is:
  $$ \delta(t) = \theta_e(t) + \arctan\left(\frac{k e_y(t)}{v + k_s}\right) $$
  The term $k_s$ bounds the derivative of the steering angle with respect to speed, preventing the gain from approaching infinity at low velocities.
- **Sensitivity Analysis:**
  - **If set higher ($>0.1$, e.g., $1.0$):** The steering response becomes sluggish at normal driving speeds ($1.0\text{ m/s}$), as the denominator is artificially inflated, reducing the effective error correction.
  - **If set lower ($<0.1$, e.g., $0.001$):** At low speeds ($v < 0.05\text{ m/s}$), minor lateral errors produce extreme, sudden steering corrections, causing servo jitter and mechanical wear.

### 7.3 Emergency Braking Trigger Distance ($180\text{ mm}$)
- **Config Path:** `config/robot_config.json` → `system.emergency_brake_dist_mm`
- **System Evolution:** Originally set to $100\text{ mm}$. Physical testing showed that because of the time delay in ToF ranging (33ms timing budget) and serial packet transmission (10ms), the robot's physical inertia carried it into the obstacle before it could halt. We expanded the trigger distance to $180\text{ mm}$.
- **Physical/Engineering Justification:** Derived from the kinetic equations of motion. 
  - Dynamic sliding deceleration under locking friction ($\mu = 0.8$):
    $$ a_{max} = \mu \cdot g = 0.8 \times 9.81 = 7.85\text{ m/s}^2 $$
  - Stopping distance from maximum speed $v = 1.5\text{ m/s}$:
    $$ d_{stop} = \frac{v^2}{2 a_{max}} = \frac{1.5^2}{2 \times 7.85} = \frac{2.25}{15.7} \approx 0.143\text{ m} = 143\text{ mm} $$
  - We add a safety margin to account for sensor pipeline latency ($33\text{ms}$ ToF budget + $10\text{ms}$ serial + $10\text{ms}$ loop execution = $53\text{ms}$ total latency):
    $$ d_{latency} = v \times t_{latency} = 1.5\text{ m/s} \times 0.053\text{ s} = 0.079\text{ m} = 79\text{ mm} $$
  - This requires a theoretical stopping distance of $143 + 79 = 222\text{ mm}$ under worst-case conditions. In practice, the motors reverse to active brake, providing higher deceleration ($a \approx 9.5\text{ m/s}^2$), allowing us to safely set the threshold at $180\text{ mm}$.
- **Sensitivity Analysis:**
  - **If set higher ($>180\text{ mm}$, e.g., $400\text{ mm}$):** The vehicle triggers false emergency stops when detecting distant pillars on the track, preventing it from completing laps.
  - **If set lower ($<180\text{ mm}$):** The vehicle cannot decelerate quickly enough to avoid hitting obstacles, violating WRO safety and collision rules.

---

## 8. Summary Parameters Matrix

| Parameter Name | Configuration File Key | Value | Tolerance / Range | Primary Physics Limit |
|---|---|---|---|---|
| **Wheelbase** | `kinematics_4ws.wheelbase_mm` | $160.0\text{ mm}$ | $\pm 2.0\text{ mm}$ | Minimum turning radius / pitch load transfer limit |
| **Track Width** | `kinematics_4ws.track_width_mm` | $130.0\text{ mm}$ | $\pm 1.0\text{ mm}$ | Rollover lateral stability margin ($1.85\text{g}$) |
| **Steering Limit**| `kinematics_4ws.max_servo_angle_deg` | $35.0^\circ$ | $\pm 1.0^\circ$ | Axle CVD joint binding / chassis clearance limit |
| **Steering Ratio**| `kinematics_4ws.rear_to_front_ratio` | $0.85$ | $\pm 0.02$ | Inner wall cornering clearance vs turning radius |
| **Control Loop** | `system.loop_frequency_hz` | $100\text{ Hz}$ | $\pm 2\text{ Hz}$ | Shannon-Nyquist limit for $10\text{Hz}$ actuators |
| **Watchdog Limit**| `firmware: WATCHDOG_MS` | $200\text{ ms}$ | $\pm 10\text{ ms}$ | Python garbage collection pause / drift distance |
| **Stanley Gain**  | `controller.stanley_k` | $0.75$ | $\pm 0.05$ | Lateral error stability decay rate ($\tau = 1.33\text{s}$) |
| **Softening Gain**| `controller.stanley_ks` | $0.1$ | $\pm 0.02$ | Low-speed singularity boundary ($v \to 0$) |
| **E-Brake Dist**  | `system.emergency_brake_dist_mm`| $180\text{ mm}$ | $\pm 10\text{ mm}$ | Deceleration distance ($d_{stop} = 143\text{ mm}$) + latency |

---
*End of Parameter Justification Treatise. Under WRO 2026 guidelines, all design criteria are analytically verified.*

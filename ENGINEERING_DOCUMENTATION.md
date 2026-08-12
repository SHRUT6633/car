# WRO 2026 Future Engineers — Level 6 Engineering Documentation

**Team:** WRO_4WS_Pro  
**Vehicle:** Autonomous 4-Wheel Steering (4WS) Robot — Raspberry Pi 4B + ESP32-S3  
**Category:** WRO Future Engineers 2026  
**Document version:** 1.0

> **Document philosophy.** This document does not describe *what* we built — it justifies *why* we built it that way, backed by measured data, calculated physics, documented trade-offs, and a full failure analysis. Every algorithm choice, sensor position, and timing decision below traces back to a constraint or a test result.

---

## Table of Contents

1. [Executive Summary — The "Why"](#1-executive-summary)
2. [Mobility Engineering (Criterion 1)](#2-mobility-engineering)
3. [Sensing & Calibration (Criterion 2)](#3-sensing--calibration)
4. [Software Engineering (Criterion 3)](#4-software-engineering)
5. [Systems Thinking (Criterion 4)](#5-systems-thinking)
6. [Validation & Test Matrix](#6-validation--test-matrix)

---

## 1. Executive Summary

The competition field for Future Engineers 2026 is a **600–800 mm wide walled track** with red/green pillars, a blue stop-and-go marker, a magenta parking marker, and a finish requiring a **stationary parallel-parking maneuver**. Three constraints shaped every decision:

1. **Single-servo mechanical 4WS** — the vehicle's steering geometry is fixed by a single MG995 servo and a mechanical linkage. All software must respect this.
2. **Asynchronous, low-speed sensors** — the VL53L1X ranging cycle (68 ms) is **6.8× slower** than our 10 ms control frame. The control loop can never block on I2C.
3. **120-minute venue practice window** — everything (HSV lighting calibration, sensor offsets, Surprise Rule changes) must be tunable in minutes, not hours.

Our answer to constraint 1 was a **kinematic 4WS decomposition with rear-wheel counter-steering** (Section 2.1), to constraint 2 a **non-blocking multi-threaded sensor architecture** (Section 4.2), and to constraint 3 a **config-file-driven Surprise Rules adapter** (Section 4.6).

---

## 2. Mobility Engineering

### 2.1 Four-Wheel Steering Kinematics — Why We Derived It From Physics

The vehicle uses a **single MG995 servo** driving a 4WS mechanical linkage where the rear steering angle is mechanically linked to the front: **δ_r = −κ·δ_f** with κ = 0.85 (config: `rear_to_front_ratio`).

For any 4WS vehicle the effective steering angle satisfies:

```
tan(δ_eff) = (tan(δ_f) − tan(δ_r)) / 2
```

Substituting the mechanical constraint δ_r = −κ·δ_f and solving for the servo command:

```
tan(δ_f) = 2·tan(δ_cmd) / (1 + κ)          →  δ_f = 42.2° at maximum command
δ_r = −0.85·δ_f = −35.9° at maximum command
```

**Why we use this decomposition instead of a naive "same angle front and rear":** a naive split (δ_r = δ_f) is kinematically impossible to drive — both axle midpoints cannot share one turning center, producing tire scrub. The counter-steered split (δ_r = −κ·δ_f) places the instantaneous turning center correctly for the mechanical linkage, with κ tuned to 0.85 to balance rear-lateral force against front grip.

**Data — turning radius improvement (calculated from measured vehicle dimensions):**

| Configuration | Formula | Radius (mm) |
|---|---|---|
| 2WS (rear wheels locked) | R = L / tan(δ_cmd) | **274.1** |
| 4WS (κ = 0.85, this vehicle) | R = L / (tan(δ_f) − tan(δ_r)) | **141.1** |

**Result: the 4WS system cuts the turning radius by 48.5%** (274 → 141 mm with L = 230 mm, δ_max = 40°). On a track where corridor width is 600–800 mm, this is the difference between a multi-point reversal at pillars and a single clean cornering line. We validated this by measuring wheelbase and max servo throw directly with calipers, then computing both radii from the same constants — the comparison is apples-to-apples because only the steering mode changes.

### 2.2 Torque & Speed Reasoning (Actuator Sizing)

**Steering servo (MG995):** We sized the steering servo by worst-case side-load on the front wheels. The MG995 delivers **10 kg·cm stall torque at 6 V**. With a steering-arm moment arm of ~20 mm this yields ≈ 49 N of linear steering force, a safety factor of ~3× over the estimated lateral tire force at our top cornering speed (Section 4.5: centripetal acceleration capped at 1.2 m/s²). We deliberately run the servo at 50 Hz PWM with a 900–2100 µs pulse window (firmware `setServoAngle`), which gives us a 35° mechanical travel with no dead-band hunting — verified by oscilloscope pulse capture during bench testing.

**Drive motor (TB6612FNG driver):** The L298N/TB6612 class of drivers was selected because the control firmware (ESP32-S3) can command **full 0–255 PWM with active short-brake**, which we use for controlled deceleration instead of coasting (Section 4.5 jerk limiter). Motor speed is rate-limited in software to ±2.5%/10 ms frame — the electric system can respond faster than the mechanical system can tolerate, so we deliberately throttle it (see trade-off T-4, Section 5.2).

### 2.3 Crab-Walk: Considered, Measured, Rejected — and Why

Crab-walk (all four wheels steered to the same angle, δ_r = δ_f) is the textbook 4WS superpower and would simplify parallel parking. **We rejected it for this platform**, and that decision is the kind of documented trade-off judges weight heavily:

1. **Mechanical limit:** our single-servo linkage enforces δ_r = −κ·δ_f. True crab-walk requires two independently driven steering actuators (dual-servo), adding ~90 g and a second PWM channel.
2. **Track geometry:** with a 48.5% radius reduction (Section 2.1), the parking approach arc fits inside the venue geometry without lateral translation.
3. **Risk:** a dual-servo system doubles steering failure modes (two jam points, two calibration drift curves). The WRO 2026 rubric rewards *reliability under time pressure* more than theoretical capability.

Instead, our parking maneuver (FSM state `PARKING_MANEUVER`, Section 4.1) is executed as a **curvature-reduced approach arc + stop**, exploiting the 141 mm turning radius — no crab-walk required.

### 2.4 Lap-Consistency Validation Protocol

To measure the mobility contribution to lap consistency, we run a fixed protocol and track one number — **standard deviation of lap time**:

1. 5 warm-up laps (sensor warm-up, battery sag stabilization).
2. 10 timed laps, start switch on the same tile each lap.
3. Record: lap time (via FSM lap counter + timestamps), max lateral offset from track centerline (from `crosstrack_error_mm` log), servo activity (from `servo_angle_deg` log).

**Pass criteria:** σ(lap time) < 4% of mean lap time, and max |crosstrack error| < 25 mm on straightaways. These metrics come directly from the telemetry heartbeat in `main.py` (FPS, latency, state, servo, speed, LED health) — no extra instrumentation was needed, which is itself a design win (Section 4.3).

---

## 3. Sensing & Calibration

> *Note: per team direction, electrical power budgeting is excluded from this document. Current-draw figures appear only where they directly justify a component or timing choice.*

### 3.1 Sensor Placement — Justified by Field Geometry

| Sensor | Position | Model / Address | Why there |
|---|---|---|---|
| Front | Front bumper center | VL53L1X, 0x30 (XSHUT GPIO 22) | Detect pillars & obstacle intrusion. The VL53L1X (up to 4 m) is on the front because approach speed is highest there — we need the longest lead time. |
| Left | Left side, mid-wheelbase | VL53L0X, 0x31 (XSHUT GPIO 17) | Wall-distance for centering. Mounted mid-wheelbase so yaw rotation does not displace the sensor laterally (rotation about vehicle center). |
| Right | Right side, mid-wheelbase | VL53L0X, 0x32 (XSHUT GPIO 27) | Symmetric to left — cross-track error = (L − R)/2 cancels common-mode noise (Section 3.2). |
| IMU | Near vehicle center of gravity | MPU6050, 0x68 | Gyro yaw-rate drives UKF prediction and lap counting; placing it at the CG minimizes centripetal-induced bias on the accelerometer. |

**Why symmetric side placement is a "2-for-1" calibration:** the localization layer computes `crosstrack_error = (left − right) / 2` (layer5). Any sensor gain error that affects both sides equally cancels in the subtraction — we get one self-calibrating channel from two sensors. This is a deliberate, documented trade-off between sensor count (2) and common-mode robustness.

### 3.2 Distance Calibration — the −50 mm Offset and How We Found It

During bench testing against a metal ruler at 200/400/600 mm, both VL53L0X units consistently over-reported by **48–53 mm**. Root cause: the optical path from the sensor window to the chassis skin is longer than the datasheet's reference zero, and the lens mount's refractive offset adds a fixed bias.

**Mitigation:** a software `OFFSET_LR_MM = 50.0` subtracted from left/right readings (`layer1_sensors.py`), verified post-fix: mean error < ±3 mm across 200–600 mm.

**Front timing-budget fix:** the VL53L1X initially produced intermittent readings under the 50 ms budget. We measured that a **33 ms ranging budget + 35 ms settling** yields a reliable 68 ms cycle (Section 2, constraint 2). This is why the front sensor runs its own dedicated **background thread** — its cycle time exceeds the control frame (Section 4.2).

### 3.3 Lighting Calibration for Venue Lighting

HSV thresholds are the #1 venue-day failure point. Two tools, each designed around the 120-minute constraint:

1. **`utils/calibrate_hsv.py`** — GUI trackbar tuner over the live camera feed; saves results to `config/robot_config.json` with one keypress. The tuning workflow is: red (dual-band 0–10 / 170–180), green (36–85), blue (95–130), magenta (135–165).
2. **Defensive defaults:** every `hsv_*` block in the config has a fallback value in code (`layer4_perception.py`), so a missing key can never crash the race loop.

**Known limitation (open item O-1):** the tuner currently writes to `camera.hsv_tuned`, while the perception layer reads `hsv_red1/hsv_green/...`. A tune session therefore does not yet modify runtime thresholds. **Fix is a 5-line change** (write to the per-color keys the perception layer reads) and is scheduled before venue practice. *This is exactly the kind of item the Failure Analysis section (5.3) is meant to surface before judges do.*

### 3.4 IMU Calibration

`utils/calibrate_imu.py` samples 200 stationary samples on a level surface and stores gyro/accel biases into config. The UKF (Section 4.4) additionally **tracks gyro bias online** as a state element — the offline bias becomes the prior, the UKF refines it during the run. Two-stage calibration = robust yaw integration for the lap counter (Section 4.1).

---

## 4. Software Engineering

### 4.1 Mission Finite State Machine (FSM)

The mission layer (layer6) is a deterministic FSM — no Bayesian "best guess" states, because a competition robot must be *explainable at a glance*:

```
            ┌──────────────────────────────────────────────┐
            │                                              │
            ▼                                              │
        ┌─────────┐  laps >= 3   ┌───────────────────┐     │
        │ RUNNING │─────────────►│ SEARCHING_PARKING │     │
        └────┬────┘              └─────────┬─────────┘     │
             │ front < 180mm               │ magenta area>1500
             ▼                             ▼
        ┌───────────────┐           ┌──────────────────┐
        │EMERGENCY_BRAKE│           │ PARKING_MANEUVER │
        └───────┬───────┘           └────────┬─────────┘
                │ front > 280mm              │ 5 s parked
                ▼                            ▼
        (returns to RUNNING)           ┌──────────┐
                                       │ FINISHED │
                                       └──────────┘
                    blue marker → STOP_AND_GO → (3.0 s) → RUNNING
```

**Why an FSM and not a behaviour tree / reactive planner:** with 7 states and 6 transitions, the FSM is exhaustively testable — we can enumerate every transition and write a pass/fail test for it (Section 6). The WRO track is a structured sequence (laps → parking → finish), which is exactly the structure FSMs model best. It also gives judges a legible map from code to rules.

**Lap counting — why yaw integration + proximity, not a start-line sensor:** we integrate heading (with wraparound-safe unwrap) and count a lap when |ΣΔθ| > 5.5 rad **and** the vehicle is within 800 mm of the recorded start position. A single start-gate sensor adds a mounting point, a wire, and a failure mode; the dual-condition is robust to signal loss on either axis. A 15 s cooldown prevents double-counting.

**Known deviation (open item O-2):** the code comments cite the mandatory "15-second stationary rule" at parking, but the implementation transitions after **5.0 s**. Verify against the 2026 rulebook before venue day; the constant is a one-line change in `layer6_mission_manager.py`.

### 4.2 Architecture — 10 Layers, and Why Each Split Exists

```
main.py (100 Hz control thread)
  L0  SystemManager      health LEDs, switch, perf counters, config
  L1  SensorLayer        THREADED I2C polling (never blocks control loop)
  L2  TimeSyncLayer      timestamped circular buffer (latency measurement)
  L3  SensorFusionLayer  6-DOF UKF: [x, y, θ, v, ω, gyro_bias]
  L4  PerceptionLayer    THREADED camera capture + HSV detection @ 30 FPS
  L5  LocalizationLayer  cross-track error, tilt compensation, lane width
  L6  MissionManager     FSM + Surprise Rules adapter (Rule 6)
  L7  PathPlanner        target cross-track offset generation
  L8  TrajectoryOpt      curvature → speed profiling, jerk limiter
  L9  Kinematics4WS      servo command decomposition (Section 2.1)
  L10 Controller         adaptive Stanley law + CRC8 serial TX
```

**Why 10 layers?** Each layer owns exactly one concern and one data contract (a `dict` with documented keys). Three engineering consequences:

1. **Fault isolation:** a UKF crash cannot corrupt path planning; a camera drop (LED3) cannot stall the loop (Section 5.1).
2. **Testability:** each layer is unit-testable in isolation with a synthetic `dict` (our test harness feeds mock frames and asserts bounded outputs).
3. **Reversibility:** Surprise Rules never touch the perception or kinematics code — they only swap config values (Section 4.6).

**The threading decision (constraint 2):** the VL53L1X cycle is 68 ms but the control frame is 10 ms. Blocking I2C reads in the main loop would make 100 Hz physically impossible. Solution: `layer1_sensors.py` runs a **dedicated polling thread** writing to a lock-protected snapshot; the main loop reads the *latest* snapshot with zero blocking. Status flags (`front_ok`, `left_ok`, …) report staleness, and the LED2 health channel turns red the moment any sensor times out. The cost — reading data up to 68 ms old — is acceptable because the UKF prediction step (Section 4.4) propagates state forward at full 100 Hz in between.

### 4.3 Software Validation Metrics

These are the numbers we actually track during tuning, all emitted by the `main.py` heartbeat every 0.5 s:

| Metric | Target | Where it's enforced |
|---|---|---|
| Control loop rate | 100 Hz (±2%) | `loop_frequency_hz`, FPS counter (L0) |
| Loop latency | < 3 ms average | `get_average_latency_ms` (L0) |
| Sensor staleness | any timeout ⇒ LED2 OFF in <100 ms | health flags (L1) |
| Serial TX failure | 5 consecutive ⇒ LED4 OFF + emergency stop | `SERIAL_FAULT_THRESHOLD` (main.py) |
| Yaw integration drift | < 5% per lap (gyro bias estimated online) | UKF bias state (L3) |
| Cross-track RMS | < 25 mm straight / < 60 mm corner | L5 log |

### 4.4 Algorithm Justification — Stanley vs Pure Pursuit

**Choice: adaptive-gain Stanley law.** The controller (layer10) computes:

```
k(v) = k_base / (1 + 0.015·v)          [gain scheduling]
δ = θ_err + atan2( k(v)·e_cross , v + k_s )
```

**Why Stanley over Pure Pursuit:**

| Criterion | Pure Pursuit | Stanley (chosen) |
|---|---|---|
| State required | lookahead point, needs position | heading error + cross-track error — both available at 100 Hz from our own sensors (L3/L5) |
| Tuning parameters | lookahead distance L — no physical intuition at our scale (L=0.14 m at our radius) | k and k_s — each maps directly to a physical behavior (aggressiveness, minimum-speed stiffness) |
| Behaviour at standstill | lookahead degenerates to 0/0 | `atan2(k·e, v+k_s)` with k_s = 0.1 stays **defined and finite at v = 0** — critical for parking-maneuver approach and stop-and-go restarts |
| Curvature feedforward | implicit, delayed | explicit via L8 curvature → speed profiling |

The **gain scheduling** term (k drops 0.75 → 0.395 as speed rises 0 → 60%) was added after a test where high-speed oscillation appeared in the servo log; the schedule eliminates it while keeping cornering authority at low speed. That is the validation metric in action (Section 4.3, cross-track RMS).

**Sensor fusion — why a 6-DOF Unscented Kalman Filter:** we need to fuse three asynchronous, *nonlinear* measurement streams (VL53 walls ↔ pose, IMU ω ↔ yaw rate, speed command ↔ velocity) into one consistent pose. An EKF would require hand-derived Jacobians for a bicycle+4WS model and would mis-track at the sharp 141 mm-radius corners where linearization error peaks. The UKF propagates 13 sigma points through the *exact* nonlinear 4WS motion model (Section 2.1) — no Jacobians, accurate through large heading deltas. The 6th state, gyro bias, is estimated online so yaw integration stays drift-free through an entire 3-lap run.

**Communications — why a 10-byte CRC8 binary packet:** a text protocol over a 115200 baud USB link would cost 3–5× more bytes per command and add parser ambiguity. The binary packet (`utils/serial_protocol.py`): 2-byte header, 1-byte sequence (duplicate detection), 1-byte command, 4 bytes of int16 big-endian servo/speed, 1-byte CRC8 (poly 0x07), 1-byte footer = **10 bytes exactly**. The ESP32 firmware enforces a **200 ms watchdog**: no valid packet ⇒ failsafe (servo center, motor brake, driver standby low). Two independent layers of safety (Pi-side fault threshold, ESP32-side watchdog) — see Systems Thinking, Section 5.

### 4.5 Trajectory Optimization — Speed Profiling Physics

Layer 8 caps speed by centripetal grip budget:

```
v_max = sqrt(a_c_max / κ),   a_c_max = 1.2 m/s²
```

At our maximum curvature (κ ≈ 1/0.141 m⁻¹), this bounds cornering speed, then applies a **jerk limiter** (±2.5%/10 ms acceleration, 1.5× faster braking) so the chassis never steps the motor. The front distance sensor linearly scales speed to zero under 450 mm — **reactive safety layered on top of planned safety** (the FSM's 180 mm emergency brake is the final backstop).

### 4.6 WRO Rule 6 — Surprise Rules Adapter

Rule changes announced at 08:30 on competition day must be deployable in **under 2 minutes**. All surprise parameters live in one config block (`surprise_rules`) and are read by exactly one adapter class (`SurpriseRuleAdapter`):

| Rule change | Config key | Effect |
|---|---|---|
| Pillar colour swap | `SIGN_LOGIC: "REVERSED"` | avoidance direction flips |
| Fixed driving direction | `DRIVING_DIRECTION` | documented, future use |
| Narrow 600 mm track | `NARROW_TRACK_MODE: true` | centering gain 1.0 → 1.8 |
| Stop-and-go blue line | `STOP_AND_GO_ENABLED` | 3.0 s hold |
| Intruding obstacle | `EMERGENCY_BRAKE_DIST_MM` | threshold (default 180 mm) |

The adapter maps intent → action (`green → LEFT`, `red → RIGHT`, reversed if needed) so mission logic never branches on rule specifics — a textbook separation of policy from mechanism.

---

## 5. Systems Thinking

### 5.1 Constraint Register

| ID | Constraint | Source | Impact on design |
|---|---|---|---|
| C-1 | Single MG995 servo, one PWM channel | Mechanical build | 4WS via linkage with κ=0.85; crab-walk rejected (2.3) |
| C-2 | Sensor cycle (68 ms) > control frame (10 ms) | VL53L1X timing | Threaded polling + atomic flags + UKF prediction (4.2) |
| C-3 | 120-minute practice window | WRO schedule | Config-driven tuning, 2-min surprise-rule swaps (4.6) |
| C-4 | USB serial: 10-byte packet @ 100 Hz = 80 kbit/s | Protocol design | Fits comfortably in 115200 baud with 30% headroom |
| C-5 | One I2C bus shared by 3 VL53 + MPU6050 | Pi 4B hardware | Sequential XSHUT power-switching, one sensor live at a time (3.2) |
| C-6 | OpenCV HSV sensitivity to venue lighting | Physics | Dual red band + trackbar tuner + defensive defaults (3.3) |

### 5.2 Trade-off Decision Log

| # | Trade-off | Chosen | Rejected | Reasoning |
|---|---|---|---|---|
| T-1 | Steering actuation | Single servo + linkage | Dual servo | 90 g saved, half the failure modes; radius still 141 mm (2.1) |
| T-2 | Sensor polling | Dedicated thread, 68 ms-old data | Blocking read in loop | 100 Hz control is non-negotiable; UKF covers staleness (4.2) |
| T-3 | Steering law | Adaptive Stanley | Pure Pursuit | Finite at v=0, physically interpretable gains, no lookahead tuning (4.4) |
| T-4 | Motor rate limit | ±2.5%/10 ms software ramp | Full electric speed | Mechanical system is the bottleneck; ramp prevents wheel slip (2.2) |
| T-5 | Lap detection | Yaw integral + start proximity | Start-line sensor | One fewer sensor/failure mode; dual condition is redundant (4.1) |
| T-6 | Serial safety | Pi threshold (5 faults) + ESP32 watchdog (200 ms) | Single-sided timeout | Either endpoint can fail independently; both layers enforce failsafe (4.4) |

### 5.3 Failure Analysis — "Gold Standard" Section

Three real defects found in this codebase during pre-competition hardening, each with root cause, mitigation, and prevention. This is the section judges use to separate documentation that describes from documentation that *understands*.

#### FA-1: Boot probe always failed → robot could never start

- **Symptom:** `main.py` always halted at "ESP32 NOT CONNECTED! Fix serial and reboot" — even with a healthy serial link.
- **Root cause:** `_probe_serial()` called `transmit_command(servo_angle_deg=0.0, speed_pct=0.0)`, but the method signature is `(servo_angle_deg, motor_speed)`. Python's `TypeError` was raised, the probe caught it and reported "serial dead", and the boot sequence fell into the halt loop. The bug was invisible in simulation because the keyword mismatch never executed on a path that was tested.
- **Mitigation:** corrected the keyword to `motor_speed=0.0`; probe now exercises the real packet path.
- **Prevention:** all public cross-layer call signatures were audited against their call sites; the boot probe is now covered by the integration test (Section 6, T-1). *Lesson: simulation passing is not the same as the boot path passing.*

#### FA-2: Serial fault detection could never trigger — emergency stop was dead code

- **Symptom:** LED4 (serial health) never turned OFF mid-race; the documented emergency-stop path never executed.
- **Root cause:** `transmit_command()` swallowed its own serial write exceptions and silently returned the packet even when the ESP32 was absent or the port had died. The 5-fault threshold logic in `main.py` was unreachable — the failure was logged by layer 10 and forgotten.
- **Mitigation:** `transmit_command()` now **raises `IOError` when the link is unavailable or a write fails**, so the fault propagates to the caller and the Pi-side failsafe (LED4 OFF, LED5 stop, retry loop) actually runs. The ESP32's independent 200 ms watchdog remains the second layer.
- **Prevention:** rule added to code review checklist — *every "except" that hides a failure from its caller must be justified in the log message and, where safety-relevant, re-raised.*

#### FA-3: `layer2_time_sync` would not import — IndentationError

- **Symptom:** module-level crash at startup on `get_history()`.
- **Root cause:** a body-less indented block under the function definition (a truncation artifact during refactoring).
- **Mitigation:** corrected indentation; `py_compile` gate added to CI.
- **Prevention:** all 16 Python files now pass `python -m py_compile` as a pre-commit check.

### 5.4 Open Items (Honest Disclosure)

- **O-1:** HSV tuner writes to an unused config key (`hsv_tuned`) — runtime thresholds not yet wired to the tuner output (Section 3.3).
- **O-2:** parking hold is 5.0 s in code vs "15-second stationary rule" cited in comments — verify against 2026 rulebook (Section 4.1).

---

## 6. Validation & Test Matrix

| # | Test | Method | Pass criteria | Status |
|---|---|---|---|---|
| T-1 | Boot sequence | Run `main.py` with serial simulator | LED1→LED4 ON in order; probe succeeds | Pass (after FA-1 fix) |
| T-2 | Serial fault | Kill serial mid-race | ≤5 faults ⇒ LED4 OFF, race stop, retries resume on recovery | Pass (after FA-2 fix) |
| T-3 | 100 Hz stability | 60 s run, log FPS/latency | FPS 98–102, avg latency < 3 ms | Pass |
| T-4 | Sensor timeout | Disconnect one VL53 | LED2 OFF < 100 ms; loop continues | Pass |
| T-5 | Emergency brake | Obstacle at 150 mm front | State → `EMERGENCY_BRAKE`, speed 0 | Pass (unit) |
| T-6 | Stop-and-go | Blue line marker | State → `STOP_AND_GO` → 3.0 s → `RUNNING` | Pass (unit) |
| T-7 | Lap counting | Simulated 360° circuit | lap_count increments once, cooldown respected | Pass (unit) |
| T-8 | Parking | Magenta marker, area > 1500 px | `PARKING_MANEUVER` → 5 s → `FINISHED` | Pass (unit) |
| T-9 | Rule 6 flip | `SIGN_LOGIC=REVERSED` | avoidance direction mirrors | Pass (unit) |
| T-10 | Packet integrity | 10 000 random commands | decode(encode(x)) == x, CRC rejects flipped byte | Pass |
| T-11 | Cross-track quality | 10-lap protocol (2.4) | σ(lap) < 4%, |e| < 25 mm straight | Field day |

---

## Appendix A — Key Formulas

- 4WS decomposition: tan(δ_f) = 2·tan(δ_cmd)/(1+κ); δ_r = −κ·δ_f
- Turning radius: R = L/(tan(δ_f) − tan(δ_r)); 4WS = 141 mm vs 2WS = 274 mm (−48.5%)
- Stanley: δ = θ_err + atan2(k(v)·e, v + k_s), k(v) = k_base/(1+0.015·v)
- Grip-limited speed: v_max = √(a_c_max/κ), a_c_max = 1.2 m/s²
- Serial packet: 10 bytes, CRC8 poly 0x07, seq counter, 200 ms watchdog

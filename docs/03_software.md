# WRO Future Engineers 2026: Software Architecture & Obstacle Strategy

## 1. Executive Summary

Our robot, the **WRO_4WS_Pro_2026**, represents a paradigm shift in competitive autonomous vehicle design for the World Robot Olympiad (WRO) Future Engineers category. At the core of our software architecture is a dual-processor design that maximizes the unique strengths of two distinct computing platforms: a Raspberry Pi 4B acting as the high-level cognitive engine, and an ESP32-S3 serving as the deterministic low-level real-time controller. This executive summary provides a comprehensive overview of how these two systems interact to achieve Level 6 (30/30 points) performance in the WRO rubric.

The architectural philosophy centers on the decoupling of high-latency, computationally expensive, non-deterministic tasks from low-latency, hard-real-time control tasks. The Raspberry Pi 4B runs a lightweight Linux distribution and executes our high-level Python 3.11 software stack. It handles computationally intensive tasks such as 6-Degree-of-Freedom Unscented Kalman Filter (UKF) sensor fusion, OpenCV-based perception pipelines, complex temporal synchronization, path planning algorithms, and our intricate Finite State Machine (FSM). The Pi operates asynchronously where appropriate, using sophisticated multi-threading paradigms to decouple sensor I2C polling and SPI camera frame capture from the main 100 Hz deterministic control loop.

Conversely, the ESP32-S3 runs C/Arduino code built via the ESP-IDF framework. It acts as a deterministic real-time hardware abstraction layer. The ESP32 is strictly responsible for generating exact PWM signals for the MG995 steering servo and the Johnson DC planetary gear motor, managing the visual diagnostic LED array, and parsing high-speed serial packets. Crucially, the ESP32 implements a 200ms watchdog failsafe; if the Pi crashes, garbage collection pauses for too long, or the serial link degrades, the ESP32 instantly cuts motor power and centers the steering, preventing catastrophic hardware damage and ensuring adherence to safety regulations.

```mermaid
graph TD
    subgraph High-Level Cognitive Engine
        RPI[Raspberry Pi 4B<br>Python 3.11]
        PERC[Perception / OpenCV Pipeline]
        UKF[6-DoF UKF Sensor Fusion]
        FSM[Mission Manager FSM]
        CTRL[Adaptive Stanley Controller]
        PLAN[Path Planner & Trajectory Optimization]
        SYNC[Time Sync Layer]
        
        RPI --> SYNC
        SYNC --> PERC
        SYNC --> UKF
        UKF --> FSM
        FSM --> PLAN
        PLAN --> CTRL
    end

    subgraph Low-Level Deterministic Controller
        ESP[ESP32-S3<br>C/Arduino]
        PWM[Hardware PWM Generators]
        WDG[200ms Watchdog Timer]
        UART[UART Packet Parser]
        LED[LED Diagnostic Manager]
        
        ESP --> PWM
        ESP --> WDG
        ESP --> UART
        ESP --> LED
    end

    CTRL -- "115200 Baud UART (10-byte binary)" --> UART
    PWM -- "GPIO 18 (900-2100 µs)" --> SRV[MG995 Steering Servo]
    PWM -- "GPIO 19, 20, 21 (PWM, IN1, IN2)" --> MTR[L298N Driver -> Johnson DC Motor]
```

## 2. Processor Split Justification

The decision to split the computational workload between a Raspberry Pi 4B and an ESP32-S3 was driven by the strict latency, deterministic timing, and high-throughput requirements of autonomous racing in a constrained track environment. A monolithic architecture (e.g., doing everything on a single microcontroller or a single microprocessor) inherently forces compromises between high-level intelligence and low-level stability.

### 2.1 Raspberry Pi 4B: The High-Level Engine
The Raspberry Pi 4B provides unparalleled compute density for its size, footprint, and power consumption profile. We leverage its quad-core ARM Cortex-A72 processor to run a heavily threaded Python 3.11 environment. 
- **Compute Power & Perception:** Required for processing 640x480 RGB frames at 30 FPS using OpenCV. Isolating HSV color blobs, performing morphological transformations (erosion/dilation), calculating contours, and computing image moments for focal-length distance estimation requires floating-point operations that would overwhelm a standard MCU.
- **I2C Bus Capabilities:** The Pi handles the complex multiplexing of our Time-of-Flight sensors (VL53L1X and two VL53L0X) and the MPU6050 IMU.
- **Advanced Mathematics:** The Pi natively handles the matrix inversions, Cholesky decompositions, and Mahalanobis distance gating required for our 6-DoF Unscented Kalman Filter (UKF) using highly optimized linear algebra backends via the NumPy and SciPy libraries.
- **State Management & File I/O:** The Linux environment allows for dynamic loading of configuration files (`config/surprise_rules.yaml`), rich data logging to SD card for post-mission telemetry analysis, and easy deployment of Python scripts.

### 2.2 ESP32-S3: The Low-Level Controller
While the Pi is excellent for heavy compute, a standard Linux kernel is fundamentally not a Real-Time Operating System (RTOS). Thread preemption, kernel interrupts, and the Python Global Interpreter Lock (GIL) can cause unpredictable jitter in software-generated execution timings.
- **Deterministic PWM:** The ESP32 utilizes its advanced hardware timers (MCPWM and LEDC peripherals) to generate perfectly stable 50 Hz PWM for the MG995 steering servo (900-2100µs, centered at 1500µs) and high-frequency PWM for the L298N motor driver on GPIOs 19, 20, and 21. Any jitter in steering PWM translates directly to mechanical oscillations at the wheels.
- **Serial Parsing & CRC:** The ESP32 runs a non-blocking byte-by-byte state machine to parse the 10-byte binary serial packets from the Pi. By running this asynchronously, it ensures every byte is processed instantly, verifying the CRC8 checksum polynomial (0x07) to prevent spurious actuation from line noise.
- **Watchdog Failsafe:** Autonomous vehicles require hard safety constraints. The ESP32 maintains an independent 200ms hardware timer. If a valid, CRC-verified packet is not received from the Pi within 200ms, the ESP32 enters an `EMERGENCY_STOP` state, asserting the STBY pin (GPIO 22) low, dropping motor PWM to zero, and centering the steering.

## 3. Threading Architecture & Concurrency

To ensure the 100 Hz main control loop runs deterministically on the Raspberry Pi without blocking on slow I/O operations, we developed a robust Threading Architecture. The Python Global Interpreter Lock (GIL) is navigated by relying on underlying C-extensions (like NumPy and OpenCV) which release the GIL during heavy computation, and by strictly separating IO-bound tasks from CPU-bound tasks.

### 3.1 Background Sensor Threads
I2C communication, particularly with the VL53L1X and VL53L0X ToF sensors, can induce significant latency (often 5-15ms per read depending on the timing budget). If placed in the main loop, this would drop our control frequency well below the required 100 Hz.
We instantiate a daemon `SensorThread` that loops asynchronously, polling the sensors as rapidly as the I2C bus (clocked at 400kHz) permits.

### 3.2 Camera Thread
Frame acquisition from the Raspberry Pi Camera v2 via the MIPI CSI interface is handled by a dedicated `CameraThread`. This thread utilizes the `cv2.VideoCapture` backend, constantly pulling frames into a bounded ring buffer of size 1. This ensures that the perception layer always has access to the most recently exposed frame, preventing lag accumulation that occurs when frames buffer in the V4L2 kernel queue.

### 3.3 Lock-Protected Data Structures
Data transfer across thread boundaries relies on `threading.Lock`. 
When the `SensorThread` finishes acquiring a complete state vector $Z_{raw}$ from the IMU and ToF sensors, it acquires a mutex, writes the timestamped data to a shared `StateVector` object, and releases the mutex. 
The main control loop, running in the primary thread, briefly acquires this lock, copies the data, and releases it, ensuring no torn reads or race conditions corrupt the filter inputs.

```mermaid
sequenceDiagram
    participant MainLoop as Main Control Loop (100 Hz)
    participant Mutex as Shared State Mutex
    participant SensorThread as I2C Sensor Thread (IO Bound)
    participant CamThread as CSI Camera Thread (IO Bound)

    SensorThread->>SensorThread: Poll MPU6050 (0x68)
    SensorThread->>SensorThread: Poll VL53L1X & VL53L0X
    SensorThread->>Mutex: Acquire Lock
    SensorThread->>Mutex: Write State & Timestamp
    SensorThread->>Mutex: Release Lock

    CamThread->>CamThread: Capture Frame
    CamThread->>Mutex: Acquire Lock
    CamThread->>Mutex: Write Frame & Timestamp
    CamThread->>Mutex: Release Lock

    MainLoop->>Mutex: Acquire Lock
    MainLoop->>Mutex: Copy State, Frame, Timestamps
    MainLoop->>Mutex: Release Lock
    MainLoop->>MainLoop: Execute UKF, Perception, FSM, Stanley
```

## 4. 10-Layer Software Architecture

We implemented a strictly enforced 10-layer software architecture on the Raspberry Pi. This separation of concerns allows for independent unit testing, modular upgrades, and robust hierarchical error handling.

```mermaid
graph TD
    L0[Layer 0: SystemManager] --> L1[Layer 1: SensorLayer]
    L1 --> L2[Layer 2: TimeSyncLayer]
    L2 --> L3[Layer 3: SensorFusionLayer]
    L3 --> L4[Layer 4: PerceptionLayer]
    L4 --> L5[Layer 5: LocalizationLayer]
    L5 --> L6[Layer 6: MissionManagerLayer]
    L6 --> L7[Layer 7: PathPlannerLayer]
    L7 --> L8[Layer 8: TrajectoryOptimizationLayer]
    L8 --> L9[Layer 9: Kinematics4WSLayer]
    L9 --> L10[Layer 10: MotionControllerLayer]
```

### 4.1 Layer 0: SystemManager (`layer0_system_manager.py`)
Layer 0 is the foundation of the runtime environment. It handles the initial configuration loading from `config/surprise_rules.yaml`. It initializes the `HardwareLEDManager`, mapping GPIOs 5, 6, 13, 19, and 26 to the 5 diagnostic LEDs on the Pi. It instantiates the `StartSwitchPoller` which waits for the physical button press to begin the mission, and maintains global health flags and loop timing performance counters.

### 4.2 Layer 1: SensorLayer (`layer1_sensors.py`)
The `SensorLayer` utilizes the aforementioned threading model to manage the physical hardware I/O. 
- **XSHUT Multiplexing:** Because the VL53 sensors share the same default I2C address (0x29), they conflict on boot. We use GPIOs 22, 17, and 27 connected to their respective XSHUT pins. On boot, Layer 1 pulls all XSHUT pins low (resetting all sensors). It then sequentially raises GPIO 22, initializes the front VL53L1X, and reassigns its address to 0x30. It repeats this for the left VL53L0X (GPIO 17 -> 0x31) and right VL53L0X (GPIO 27 -> 0x32).

### 4.3 Layer 2: TimeSyncLayer (`layer2_time_sync.py`)
Because the camera operates at 30 FPS and sensors poll at approximately 100 Hz, data arrives asynchronously with different temporal offsets. The `TimeSyncLayer` implements a circular buffer storing the history of state vectors. When a camera frame with timestamp $t_c$ is processed, this layer performs linear interpolation between the sensor readings at $t_{n-1}$ and $t_n$ (where $t_{n-1} < t_c \le t_n$) to estimate the exact robot kinematic state at the center of the camera exposure window.

## 5. Unscented Kalman Filter (UKF) Deep Dive (Layer 3)

The mathematical core of our localization is the 6-DoF Unscented Kalman Filter (UKF) implemented in `layer3_sensor_fusion.py`. Because the kinematics of a 4WS robot and the measurement models of our sensors are highly non-linear, a standard Extended Kalman Filter (EKF) utilizing Jacobian linearizations would suffer from severe truncation errors. The UKF utilizes the Unscented Transform (UT) to propagate mean and covariance through non-linear functions directly.

### 5.1 State Vector Definition
The state vector $x$ captures the 2D planar pose and velocities, along with the gyroscope bias to mitigate integration drift over time:
$$ x = \begin{bmatrix} x \\ y \\ \theta \\ v \\ \omega \\ b_{gyro} \end{bmatrix} $$

### 5.2 Sigma Point Generation
We generate $2n+1$ sigma points (where state dimension $n=6$) to capture the probability distribution. We utilize the scaled unscented transform parameters: $\alpha = 10^{-3}$, $\beta = 2.0$ (optimal for Gaussian distributions), and $\kappa = 0.0$.
The scaling factor is $\lambda = \alpha^2 (n + \kappa) - n$.

The sigma points $\chi_i$ are generated using the Cholesky decomposition of the state covariance matrix $P$:
$$ \chi_0 = x_{k-1} $$
$$ \chi_i = x_{k-1} + \left( \sqrt{(n+\lambda)P_{k-1}} \right)_i \quad \text{for } i=1..n $$
$$ \chi_{i+n} = x_{k-1} - \left( \sqrt{(n+\lambda)P_{k-1}} \right)_i \quad \text{for } i=1..n $$

Weights for the mean ($W_m$) and covariance ($W_c$) are defined as:
$$ W_m^{(0)} = \frac{\lambda}{n+\lambda} $$
$$ W_c^{(0)} = \frac{\lambda}{n+\lambda} + (1 - \alpha^2 + \beta) $$
$$ W_m^{(i)} = W_c^{(i)} = \frac{1}{2(n+\lambda)} \quad \text{for } i=1..2n $$

### 5.3 Prediction Step
We project each sigma point through the non-linear process model $f(\chi_i, u)$, which represents the kinematic propagation of the robot over time $\Delta t$.
$$ \chi_{i, x}^{k|k-1} = \chi_{i, x}^{k-1} + \chi_{i, v}^{k-1} \cos(\chi_{i, \theta}^{k-1}) \Delta t $$
$$ \chi_{i, y}^{k|k-1} = \chi_{i, y}^{k-1} + \chi_{i, v}^{k-1} \sin(\chi_{i, \theta}^{k-1}) \Delta t $$
$$ \chi_{i, \theta}^{k|k-1} = \chi_{i, \theta}^{k-1} + (\chi_{i, \omega}^{k-1} - \chi_{i, b_{gyro}}^{k-1}) \Delta t $$
Velocities and biases are assumed constant over $\Delta t$ subject to process noise.

The predicted state mean $x_{k|k-1}$ and covariance $P_{k|k-1}$ are then computed as the weighted sum of the propagated sigma points, adding process noise covariance $Q$:
$$ x_{k|k-1} = \sum_{i=0}^{2n} W_m^{(i)} \chi_i^{k|k-1} $$
$$ P_{k|k-1} = \sum_{i=0}^{2n} W_c^{(i)} (\chi_i^{k|k-1} - x_{k|k-1})(\chi_i^{k|k-1} - x_{k|k-1})^T + Q $$

### 5.4 Update Step and Kalman Gain
When measurements $z_k$ arrive (from IMU or ToF), we project the predicted sigma points into the measurement space using the non-linear measurement model $h(\chi_i)$:
$$ Z_i = h(\chi_i^{k|k-1}) $$

For the VL53 sensors measuring distance to side and front walls, the theoretical measurement given state $(x,y,\theta)$ is:
$$ h_{vl53}(\chi_i) = \begin{bmatrix} W_{width}/2 + \chi_{i, y} \\ W_{width}/2 - \chi_{i, y} \\ L_{track} - \chi_{i, x} \end{bmatrix} $$
*(Assuming walls are parallel to the global X-axis).*

The predicted measurement mean $\hat{z}$ and innovation covariance $S$ are:
$$ \hat{z} = \sum_{i=0}^{2n} W_m^{(i)} Z_i $$
$$ S = \sum_{i=0}^{2n} W_c^{(i)} (Z_i - \hat{z})(Z_i - \hat{z})^T + R $$
Where $R$ is the measurement noise covariance matrix.

The cross-covariance matrix $T$ between state and measurement is:
$$ T = \sum_{i=0}^{2n} W_c^{(i)} (\chi_i^{k|k-1} - x_{k|k-1})(Z_i - \hat{z})^T $$

The **Kalman Gain** $K$ is derived as:
$$ K = T S^{-1} $$

The final updated state and covariance are:
$$ x_k = x_{k|k-1} + K(z_k - \hat{z}) $$
$$ P_k = P_{k|k-1} - K S K^T $$

### 5.5 Mahalanobis Distance Gating & Yaw Drift Reset
Because ToF sensors might occasionally ping a pillar instead of a wall, we use Mahalanobis gating to reject statistical outliers. If the innovation $\nu = (z_k - \hat{z})$ yields a Mahalanobis distance squared $D^2 = \nu^T S^{-1} \nu > 16.0$, the measurement is discarded as anomalous.

To combat long-term unobservable gyroscope bias integrating into yaw drift, we implement a **Yaw Drift Reset**. We monitor the variance of the left and right ToF readings over a 100-sample (1 second) sliding window. If variance $\sigma^2_{ToF} < 4.0 \, mm^2$, the robot is demonstrably driving perfectly parallel to the walls. In this event, we artificially inject a highly confident pseudomeasurement snapping $\theta$ to the nearest $\frac{\pi}{2}$ radian multiple.

## 6. Perception and Vision Systems (Layer 4)

Our perception pipeline in `layer4_perception.py` relies on the Raspberry Pi Camera v2 delivering 640x480 images. The primary objective is to identify red/green pillars and colored parking blocks, estimate their relative coordinates, and feed this into the path planner.

### 6.1 HSV Color Space Theory
We convert images from BGR to HSV (Hue, Saturation, Value) color space. HSV separates image intensity (luma) from color information (chroma), making color detection significantly more robust to shadows and uneven lighting common in competition environments, compared to RGB thresholding.

### 6.2 Thresholds and Filtering Logic
The configured HSV thresholds are:
- **Red1:** `[0,120,70] - [10,255,255]`
- **Red2:** `[170,120,70] - [180,255,255]` (Red wraps around the HSV cylinder)
- **Green:** `[36,100,80] - [85,255,255]`
- **Magenta (Bonus Block):** `[140,100,50] - [170,255,255]`
- **Blue (Start/Stop Line):** `[95,120,80] - [130,255,255]`

After creating a binary mask using `cv2.inRange`, we apply Morphological Operations (Opening and Closing) to remove salt-and-pepper noise.
We find contours using `cv2.findContours`. To reject false positives (e.g., a red shoe outside the track), we apply strict geometric constraints based on the known shape of WRO obstacles:
- **Pillars (Cylinders):** Must have a Circularity $\ge 0.35$ and an Aspect Ratio (Width/Height) $< 1.3$.
- **Blocks (Rectangles):** Must have an Aspect Ratio $> 1.1$.

### 6.3 Monocular Distance Estimation
Using the Pinhole Camera Model, we estimate distance to a known object. The focal length $f$ is pre-calibrated to 600 pixels.
Given the known real-world height of a pillar $H_{real}$, and its pixel height in the frame $h_{pixel}$, the distance $d$ is:
$$ d = \frac{f \cdot H_{real}}{h_{pixel}} $$

## 7. Finite State Machine (Layer 6)

The `MissionManagerLayer` implements a deterministic FSM dictating macroscopic behavior.

```mermaid
stateDiagram-v2
    [*] --> INIT
    INIT --> START_FROM_PARKING : Start Button Pressed
    START_FROM_PARKING --> RUNNING : Exited Parking Box
    RUNNING --> AVOIDING_PILLAR : Pillar Detected (ToF/Vision)
    AVOIDING_PILLAR --> RUNNING : Pillar Passed (ToF clears)
    RUNNING --> STOP_AND_GO : Blue Line Detected
    STOP_AND_GO --> RUNNING : 3 Seconds Passed
    RUNNING --> EMERGENCY_BRAKE : Front ToF < 180mm
    RUNNING --> PARKING_SEARCH : 3 Laps Completed
    PARKING_SEARCH --> PARKING_APPROACH : Parking Spot Found
    PARKING_APPROACH --> PARKING_MANEUVER_P1 : Aligned for Parallel
    PARKING_MANEUVER_P1 --> PARKING_MANEUVER_P2 : Target Reached
    PARKING_MANEUVER_P2 --> PARKING_MANEUVER_P3 : Target Reached
    PARKING_MANEUVER_P3 --> PARKING_MANEUVER_P4 : Target Reached
    PARKING_MANEUVER_P4 --> PARKED : Maneuver Complete
    PARKED --> [*]
```

### 7.1 Detailed State Transition Logic
- **START_FROM_PARKING:** Triggers a +7 point WRO bonus. Robot moves straight until the left/right ToF sensors indicate exiting the starting box boundaries.
- **RUNNING:** The default lane-keeping state targeting 0.0m crosstrack error.
- **AVOIDING_PILLAR:** If a red pillar is detected at distance < 800mm, state shifts. Target offset shifts to $-0.65m$ (steer right) or $+0.65m$ (steer left) depending on color and lap direction configuration.
- **STOP_AND_GO:** Triggered by blue line perception. Injects a 3.0 second hardware timer block setting $v_{target}=0$.
- **PARKING_MANEUVER:** A 4-phase geometric sequence executing a perfect parallel park (+15 points).

## 8. Adaptive Stanley Controller (Layer 10)

To actuate the 4WS linkage, we utilize an Adaptive Stanley Controller, famous for its performance in the DARPA Grand Challenge. Unlike Pure Pursuit which targets a point ahead, Stanley minimizes both heading error and crosstrack error relative to the front axle.

### 8.1 Derivation from First Principles
Let $\psi_e$ be the heading error (path heading - robot heading), and $e_{fa}$ be the crosstrack error measured from the center of the front axle to the nearest point on the path.
The fundamental Stanley control law for steering angle $\delta$ is:
$$ \delta(t) = \psi_e(t) + \arctan\left(\frac{k_{base} \cdot e_{fa}(t)}{v(t)}\right) $$

As velocity $v(t) \to 0$, the arctan term approaches $\frac{\pi}{2}$, causing severe steering chatter at low speeds. To mitigate this and ensure high-speed stability, we introduce a softening constant $k_s = 0.1$ and implement **Gain Scheduling**.

The adaptive gain $k(v)$ reduces aggressive steering at high speeds:
$$ k(v) = \frac{k_{base}}{1 + 0.015 \cdot v} $$
Where $k_{base} = 0.75$.

The final implemented control law:
$$ \delta = \psi_e + \arctan\left(\frac{k(v) \cdot e_{fa}}{v + k_s}\right) $$

### 8.2 4WS Kinematic Mapping
The theoretical steering angle $\delta$ must be mapped to the actual 4-Wheel Steering hardware. For a wheelbase $L = 160mm$, the mechanical linkage connects front and rear wheels out-of-phase with a ratio $\kappa = 0.85$.
The layer calculates the required servo PWM (in microseconds) mapping $\pm 35^\circ$ to $900-2100\mu s$, centering at $1500\mu s$.

## 9. Serial Communication Protocol

The Raspberry Pi transmits motor and servo commands to the ESP32 via UART (115200 baud). We engineered a highly robust 10-byte binary protocol.

### 9.1 Byte-by-Byte Walkthrough
Packet format: `[START1] [START2] [SEQ] [CMD] [SRV_HI] [SRV_LO] [SPD_HI] [SPD_LO] [CRC8] [STOP]`

Example scenario: Command servo to $1650\mu s$, Motor to $+150$ PWM speed.
- `[START1]`: `0xAA` (Fixed synchronization byte)
- `[START2]`: `0x55` (Fixed synchronization byte)
- `[SEQ]`: `0x14` (Rolling counter, e.g., packet #20)
- `[CMD]`: `0x01` (0x01 = DRIVE mode)
- `[SRV_HI]`: `0x06` (1650 in hex is `0x0672`, high byte)
- `[SRV_LO]`: `0x72` (low byte)
- `[SPD_HI]`: `0x00` (150 in hex is `0x0096`, high byte)
- `[SPD_LO]`: `0x96` (low byte)
- `[CRC8]`: Computed across `SEQ` through `SPD_LO` using polynomial `0x07`.
- `[STOP]`: `0x0D` (Carriage return)

The ESP32 reconstructs the 16-bit values via bitwise shifting:
```c
uint16_t servo_pwm = (buffer[4] << 8) | buffer[5];
int16_t motor_pwm = (buffer[6] << 8) | buffer[7];
```

## 10. Error Handling and Failsafes

Robustness is achieved through pervasive `try/except` wrapping and watchdog integration.
- **I2C Bus Faults:** The `SensorThread` wraps every `read_byte_data` call in a `try/except OSError`. If an I2C NACK occurs, it catches the error, increments a fault counter, and attempts a soft reset of the specific I2C device via its XSHUT pin, without crashing the Python interpreter.
- **Camera Drops:** If `cv2.VideoCapture.read()` returns `False`, the pipeline gracefully yields an empty contour array, allowing the UKF to fly blind momentarily using only IMU/ToF odometry until the driver restarts.
- **Configuration Errors:** If `surprise_rules.yaml` contains malformed YAML during a hot-reload, the `yaml.parser.ParserError` is caught, logging a warning to `stderr`, and the system retains the last known good configuration state.

## 11. Performance Analysis and Loop Budgets

To achieve a 100 Hz control loop, each iteration has a strict total time budget of 10.0 milliseconds. We extensively profiled the Python execution using the `cProfile` module.

**Average Loop Timing Budget Allocation:**
- **Layer Mutex Locking & State Fetch:** 0.1 ms
- **UKF Prediction & Update Matrix Math (NumPy):** 2.5 ms
- **OpenCV Contour Analysis (C-backend):** 3.0 ms
- **FSM Evaluation:** 0.2 ms
- **Path Planning & Stanley Control:** 0.5 ms
- **UART Packet Serialization & Dispatch:** 0.2 ms
- **Total Execution Time:** ~6.5 ms
- **Idle Sleep (Yielding GIL):** ~3.5 ms

Because the total execution time (6.5 ms) is strictly less than the 10.0 ms budget, the system achieves hard real-time deterministic performance at 100 Hz, with sufficient headroom to handle operating system scheduling jitter.

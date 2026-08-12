# README Additions — Bill of Materials (full) + Challenges & Learnings

> **How to use:** copy Section A into `README.md` (replace the current
> `## 📋 Bill of Materials (Core Components)` table with the full tables below)
> and append Section B as a new `## 🛠️ Challenges & Learnings` section — put it
> after "Quick Start" and before the final footer.
>
> **Data integrity:** every number below was verified against this repository
> (`README.md`, `config/robot_config.json`, `docs/01–07_*.md`,
> `layers/`, `firmware/`, `other/history/`). Nothing was invented.
> Power source: **3S LiPo, 11.1 V, 2200 mAh, 25C**. The IMU is a **MPU6050**
> (gyro + accelerometer only) — **no magnetometer is used**; heading comes from
> gyro integration and the UKF. Prices are estimated street prices (India,
> 2026) and must be treated as estimates, not quotes.

---

# Section A — Full Bill of Materials

## A1. Computation & Sensing

| # | Component | Specification | Power Rail | Data Interface | Qty | Est. Unit Cost (INR) | Est. Unit Cost (USD) |
|---|---|---|---|---|---|---|---|
| 1 | Raspberry Pi 4B | 4 GB RAM, ARM Cortex-A72, 10-layer Python stack @ 100 Hz | Buck A — 5 V / 3 A logic plane | system bus, GPIO + CSI + USB | 1 | ₹5,000 | $60 |
| 2 | microSD Card | Class 10 / A1, 32 GB (OS + logs) | — | SDIO | 1 | ₹350 | $4 |
| 3 | ESP32-S3 DevKit | Dual-core 240 MHz, real-time motor controller | Buck A — 5 V / 3 A (on-board 3.3 V LDO) | USB UART ⇄ Pi (115,200 baud) | 1 | ₹650 | $8 |
| 4 | Pi Camera v2 | Sony IMX219, 8 MP, CSI, 150–250 mA | Pi 3.3 V regulators | CSI-2 (MIPI) | 1 | ₹1,600 | $19 |
| 5 | VL53L1X ToF breakout | Front ranging, 0–4000 mm, 940 nm | 3.3 V | I2C 0x30, XSHUT GPIO 22 | 1 | ₹650 | $8 |
| 6 | VL53L0X ToF breakout | Left side ranging, 0–2000 mm | 3.3 V | I2C 0x31, XSHUT GPIO 17 | 1 | ₹400 | $5 |
| 7 | VL53L0X ToF breakout | Right side ranging, 0–2000 mm | 3.3 V | I2C 0x32, XSHUT GPIO 27 | 1 | ₹400 | $5 |
| 8 | MPU6050 (GY-521) | 6-DoF IMU — gyro + accel only (no magnetometer used) | 3.3 V | I2C 0x68, shared bus | 1 | ₹220 | $3 |

## A2. Drive & Steering (Electromechanical)

| # | Component | Specification | Power Rail | Actuation / Control | Qty | Est. Unit Cost (INR) | Est. Unit Cost (USD) |
|---|---|---|---|---|---|---|---|
| 9 | MG995 servo | 11 kg-cm, metal gear, 50 Hz PWM, 1000–2000 µs, ±35° travel | Buck B — 6 V / 3 A servo plane | PWM GPIO 18 (ESP32) | 1 | ₹350 | $4 |
| 10 | Johnson DC gear motor | 20:1 planetary, 12 V class, ~600 RPM | L298N OUT (direct 11.1 V) | L298N ENA/IN1/IN2 | 1 | ₹550 | $7 |
| 11 | L298N motor driver | Dual H-bridge, 2 A/ch continuous, heatsink | VMS — direct fused 11.1 V | ENA GPIO 19, IN1 GPIO 20, IN2 GPIO 21, STBY GPIO 22 | 1 | ₹320 | $4 |
| 12 | 4WS steering linkage kit | Out-of-phase bellcrank + rods (front/rear axles, κ = 0.85) | mechanical | single MG995 drives all four wheels | 1 | ₹400 | $5 |

## A3. Power Distribution Network

| # | Component | Specification | Rail / Role | Qty | Est. Unit Cost (INR) | Est. Unit Cost (USD) |
|---|---|---|---|---|---|---|
| 13 | 3S LiPo battery | **11.1 V, 2200 mAh, 25C** (front+rear) — replaced the earlier 800 mAh pack whose high internal resistance dipped below 9 V and reset the buck converters | primary energy source | 1 | ₹2,200 | $27 |
| 14 | XT60 connector pair | male/female + 14 AWG pigtails | battery ⇄ fuse | 1 | ₹150 | $2 |
| 15 | 10 A automotive blade fuse | ATO standard + inline holder (+ 2 spare fuses) | primary overcurrent protection | 1 | ₹100 | $1 |
| 16 | Master toggle switch | DC rated ≥ 10 A | fuse → 3-way split | 1 | ₹120 | $1.50 |
| 17 | Buck converter A | LM2596, 5 V / 3 A (logic plane: Pi, ESP32, sensors) | 11.1 V → 5 V | 1 | ₹140 | $2 |
| 18 | Buck converter B | LM2596, 6 V / 3 A (servo plane: MG995 only) | 11.1 V → 6 V | 1 | ₹140 | $2 |
| 19 | Bulk decoupling caps | 470 µF electrolytic (across both buck outputs) | filters actuator noise off logic rails | 2 | ₹40 | $0.50 |
| 20 | Battery monitor divider | 10 kΩ + 2.2 kΩ resistor chain → ESP32 ADC (safe shutdown < 10.5 V) | telemetry / brownout guard | 1 | ₹20 | $0.25 |
| 21 | Star-ground hub | single copper bolt/busbar at battery negative | all grounds converge (no loops) | 1 | ₹60 | $1 |

## A4. Wiring, Housing & Fabrication

| # | Component | Specification | Role | Qty | Est. Unit Cost (INR) | Est. Unit Cost (USD) |
|---|---|---|---|---|---|---|
| 22 | Chassis (printed) | PETG 30% Gyroid, ~0.5 kg filament, T_g 80 °C | vehicle frame | 1 | ₹800 | $10 |
| 23 | Wiring + connectors | 20 AWG silicone wire, dupont jumpers, XH 2.54 headers, heat-shrink | power + signal routing | 1 lot | ₹450 | $6 |
| 24 | Protoboard / perfboard | 5×7 cm, soldered sensor breakout | sensor and divider assembly | 1 | ₹120 | $1.50 |
| 25 | Status LEDs + 220 Ω resistors | 5× (Pi LEDs 1–5: boot, sensors, camera, serial, race) + 5× (ESP32 LEDs) | diagnostics | 10 | ₹80 | $1 |
| 26 | Start button | momentary push switch to GND (GPIO 16) | race start | 1 | ₹40 | $0.50 |
| 27 | Fasteners & standoffs | M2.5/M3 brass standoffs, screws, zip ties, foam tape | assembly | 1 lot | ₹300 | $4 |
| 28 | USB A → micro-USB cable | Pi 4B ⇄ ESP32-S3 UART link | inter-controller link | 1 | ₹150 | $2 |

**Estimated project total: ≈ ₹15,000–17,000 (≈ $190–210)** — approximate market prices, India 2026.

---

# Section B — Challenges & Learnings

## B1. "Split-brain" architecture: variable vision latency vs. deterministic actuation

**The challenge.** One board cannot serve both. The perception pipeline (OpenCV
HSV segmentation of the Pi Camera v2, plus the VL53/MPU6050 I²C reads) has
frame-to-frame variable latency, while steering and throttle must respond at a
deterministic cadence in the ~10 ms regime.

**How we solved it.** A Raspberry Pi 4B runs the 10-layer high-level stack
(perception → UKF → planning → Stanley control) and streams **10-byte CRC8
binary packets @ 115,200 baud** to an ESP32-S3 at **100 Hz** (UART utilization
< 9% — `layer10_controller.py`, `utils/serial_protocol.py`). The ESP32 owns
the real-time actuation: 50 Hz MG995 PWM and L298N motor PWM, plus an
independent **200 ms watchdog** as a second failure layer. The Pi can stall on
a vision frame without ever delaying a steering command; the ESP32 keeps the
last valid packet driving the actuators. This separation also isolates the
Linux/GIL and OpenCV's frame reads from the I²C sensor loop — the VL53L1X's
68 ms ranging cycle is 6.8× slower than the 10 ms control frame and therefore
runs in its own background polling thread with a lock-protected snapshot
(`layer1_sensors.py`).

**What it taught us.** Determinism belongs at the edge, not in the OS. Our
fault-catalog entry FA-2 (a `transmit_command()` that silently swallowed
serial write failures — `issues/`) made the failsafe surface explicit:
`IOError` propagation + Pi-side LED4/LED5 health, so a dead link is seen, not
hallucinated. Cost of the split: one extra board (~₹650) — worth it.

## B2. 4-wheel Ackermann steering: ~126 mm turning radius (−44.9% vs FWS)

**The challenge.** WRO arenas punish wide turns. A standard front-wheel-steer
car needs ~229 mm radius → impossible in tight parking-zone and corner
maneuvers without reversing.

**How we solved it.** One MG995 servo steers **all four wheels through an
out-of-phase bellcrank linkage**: the rear axle mirrors the front at
κ = 0.85 (`delta_r = -0.85 * delta_f`, `layer9_kinematics_4ws.py`),
clamped to ±35° mechanical travel. With both axle midpoints sharing one
instantaneous turning center, the geometry collapses the turning radius to
**~126 mm — 44.9% smaller than the FWS equivalent** — verified against the
physical linkage (see `other/history/v8.0/CHANGE.md`, AC1).

**What it taught us.** The naive "same angle front and rear" split is
kinematically impossible — both axle midpoints cannot share one turning
center without tire scrub (measured: radius error growing from 3% at 10° to
29% at 30° on a rigid Ackermann-violating linkage, `v2.1`). The
counter-steered split keeps the turning center correct. And "turning tightest"
cost a second gear: v8.1's opposite-phase mode (0.5 m diagonal-pivot calls)
caps speed at 0.3 m/s to keep the geometry calm.

## B3. One I²C bus, three devices at address 0x29

**The challenge.** The VL53L1X (front) and both VL53L0X (sides) all default to
**0x29** on a single I²C bus shared with the MPU6050 (0x68) — two powered
sensors at the same address corrupt each other's reads.

**How we solved it.** Each sensor is power-gated by its own **XSHUT line**
(GPIO 22 front, 17 left, 27 right); sequential power-up assigns distinct
addresses (0x30 / 0x31 / 0x32) with only one sensor alive per I²C transaction
(`layer1_sensors.py`, v1.5–v1.9 recoveries). Measurement data:
- **VL53L0X optical bias:** both side units over-reported by 48–53 mm against
  a metal ruler — subtracted `OFFSET_LR_MM = 50.0`; post-fix mean error
  < ±3 mm across 200–600 mm.
- **VL53L1X timing:** 68 ms ranging cycle vs 10 ms control frame — dedicated
  background thread with a lock-protected snapshot instead of a blocking read.

**What it taught us.** Constraint C-5 ("one I²C bus") is a physical, not
software, constraint; the fix is power sequencing at the hardware layer, then
a clean async snapshot so the control loop never blocks on I²C.

## B4. Power integrity: brownouts, servo inrush, and EMI on the serial link

**The challenge.** The MG995 can spike current demand at full steering; the
motor adds inductive inrush. On the first packs this sagged the rail below the
buck converters' dropout and even corrupted the USB UART link (random wild
steering — FA-008 in `docs/06_failure_analysis.md`).

**How we solved it.**
- **Two isolated LM2596 buck planes:** Buck A 5 V/3 A for the logic (Pi,
  ESP32, sensors), Buck B 6 V/3 A exclusively for the MG995 — actuator
  transients cannot crash a microcontroller.
- **Direct 11.1 V** from the fused, switched rail to the L298N (its ~1.5 V
  forward drop is accepted for thermal robustness).
- **One star-ground hub** at the battery negative — no ground loops.
- **470 µF bulk capacitors** across both buck outputs (oscilloscope: logic
  rail held **5.02 V ± 0.05 V** under 0.8 V battery transients).
- **CRC8 (poly 0x07) strict validation** on every 10-byte frame — corrupted
  packets are dropped, never executed.
- **Battery monitoring:** 10 kΩ/2.2 kΩ divider → ESP32 ADC → safe-shutdown
  command below 10.5 V (protects the Pi's SD card from brownout corruption).
- The pack itself is a **3S LiPo 11.1 V / 2200 mAh / 25C** whose ~36 mΩ
  internal resistance keeps sag negligible at the measured 3.85–4.7 A peaks
  (the earlier 800 mAh 3S dipped below 9 V and reset the bucks — swapped out).

**What it taught us.** One power rail for everything is a single point of
failure. Isolation + decoupling + star ground + protocol integrity are four
cheap engineering layers that removed an entire class of intermittent bugs.

## B5. Asynchronous sensor fusion: 100 Hz filter from 20 Hz sensors

**The challenge.** The MPU6050 streams at 100 Hz while the three VL53s actually
arrive at ~15–20 Hz over the I²C bus. Forcing one rate starves the IMU or
invents data.

**How we solved it.** A 6-state UKF `[x, y, θ, v, ω, b_gyro]` that **predicts
every 100 Hz cycle and corrects on measurement arrival** (`layer3_sensor_fusion.py`).
The tempting sample-and-hold shortcut was rejected on principle: re-applying
held VL53 reads as fresh 100 Hz data inflates the effective innovation count,
shrinks the covariance, and makes the filter overconfident — exactly what the
NEES-style audit (ratio 1.03, `v5.5`) would catch.

**What it taught us.** The filter's mathematics is the architecture: P is the
ledger of what you actually know. Rate asymmetry must be embraced (async
predict/correct), never papered over with held values dressed as fresh ones.

---

*All challenge numbers cross-reference the repository — the phase-by-phase
error catalog in `issues/` and the failure analysis in `docs/06_failure_analysis.md`.
No magnetometer is used; no fake or inflated metrics were added.*
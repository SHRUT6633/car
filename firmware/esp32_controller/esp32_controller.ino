/*
 * ======================================================================================
 *                   ESP32-S3 REAL-TIME MOTOR CONTROLLER FIRMWARE
 *          WRO Future Engineers 2026 - Single Servo Mechanical 4WS Robot
 * ======================================================================================
 * Features:
 *  - Non-blocking UART packet receiver @ 115200 baud (USB CDC or Serial1)
 *  - CRC8 (SMBus) Checksum Verification
 *  - 200ms Watchdog Timer with Failsafe Auto-Stop
 *  - Hardware LEDC PWM for MG995 4WS Servo (GPIO 18)
 *  - TB6612FNG / L298N Motor Driver PWM & Direction Control (GPIO 19, 20, 21, 22)
 * ======================================================================================
 */

#include <Arduino.h>
#include <ESP32Servo.h>

// --------------------------------------------------------------------------------------
// PIN DEFINITIONS (ESP32-S3)
// --------------------------------------------------------------------------------------
#define SERVO_PIN         18    // MG995 4WS Steering Servo PWM
#define MOTOR_PWM_PIN     19    // TB6612FNG PWMA / L298N ENA
#define MOTOR_IN1_PIN     20    // TB6612FNG AIN1 / L298N IN1
#define MOTOR_IN2_PIN     21    // TB6612FNG AIN2 / L298N IN2
#define MOTOR_STBY_PIN    22    // TB6612FNG STBY (High = Active)

// --------------------------------------------------------------------------------------
// CONSTANTS & TIMEOUTS
// --------------------------------------------------------------------------------------
#define SERIAL_BAUD       115200
#define TIMEOUT_MS        200    // Failsafe auto-stop timeout
#define PACKET_SIZE       10

const uint8_t HEADER_0 = 0xAA;
const uint8_t HEADER_1 = 0x55;
const uint8_t FOOTER   = 0x0D;

// --------------------------------------------------------------------------------------
// GLOBAL OBJECTS & STATE
// --------------------------------------------------------------------------------------
Servo mg995Servo;
unsigned long lastPacketTime = 0;
uint8_t rxBuffer[PACKET_SIZE];
uint8_t bufferIdx = 0;

// --------------------------------------------------------------------------------------
// CRC8 CHECKSUM (Polynomial 0x07)
// --------------------------------------------------------------------------------------
uint8_t calculateCRC8(const uint8_t *data, size_t len) {
    uint8_t crc = 0x00;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x80) {
                crc = (crc << 1) ^ 0x07;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

// --------------------------------------------------------------------------------------
// HARDWARE ACTUATOR CONTROL
// --------------------------------------------------------------------------------------
void setServoAngle(float angleDeg) {
    // Map -35.0 to +35.0 deg to servo pulse width 1000us to 2000us (1500us Center)
    int pulseUs = map((long)(angleDeg * 10), -350, 350, 1000, 2000);
    pulseUs = constrain(pulseUs, 1000, 2000);
    mg995Servo.writeMicroseconds(pulseUs);
}

void setMotorSpeed(float speedPct) {
    // Clamp speed -100.0 to +100.0 %
    speedPct = constrain(speedPct, -100.0f, 100.0f);
    int pwmVal = map((long)abs(speedPct), 0, 100, 0, 255);

    digitalWrite(MOTOR_STBY_PIN, HIGH);

    if (speedPct > 0.5f) {
        // Forward
        digitalWrite(MOTOR_IN1_PIN, HIGH);
        digitalWrite(MOTOR_IN2_PIN, LOW);
    } else if (speedPct < -0.5f) {
        // Reverse
        digitalWrite(MOTOR_IN1_PIN, LOW);
        digitalWrite(MOTOR_IN2_PIN, HIGH);
    } else {
        // Coast / Stop
        digitalWrite(MOTOR_IN1_PIN, LOW);
        digitalWrite(MOTOR_IN2_PIN, LOW);
        pwmVal = 0;
    }

    analogWrite(MOTOR_PWM_PIN, pwmVal);
}

void executeFailsafe() {
    // Stop Motor & Center Steering
    setMotorSpeed(0.0f);
    setServoAngle(0.0f);
    digitalWrite(MOTOR_STBY_PIN, LOW);
}

// --------------------------------------------------------------------------------------
// PACKET PROCESSING
// --------------------------------------------------------------------------------------
void processPacket(const uint8_t *pkt) {
    // Format: [0xAA, 0x55, SEQ, CMD, SERVO_H, SERVO_L, SPEED_H, SPEED_L, CRC8, 0x0D]
    uint8_t calculatedCRC = calculateCRC8(pkt, 8);
    if (calculatedCRC != pkt[8]) {
        return; // CRC mismatch - discard
    }

    int16_t rawServo = (int16_t)((pkt[4] << 8) | pkt[5]);
    int16_t rawSpeed = (int16_t)((pkt[6] << 8) | pkt[7]);

    float servoAngleDeg = rawServo / 100.0f;
    float motorSpeedPct = rawSpeed / 10.0f;

    setServoAngle(servoAngleDeg);
    setMotorSpeed(motorSpeedPct);

    lastPacketTime = millis();
}

// --------------------------------------------------------------------------------------
// SETUP & MAIN LOOP
// --------------------------------------------------------------------------------------
void setup() {
    Serial.begin(SERIAL_BAUD);

    // Motor driver pin setup
    pinMode(MOTOR_PWM_PIN, OUTPUT);
    pinMode(MOTOR_IN1_PIN, OUTPUT);
    pinMode(MOTOR_IN2_PIN, OUTPUT);
    pinMode(MOTOR_STBY_PIN, OUTPUT);
    digitalWrite(MOTOR_STBY_PIN, LOW);

    // Servo pin setup
    ESP32PWM::allocateTimer(0);
    mg995Servo.setPeriodHertz(50); // Standard 50Hz Servo
    mg995Servo.attach(SERVO_PIN, 1000, 2000);

    executeFailsafe();
    lastPacketTime = millis();
}

void loop() {
    // 1. Non-blocking Serial Packet Ingestion
    while (Serial.available() > 0) {
        uint8_t byteIn = Serial.read();

        if (bufferIdx == 0) {
            if (byteIn == HEADER_0) rxBuffer[bufferIdx++] = byteIn;
        } else if (bufferIdx == 1) {
            if (byteIn == HEADER_1) rxBuffer[bufferIdx++] = byteIn;
            else bufferIdx = 0;
        } else {
            rxBuffer[bufferIdx++] = byteIn;
            if (bufferIdx == PACKET_SIZE) {
                if (rxBuffer[PACKET_SIZE - 1] == FOOTER) {
                    processPacket(rxBuffer);
                }
                bufferIdx = 0; // Reset buffer
            }
        }
    }

    // 2. Communication Watchdog Timer Check
    if (millis() - lastPacketTime > TIMEOUT_MS) {
        executeFailsafe();
    }
}

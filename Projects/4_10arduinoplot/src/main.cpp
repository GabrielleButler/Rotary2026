#include <Arduino.h>
#include <Arduino_BMI270_BMM150.h>
#include <ArduinoBLE.h>
#include <Servo.h>

// ---------------- BLE ----------------
BLEService imuService("12345678-1234-1234-1234-1234567890ab");

BLEFloatCharacteristic zChar(
    "12345678-1234-1234-1234-1234567890ac",
    BLERead | BLENotify
);

// Command characteristic, written by the laptop
//   1 = start 8.5s timer, then move servo to 120 deg
//   0 = reset: cancel timer, return servo to 0 deg, re-arm
BLEByteCharacteristic cmdChar(
    "12345678-1234-1234-1234-1234567890ad",
    BLEWrite
);

// ---------------- Servo ----------------
Servo myServo;
const int SERVO_PIN     = 9;       // signal wire on D9
const int REST_ANGLE    = 0;
const int TARGET_ANGLE  = 120;
const unsigned long DELAY_MS = 8500;

bool          timerActive    = false;
bool          servoTriggered = false;
unsigned long timerStart     = 0;

void setup() {
    Serial.begin(115200);
    delay(2000);                        // give USB-Serial time to enumerate on Mac
    Serial.println("=== Boot ===");

    Serial.println("Attaching servo...");
    myServo.attach(SERVO_PIN);
    myServo.write(REST_ANGLE);
    Serial.println("Servo OK");

    Serial.println("Starting IMU...");
    if (!IMU.begin()) {
        Serial.println("Failed to initialize IMU!");
        while (1) { delay(1000); Serial.println("(stuck on IMU)"); }
    }
    Serial.println("IMU OK");

    Serial.println("Starting BLE...");
    if (!BLE.begin()) {
        Serial.println("Failed to initialize BLE!");
        while (1) { delay(1000); Serial.println("(stuck on BLE)"); }
    }
    Serial.println("BLE OK");

    BLE.setLocalName("Nano33BLE_Z");
    BLE.setAdvertisedService(imuService);
    imuService.addCharacteristic(zChar);
    imuService.addCharacteristic(cmdChar);
    BLE.addService(imuService);

    zChar.writeValue(0.0);
    cmdChar.writeValue(0);

    BLE.advertise();
    Serial.println("BLE device is now advertising...");
}

void loop() {
    // Wait for BLE central connection
    BLEDevice central = BLE.central();
    if (central) {
        Serial.print("Connected to central: ");
        Serial.println(central.address());

        // Reset state on a fresh connection
        timerActive    = false;
        servoTriggered = false;
        myServo.write(REST_ANGLE);

        while (central.connected()) {
            float x, y, z;

            // ---------------- READ IMU ----------------
            if (IMU.accelerationAvailable()) {
                IMU.readAcceleration(x, y, z);

                // Send Z acceleration over BLE
                if (zChar.subscribed()) {
                    zChar.writeValue(z);
                }

                // Optional serial debug
                Serial.println(z);
            }

            // ---------------- HANDLE COMMAND ----------------
            if (cmdChar.written()) {
                byte cmd = cmdChar.value();
                Serial.print("Command received: ");
                Serial.println(cmd);

                if (cmd == 1 && !timerActive && !servoTriggered) {
                    timerActive = true;
                    timerStart  = millis();
                    Serial.println("Timer started: 8.5s countdown");
                }
                else if (cmd == 0) {
                    // Reset: cancel timer, return servo to rest, re-arm
                    timerActive    = false;
                    servoTriggered = false;
                    myServo.write(REST_ANGLE);
                    Serial.println("Reset: servo back to 0 deg, ready to fire again");
                }
            }

            // ---------------- NON-BLOCKING TIMER ----------------
            if (timerActive && !servoTriggered) {
                if (millis() - timerStart >= DELAY_MS) {
                    myServo.write(TARGET_ANGLE);
                    servoTriggered = true;
                    timerActive    = false;
                    Serial.println("Servo moved to 120 deg");
                }
            }

            // Small delay for stable BLE streaming
            delay(20);
        }

        Serial.println("Central disconnected");
    }
}
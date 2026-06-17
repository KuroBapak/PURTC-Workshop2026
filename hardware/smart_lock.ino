/*
 * Edge AI Smart Lock — ESP32 Arduino Sketch
 * Workshop Edition
 * 
 * Receives serial commands from the Python backend:
 *   "OPEN"  → Unlock (Green LED, 2 beeps, servo 90°, hold 5s, re-lock)
 *   "CLOSE" → Lock   (Red LED, 1 long beep, servo stays 0°)
 * 
 * Baud Rate: 115200
 * 
 * === PIN CONFIGURATION ===
 * Adjust these pin numbers to match your wiring.
 */

#include <ESP32Servo.h>

// ==================== PIN DEFINITIONS ====================
#define SERVO_PIN     13    // Servo signal wire (orange)
#define GREEN_LED_PIN 27    // Green LED anode (with resistor)
#define RED_LED_PIN   26    // Red LED anode (with resistor)
#define BUZZER_PIN    25    // Active buzzer positive pin

// ==================== CONSTANTS ==========================
#define BAUD_RATE     115200
#define UNLOCK_ANGLE  90    // Servo angle for unlocked position
#define LOCK_ANGLE    0     // Servo angle for locked position
#define HOLD_TIME     5000  // Time to hold unlock (5 seconds)

// ==================== OBJECTS ============================
Servo lockServo;
String command = "";

// ==================== SETUP ==============================
void setup() {
    Serial.begin(BAUD_RATE);
    
    // Initialize pins
    pinMode(GREEN_LED_PIN, OUTPUT);
    pinMode(RED_LED_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    
    // Attach servo
    lockServo.attach(SERVO_PIN);
    
    // Initial state: LOCKED
    lockServo.write(LOCK_ANGLE);
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    
    Serial.println("Smart Lock Ready — Waiting for commands...");
}

// ==================== MAIN LOOP ==========================
void loop() {
    if (Serial.available() > 0) {
        command = Serial.readStringUntil('\n');
        command.trim();
        
        if (command == "OPEN") {
            handleOpen();
        } 
        else if (command == "CLOSE") {
            handleClose();
        }
    }
}

// ==================== COMMAND HANDLERS ===================

void handleOpen() {
    Serial.println(">> ACCESS GRANTED — Unlocking...");
    
    // 1. Green LED ON, Red LED OFF
    digitalWrite(GREEN_LED_PIN, HIGH);
    digitalWrite(RED_LED_PIN, LOW);
    
    // 2. Buzzer: 2 short rapid beeps
    shortBeep();
    delay(100);
    shortBeep();
    
    // 3. Servo → 90° (Unlock)
    lockServo.write(UNLOCK_ANGLE);
    
    // 4. Hold for 5 seconds
    delay(HOLD_TIME);
    
    // 5. Re-lock automatically
    lockServo.write(LOCK_ANGLE);
    
    // 6. Reset LEDs back to locked state
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(RED_LED_PIN, HIGH);
    
    Serial.println(">> Auto re-locked.");
}

void handleClose() {
    Serial.println(">> ACCESS DENIED — Locked.");
    
    // 1. Red LED ON, Green LED OFF
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, LOW);
    
    // 2. Buzzer: 1 long continuous beep
    longBeep();
    
    // 3. Servo stays at 0° (Locked)
    lockServo.write(LOCK_ANGLE);
}

// ==================== BUZZER HELPERS =====================

void shortBeep() {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
}

void longBeep() {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(500);
    digitalWrite(BUZZER_PIN, LOW);
}

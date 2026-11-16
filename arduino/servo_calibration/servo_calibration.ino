// Manual servo calibration from the Serial Monitor (9600 baud, New Line).
//   "1 90"  -> move servo 1 to 90 degrees (servos 1-4)
//   "+"/"-" -> move the last servo by 2 degrees
//   "off"   -> release all servos
// Use it to find each servo's open and closed angle.

#include <Servo.h>

const int PINS[4] = {4, 5, 12, 11};
const char* NAMES[4] = {"Thumb", "Index", "Middle", "Ring+Pinky"};      // same order as hand_servos.ino and the Python code
Servo servos[4];
int angles[4] = {0, 0, 0, 0};
int selected = -1;                                                      // -1 = no servo chosen yet

void moveServo(int i, int angle) {
  angle = constrain(angle, 0, 180);
  if (!servos[i].attached()) {
    servos[i].attach(PINS[i], 500, 2500);
  }
  servos[i].write(angle);
  angles[i] = angle;
  selected = i;
  Serial.print(NAMES[i]);
  Serial.print(" -> ");
  Serial.println(angle);
}

void setup() {
  Serial.begin(9600);
  delay(2000);
  Serial.println("Servo calibration");
  Serial.println("  1 90  -> move servo 1 to 90 degrees");
  Serial.println("  + / - -> move the last servo by 2 degrees");
  Serial.println("  off   -> release all servos");
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "off") {
      for (int i = 0; i < 4; i++) {
        servos[i].detach();
      }
      Serial.println("All servos released");
    } else if (cmd == "+" || cmd == "-") {
      if (selected < 0) {
        Serial.println("First choose a servo, e.g. 1 90");
      } else if (cmd == "+") {
        moveServo(selected, angles[selected] + 2);
      } else {
        moveServo(selected, angles[selected] - 2);
      }
    } else {
      int space = cmd.indexOf(' ');
      if (space > 0) {
        int number = cmd.substring(0, space).toInt();
        int angle = cmd.substring(space + 1).toInt();
        if (number >= 1 && number <= 4) {
          moveServo(number - 1, angle);
        } else {
          Serial.println("Servo number must be 1-4");
        }
      } else {
        Serial.println("Unknown command");
      }
    }
  }
}
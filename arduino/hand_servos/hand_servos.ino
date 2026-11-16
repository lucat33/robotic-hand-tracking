// Receives four servo angles from Python, one line at a time:
//   "thumb,index,middle,ring_pinky\n"
// Broken lines are ignored. 
//The board never replies, so the USB serial buffer cannot fill up while streaming.

#include <Servo.h>

const int PINS[4] = {4, 5, 12, 11};   // Thumb, Index, Middle, Ring+Pinky
Servo servos[4];

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    servos[i].attach(PINS[i], 500, 2500);     // 500–2500 µs: full 0–180° range for these servos
    servos[i].write(0);                       // start with the hand open
  }
}

void loop() {
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');

    int c1 = line.indexOf(',');
    int c2 = line.indexOf(',', c1 + 1);
    int c3 = line.indexOf(',', c2 + 1);       // find the positions of the three commas

    if (c1 > 0 && c2 > c1 && c3 > c2) {
      int angles[4];
      angles[0] = line.substring(0, c1).toInt();
      angles[1] = line.substring(c1 + 1, c2).toInt();
      angles[2] = line.substring(c2 + 1, c3).toInt();
      angles[3] = line.substring(c3 + 1).toInt();

      // clamp every angle to the servo range before moving
      for (int i = 0; i < 4; i++) {
        servos[i].write(constrain(angles[i], 0, 180));
      }
    }
  }
}
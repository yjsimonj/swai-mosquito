/*
 * 모기 신고 시스템 — Arduino Uno 서보 노드
 * ------------------------------------------------------------------
 * 역할: ESP-01에서 신호 핀이 HIGH가 되면, 서보모터로 모기약 버튼을
 *       눌렀다(분사) 떼는 동작 수행.
 *
 * 배선:
 *   ESP-01 GPIO2 ── Uno D2   (신호선, ESP가 HIGH/LOW 출력)
 *   ESP-01 GND   ── Uno GND  (★ 공통 GND 필수)
 *   서보 신호선   ── Uno D9
 *   서보 +(빨강)  ── 외부 5V (서보 전류가 커서 별도 5V 권장)
 *   서보 -(갈색)  ── 외부 5V GND ── Uno GND (공통)
 * ------------------------------------------------------------------
 */

#include <Servo.h>

const uint8_t SIGNAL_PIN = 2;    // ESP-01 GPIO2에서 들어오는 신호
const uint8_t SERVO_PIN  = 9;    // 서보 신호선

const int ANGLE_RELEASED = 0;    // 버튼 안 누른 상태
const int ANGLE_PRESSED  = 80;   // 버튼 누른 상태 (분사기에 맞게 조정)
const unsigned long SPRAY_HOLD_MS = 2000;  // 분사 유지 시간(ms)

Servo sprayServo;

void spray() {
  Serial.println("[SERVO] 분사 시작");
  sprayServo.write(ANGLE_PRESSED);
  delay(SPRAY_HOLD_MS);
  sprayServo.write(ANGLE_RELEASED);
  Serial.println("[SERVO] 분사 종료");
}

void setup() {
  Serial.begin(9600);
  pinMode(SIGNAL_PIN, INPUT);     // ESP가 HIGH/LOW로 구동하므로 INPUT
  sprayServo.attach(SERVO_PIN);
  sprayServo.write(ANGLE_RELEASED);
  Serial.println("Uno 서보 노드 준비 완료");
}

void loop() {
  if (digitalRead(SIGNAL_PIN) == HIGH) {
    spray();
    // 신호가 LOW로 떨어질 때까지 대기 (한 번의 펄스 = 한 번 분사)
    while (digitalRead(SIGNAL_PIN) == HIGH) {
      delay(10);
    }
  }
  delay(10);
}

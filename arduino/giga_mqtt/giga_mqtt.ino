/*
 * 모기 신고 시스템 — GIGA R1 WiFi + LED (MQTT 버전)
 * ------------------------------------------------------------------
 * 동작: WiFi 접속 → MQTT 공개 브로커(HiveMQ)에 평문(1883)으로 접속 →
 *       내 구역 토픽 구독 → 서버가 "1" 발행하면 LED 켜기, "0"이면 끄기.
 *       (인증서 불필요 — 평문 MQTT라 GIGA에서 바로 됨)
 *
 * 테스트: 웹사이트에서 해당 구역 신고 → 거의 즉시 LED 켜짐. 종료하면 꺼짐.
 *
 * 필요 라이브러리 (Library Manager에서 설치):
 *   - "ArduinoMqttClient" by Arduino
 * 보드: Arduino GIGA R1 WiFi  (★ 안테나 연결 필수)
 *
 * LED 배선: LED 긴 다리(+) ── D7,  짧은 다리(-) ── 220Ω ── GND
 * ------------------------------------------------------------------
 */

#include <WiFi.h>
#include <ArduinoMqttClient.h>

// ====== 사용자 설정 ======================================================
char ssid[] = "일반물리실험실_2.4";
char pass[] = "2022eowjsrhkgkrrhek@";

const char* BROKER = "broker.hivemq.com";   // 무료 공개 브로커
const int   BROKER_PORT = 1883;             // 평문 (TLS 아님)

// 서버(main.py)의 MQTT_PREFIX 와 반드시 동일해야 함
const char* PREFIX = "swaimosquito/43th36";
const char* ZONE   = "ilsin_2f_class_1_3";  // 감시할 구역

const int LED_PIN = 7;
// =========================================================================

WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

String topic;  // PREFIX/zone/ZONE

void onMqttMessage(int messageSize) {
  String payload = "";
  while (mqttClient.available()) payload += (char)mqttClient.read();
  payload.trim();

  bool on = (payload == "1");
  digitalWrite(LED_PIN, on ? HIGH : LOW);
  Serial.print("[MSG] ");
  Serial.print(payload);
  Serial.println(on ? "  → LED ON" : "  → LED OFF");
}

void connectWiFi() {
  Serial.print("WiFi 연결 중");
  while (WiFi.status() != WL_CONNECTED) {
    WiFi.begin(ssid, pass);
    delay(3000);
    Serial.print(".");
  }
  Serial.print(" 완료! IP: ");
  Serial.println(WiFi.localIP());
}

void connectBroker() {
  Serial.print("MQTT 브로커 연결 중...");
  while (!mqttClient.connect(BROKER, BROKER_PORT)) {
    Serial.print(" 실패(");
    Serial.print(mqttClient.connectError());
    Serial.println(") 재시도");
    delay(2000);
  }
  Serial.println(" 완료!");
  mqttClient.subscribe(topic);          // retain된 현재 상태 즉시 수신됨
  Serial.print("구독: ");
  Serial.println(topic);
}

void setup() {
  Serial.begin(115200);
  unsigned long s = millis();
  while (!Serial && millis() - s < 3000) {}

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  topic = String(PREFIX) + "/zone/" + ZONE;

  connectWiFi();
  mqttClient.onMessage(onMqttMessage);
  connectBroker();
}

void loop() {
  // 연결 유지 + 메시지 수신
  if (!mqttClient.connected()) {
    if (WiFi.status() != WL_CONNECTED) connectWiFi();
    connectBroker();
  }
  mqttClient.poll();
}

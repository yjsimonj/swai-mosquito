/*
 * 모기 신고 시스템 — ESP-01(ESP8266) WiFi 노드
 * ------------------------------------------------------------------
 * 역할: 학교 WiFi 접속 → HF 서버의 WebSocket(/ws/device/<zone>) 접속 →
 *       내 구역이 "1"(신고됨)로 바뀌면 Uno에 분사 신호(HIGH 펄스) 전송.
 *
 * 통신: 서버가 접속 즉시 "1"/"0" 1회 전송, 이후 상태 바뀔 때마다 전송(푸시).
 *       0 -> 1 로 바뀌는 순간에만 분사 (계속 분사 방지 + 쿨다운).
 *
 * 필요 라이브러리 (Arduino IDE 라이브러리 매니저):
 *   - "WebSockets" by Markus Sattler (links2004/arduinoWebSockets)
 *   - ESP8266 보드 패키지 (Boards Manager)
 *
 * 보드 선택: Tools > Board > "Generic ESP8266 Module"
 * ------------------------------------------------------------------
 */

#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>

// ====== 사용자 설정 ======================================================
const char* WIFI_SSID = "학교_와이파이_이름";
const char* WIFI_PASS = "와이파이_비밀번호";

// HF Space 호스트 (https:// 와 / 는 빼고 도메인만)
const char* WS_HOST = "43th36-swai-mosquito.hf.space";
const uint16_t WS_PORT = 443;          // HTTPS/WSS

// 이 기기가 담당하는 구역 ID (지도 코드의 zone_id 와 동일하게)
const char* MY_ZONE = "ilsin_2f_class_1_3";

// Uno로 보내는 신호 핀 (ESP-01의 GPIO2)
const uint8_t SIGNAL_PIN = 2;

// 분사 쿨다운(ms): 재접속/깜빡임으로 인한 연속 분사 방지
const unsigned long SPRAY_COOLDOWN = 30000;  // 30초
// =========================================================================

WebSocketsClient webSocket;
int lastState = -1;              // -1=미초기화, 0=정상, 1=신고
unsigned long lastSprayMs = 0;

void pulseUno() {
  // Uno에 ~600ms HIGH 펄스 → Uno가 서보로 분사
  digitalWrite(SIGNAL_PIN, HIGH);
  delay(600);
  digitalWrite(SIGNAL_PIN, LOW);
  Serial.println("[SPRAY] Uno에 분사 신호 전송");
}

void maybeSpray() {
  unsigned long now = millis();
  if (now - lastSprayMs < SPRAY_COOLDOWN) {
    Serial.println("[SKIP] 쿨다운 중 — 분사 생략");
    return;
  }
  lastSprayMs = now;
  pulseUno();
}

void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("[WS] 서버 연결됨");
      break;
    case WStype_DISCONNECTED:
      Serial.println("[WS] 연결 끊김 (자동 재접속 대기)");
      break;
    case WStype_TEXT: {
      int s = (length > 0 && payload[0] == '1') ? 1 : 0;
      Serial.printf("[WS] 상태 수신: %d\n", s);
      // 0->1 전환(또는 접속 시 이미 1)일 때 분사
      if (s == 1 && lastState != 1) {
        maybeSpray();
      }
      lastState = s;
      break;
    }
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(SIGNAL_PIN, OUTPUT);
  digitalWrite(SIGNAL_PIN, LOW);

  Serial.printf("\n구역: %s\n", MY_ZONE);
  Serial.print("WiFi 연결 중");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" 완료");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  // WSS(보안 WebSocket)로 접속. 인증서 검증은 생략(insecure).
  String path = String("/ws/device/") + MY_ZONE;
  webSocket.beginSSL(WS_HOST, WS_PORT, path.c_str());
  webSocket.onEvent(onWsEvent);
  webSocket.setReconnectInterval(5000);       // 끊기면 5초마다 재접속
  webSocket.enableHeartbeat(15000, 3000, 2);  // 연결 유지(ping)
}

void loop() {
  webSocket.loop();
}

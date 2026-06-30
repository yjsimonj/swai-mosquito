# 아두이노 연동 가이드 (WebSocket 푸시)

ESP-01(WiFi 담당) + Arduino Uno(서보 담당) 구성.
서버가 신고를 받으면 WebSocket으로 해당 구역 ESP-01에 즉시 "1"을 푸시 →
ESP-01이 Uno에 신호 → Uno가 서보로 모기약 버튼을 누름.

```
[서버(HF)] --WSS 푸시("1")--> [ESP-01] --HIGH 펄스--> [Uno] --각도--> [서보] --누름--> 모기약
```

---

## 1. 준비물

| 부품 | 비고 |
|------|------|
| Arduino Uno | 서보 구동 |
| ESP-01 (ESP8266) | WiFi. 가능하면 ESP-01**S**(1MB)가 TLS에 안정적 |
| USB-TTL 어댑터 (3.3V) | ESP-01에 코드 굽기용 (CP2102/FT232 등) |
| SG90/MG90 서보모터 | 버튼 누르기 |
| 외부 5V 전원 | 서보용 (어댑터 또는 배터리) |
| 3.3V 전원 | ESP-01용 (★ Uno의 3.3V 핀은 전류 부족 → 브라운아웃 주의) |
| 점퍼선 | — |

> ⚠️ **ESP-01 전원 주의**: ESP-01은 WiFi 송신 시 순간 ~300mA를 먹습니다.
> Uno의 3.3V 핀(최대 ~50mA)으로는 부족해 리셋이 반복될 수 있어요.
> **별도 3.3V 레귤레이터(AMS1117 모듈 등)** 사용을 권장합니다.

---

## 2. ESP-01에 코드 굽기

ESP-01은 ESP8266 칩이라 아두이노 코드를 직접 구울 수 있습니다.

### (1) Arduino IDE에 ESP8266 보드 추가
1. File > Preferences > "Additional Boards Manager URLs"에 추가:
   ```
   http://arduino.esp8266.com/stable/package_esp8266com_index.json
   ```
2. Tools > Board > Boards Manager > "esp8266" 검색 > 설치

### (2) 라이브러리 설치
- Sketch > Include Library > Manage Libraries
- **"WebSockets" by Markus Sattler** 검색 > 설치

### (3) 굽기용 배선 (USB-TTL ↔ ESP-01)
| ESP-01 핀 | 연결 |
|-----------|------|
| VCC | 3.3V |
| GND | GND |
| CH_PD (EN) | 3.3V |
| GPIO0 | **GND** (굽는 동안만! 플래시 모드 진입) |
| TXD | USB-TTL RXD |
| RXD | USB-TTL TXD |

> GPIO0를 GND에 연결한 상태로 전원 인가 → 플래시 모드.

### (4) IDE 설정 & 업로드
- Tools > Board: **Generic ESP8266 Module**
- Flash Size: 1M, Upload Speed: 115200
- `esp01_wifi/esp01_wifi.ino` 열기
- 상단 설정값 수정:
  - `WIFI_SSID`, `WIFI_PASS` — 학교 WiFi
  - `MY_ZONE` — 이 기기 담당 구역 (예: `ilsin_2f_class_1_3`)
  - `WS_HOST` — 이미 `43th36-swai-mosquito.hf.space` 로 설정됨
- 업로드(→)

### (5) 실행 모드로 전환
- **GPIO0 - GND 연결 제거** → 전원 재인가(리셋)
- Serial Monitor(115200)에서 "WiFi 완료", "[WS] 서버 연결됨" 확인

---

## 3. Uno에 코드 굽기
- `uno_servo/uno_servo.ino` 열기 → Uno 선택 → 업로드
- `ANGLE_PRESSED`(누르는 각도), `SPRAY_HOLD_MS`(분사 시간)는 실제 분사기에 맞게 조정

---

## 4. 운영 배선 (굽기 끝난 뒤)

| 연결 | 핀 |
|------|----|
| ESP-01 GPIO2 → Uno D2 | 신호선 |
| ESP-01 GND ↔ Uno GND | ★ 공통 GND 필수 |
| ESP-01 VCC, CH_PD → 3.3V | 별도 3.3V 전원 |
| 서보 신호선 → Uno D9 | — |
| 서보 +5V → 외부 5V | — |
| 서보 GND → 외부 5V GND ↔ Uno GND | 공통 |

> ESP-01의 GPIO2는 3.3V HIGH를 출력하고, Uno는 이를 HIGH로 인식합니다(임계 ~3V).
> 신호 방향이 ESP→Uno 한쪽뿐이라 레벨 변환은 없어도 됩니다.

---

## 5. 동작 테스트 (하드웨어 없이 먼저)

브라우저에서 아래 주소를 열면 해당 구역 상태(1/0)를 바로 확인할 수 있습니다:
```
https://43th36-swai-mosquito.hf.space/api/zone/ilsin_2f_class_1_3
```
지도에서 그 구역을 신고하면 `0` → `1` 로 바뀝니다.

ESP-01 연결 후, 지도에서 신고하면 Serial Monitor에 `[WS] 상태 수신: 1` →
`[SPRAY] Uno에 분사 신호 전송` 이 떠야 정상입니다.

---

## 6. 동작 로직 요약

- 서버는 접속 즉시 현재 상태("1"/"0")를 보내고, 이후 바뀔 때마다 푸시.
- ESP-01은 **0→1 전환 순간에만** 분사 (계속 분사 방지).
- **쿨다운 30초**: 재접속/깜빡임으로 인한 중복 분사 방지 (`SPRAY_COOLDOWN`).
- 상황 종료(또는 30분 타임아웃)되면 "0" 수신 → 다음 신고 때 다시 분사 가능.

## 7. ⚠️ 안전
사람이 있는 공간에서 살충제 자동분사는 위험할 수 있습니다.
시연은 **LED/부저로 대체**하고, 실제 분사는 사람이 최종 확인하는 방식을 권장합니다.

## 트러블슈팅
- **계속 리셋/연결 실패**: ESP-01 전원 부족 → 별도 3.3V 전원 사용.
- **WSS 연결 안 됨**: "WebSockets" 라이브러리를 최신으로 업데이트(빈 fingerprint = insecure 처리).
  그래도 안 되면 ESP-01S(1MB) 사용 또는 서버를 로컬(ws://)로 띄워 테스트.
- **서보 떨림/Uno 리셋**: 서보를 Uno 5V가 아닌 외부 5V로 구동.

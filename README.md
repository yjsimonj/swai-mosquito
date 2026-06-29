---
title: 모기 신고 시스템
emoji: 🦟
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# 🦟 모기 신고 시스템 (Mosquito Report System)

대전과학고등학교 교내 모기 신고/현황 공유 웹앱.
사용자가 지도에서 자기 구역을 클릭해 모기를 신고하면, 모든 접속자의 지도에 실시간으로 표시됩니다.
상황 종료 버튼을 누르거나 30분이 지나면 자동으로 해제됩니다.

## 기능

- 3개 건물(일신관 1·2F, 다산관 1F, 탐의관 1F) 도면 기반 구역 지도
- 구역 클릭 → 모기 신고 / 상황 종료
- WebSocket 실시간 동기화
- 30분 자동 만료
- SQLite 저장

## 기술 스택

- **백엔드**: FastAPI + WebSocket
- **프론트**: 단일 HTML (Leaflet 불필요, SVG 직접 렌더)
- **DB**: SQLite
- **배포**: Docker (Hugging Face Spaces)

## 로컬 실행

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7860
# http://localhost:7860
```

## API (아두이노 연동용)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/report` | 모기 신고 `{zone_id, building, floor, zone_name}` |
| POST | `/api/resolve/{zone_id}` | 상황 종료 |
| GET | `/api/reports` | 활성 신고 목록 |
| WS | `/ws` | 실시간 업데이트 |

## 데이터 영속성 참고

기본 DB 경로는 컨테이너 내부(`mosquito.db`)로, HF Space 무료 플랜에서는
재시작 시 초기화됩니다. 영구 저장이 필요하면 HF Persistent Storage를 활성화하고
환경변수 `DB_PATH=/data/mosquito.db` 를 설정하세요.

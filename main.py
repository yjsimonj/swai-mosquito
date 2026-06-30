import os
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

DB_PATH = os.environ.get("DB_PATH", "mosquito.db")
TIMEOUT_MINUTES = 30


class ConnectionManager:
    """브라우저(지도)와 기기(아두이노) 연결을 함께 관리.

    - 브라우저: 전체 신고 목록 JSON 수신
    - 기기:     자기 구역 상태만 "1"/"0" 로 수신 (JSON 파싱 불필요)
    """

    def __init__(self):
        self.browsers: List[WebSocket] = []
        self.devices: List[Dict] = []  # [{"ws": WebSocket, "zone_id": str}]

    async def connect_browser(self, ws: WebSocket):
        await ws.accept()
        self.browsers.append(ws)

    async def connect_device(self, ws: WebSocket, zone_id: str):
        await ws.accept()
        self.devices.append({"ws": ws, "zone_id": zone_id})

    def disconnect(self, ws: WebSocket):
        if ws in self.browsers:
            self.browsers.remove(ws)
        self.devices = [d for d in self.devices if d["ws"] is not ws]

    async def broadcast(self):
        """현재 활성 신고 기준으로 브라우저+기기 모두에게 전송."""
        reports = get_active_reports()
        active_zones = {r["zone_id"] for r in reports}

        # 브라우저 → 전체 목록
        msg = json.dumps({"type": "update", "reports": reports}, ensure_ascii=False)
        for ws in list(self.browsers):
            try:
                await ws.send_text(msg)
            except Exception:
                self.disconnect(ws)

        # 기기 → 자기 구역 상태("1"/"0")
        for d in list(self.devices):
            try:
                await d["ws"].send_text("1" if d["zone_id"] in active_zones else "0")
            except Exception:
                self.disconnect(d["ws"])


manager = ConnectionManager()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id TEXT NOT NULL,
            building TEXT NOT NULL,
            floor TEXT NOT NULL,
            zone_name TEXT NOT NULL,
            reported_at TEXT NOT NULL,
            resolved_at TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    conn.commit()
    conn.close()


def get_active_reports():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reports WHERE status='active' ORDER BY reported_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_zone_active(zone_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM reports WHERE zone_id=? AND status='active' LIMIT 1",
        (zone_id,),
    ).fetchone()
    conn.close()
    return row is not None


async def timeout_loop():
    while True:
        await asyncio.sleep(60)
        conn = sqlite3.connect(DB_PATH)
        cutoff = (datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES)).isoformat()
        conn.execute(
            "UPDATE reports SET status='timeout', resolved_at=? "
            "WHERE status='active' AND reported_at < ?",
            (datetime.utcnow().isoformat(), cutoff),
        )
        conn.commit()
        conn.close()
        await manager.broadcast()


@app.on_event("startup")
async def startup():
    init_db()
    asyncio.create_task(timeout_loop())


class ReportRequest(BaseModel):
    zone_id: str
    building: str
    floor: str
    zone_name: str


@app.post("/api/report")
async def report(req: ReportRequest):
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT id FROM reports WHERE zone_id=? AND status='active'", (req.zone_id,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO reports (zone_id, building, floor, zone_name, reported_at) "
            "VALUES (?,?,?,?,?)",
            (req.zone_id, req.building, req.floor, req.zone_name,
             datetime.utcnow().isoformat()),
        )
        conn.commit()
    conn.close()
    await manager.broadcast()
    return {"ok": True}


@app.post("/api/resolve/{zone_id}")
async def resolve(zone_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE reports SET status='resolved', resolved_at=? "
        "WHERE zone_id=? AND status='active'",
        (datetime.utcnow().isoformat(), zone_id),
    )
    conn.commit()
    conn.close()
    await manager.broadcast()
    return {"ok": True}


@app.get("/api/reports")
async def reports():
    return get_active_reports()


@app.get("/api/zone/{zone_id}", response_class=PlainTextResponse)
async def zone_status(zone_id: str):
    """기기/디버그용: 해당 구역이 활성 신고 상태면 '1', 아니면 '0'."""
    return "1" if is_zone_active(zone_id) else "0"


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """브라우저(지도)용 — 전체 신고 목록 JSON 푸시."""
    await manager.connect_browser(ws)
    try:
        await ws.send_text(
            json.dumps({"type": "update", "reports": get_active_reports()},
                       ensure_ascii=False)
        )
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.websocket("/ws/device/{zone_id}")
async def ws_device(ws: WebSocket, zone_id: str):
    """아두이노(모기약)용 — 해당 구역 상태만 '1'/'0' 푸시.

    접속 즉시 현재 상태 1회 전송, 이후 상태가 바뀔 때마다 전송.
    기기는 텍스트가 '1'로 바뀌는 순간(0→1)에 분사하면 됨.
    """
    await manager.connect_device(ws, zone_id)
    try:
        await ws.send_text("1" if is_zone_active(zone_id) else "0")
        while True:
            await ws.receive_text()  # 기기의 ping/keepalive 수신(무시)
    except WebSocketDisconnect:
        manager.disconnect(ws)


app.mount("/", StaticFiles(directory="static", html=True), name="static")

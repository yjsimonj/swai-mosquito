import os
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

DB_PATH = os.environ.get("DB_PATH", "mosquito.db")
TIMEOUT_MINUTES = 30


class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


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
        await manager.broadcast({"type": "update", "reports": get_active_reports()})


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
    await manager.broadcast({"type": "update", "reports": get_active_reports()})
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
    await manager.broadcast({"type": "update", "reports": get_active_reports()})
    return {"ok": True}


@app.get("/api/reports")
async def reports():
    return get_active_reports()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text(
            json.dumps({"type": "update", "reports": get_active_reports()},
                       ensure_ascii=False)
        )
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


app.mount("/", StaticFiles(directory="static", html=True), name="static")

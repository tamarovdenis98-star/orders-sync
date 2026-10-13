import logging
import os
import re
from datetime import datetime, timezone
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import httpx

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = os.getenv("DB_PATH", "/data/app.db")
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Test task service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SOURCE_URL = os.getenv("SOURCE_URL", "https://test.ooobs.ru/api/orders")


def init_db():
    with db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                phone TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                received INTEGER, "unique" INTEGER,
                duplicates_merged INTEGER, invalid_dropped INTEGER
            );
            CREATE TABLE IF NOT EXISTS sync_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_attempt_at TEXT, last_success_at TEXT,
                last_error TEXT, last_error_at TEXT
            );
            INSERT OR IGNORE INTO sync_meta (id) VALUES (1);
            """
        )


init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Синхронизация заявок ---------------------------------------------------

def normalize_phone(raw) -> str | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    return None


def to_amount(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def to_ts(v) -> float:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def better(a: dict, b: dict) -> bool:
    """True, если запись a должна победить b: больше amount, при равенстве позже created_at."""
    return (a["amount"], to_ts(a["created_at"])) > (b["amount"], to_ts(b["created_at"]))


def fmt_amount(v: float):
    return int(v) if float(v).is_integer() else v


def sync() -> None:
    resp = httpx.get(SOURCE_URL, timeout=10)
    resp.raise_for_status()
    orders = resp.json()
    if not isinstance(orders, list):
        raise ValueError("source is not a JSON array")

    best: dict[str, dict] = {}
    invalid = 0
    for o in orders:
        o = o if isinstance(o, dict) else {}
        phone = normalize_phone(o.get("phone"))
        if not phone:
            invalid += 1
            continue
        rec = {
            "phone": phone,
            "name": str(o.get("name") or ""),
            "email": str(o.get("email") or ""),
            "amount": to_amount(o.get("amount")),
            "created_at": str(o.get("created_at") or ""),
        }
        if phone not in best or better(rec, best[phone]):
            best[phone] = rec

    valid = len(orders) - invalid
    with db() as c:
        # Снимок пересобирается целиком в одной транзакции, phone — PRIMARY KEY: повтор не плодит дубли.
        c.execute("DELETE FROM clients")
        c.executemany(
            "INSERT INTO clients (phone, name, email, amount, created_at) "
            "VALUES (:phone, :name, :email, :amount, :created_at)",
            list(best.values()),
        )
        c.execute(
            "INSERT OR REPLACE INTO sync_stats VALUES (1, ?, ?, ?, ?)",
            (len(orders), len(best), valid - len(best), invalid),
        )


def result() -> dict:
    with db() as c:
        rows = c.execute("SELECT * FROM clients ORDER BY rowid").fetchall()
        st = c.execute("SELECT * FROM sync_stats WHERE id = 1").fetchone()
    if st is None:
        raise HTTPException(502, "source unavailable and no synced data yet")
    return {
        "clients": [
            {"name": r["name"], "phone": r["phone"], "email": r["email"], "amount": fmt_amount(r["amount"])}
            for r in rows
        ],
        "stats": {
            "received": st["received"],
            "unique": st["unique"],
            "duplicates_merged": st["duplicates_merged"],
            "invalid_dropped": st["invalid_dropped"],
        },
    }


log = logging.getLogger("uvicorn.error")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_sync() -> str | None:
    """Синхронизация с фиксацией статуса. Возвращает текст ошибки или None."""
    ts = now()
    try:
        sync()
    except Exception as e:
        err = f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"
        log.error("sync failed, serving last snapshot: %s", err)
        with db() as c:
            c.execute(
                "UPDATE sync_meta SET last_attempt_at=?, last_error=?, last_error_at=? WHERE id=1",
                (ts, err, ts),
            )
        return err
    with db() as c:
        c.execute(
            "UPDATE sync_meta SET last_attempt_at=?, last_success_at=?, last_error=NULL WHERE id=1",
            (ts, ts),
        )
    return None


@app.get("/")
@app.get("/api/clients")
@app.post("/api/sync")
def clients(response: Response):
    err = run_sync()
    data = result()  # 502, если источник недоступен и снимка ещё нет
    with db() as c:
        meta = c.execute("SELECT * FROM sync_meta WHERE id=1").fetchone()
    # Тело строго по схеме, статус синхронизации — в заголовках.
    response.headers["X-Sync-Status"] = "stale" if err else "ok"
    response.headers["X-Last-Sync"] = meta["last_success_at"] or ""
    if err:
        response.headers["X-Sync-Error"] = err.encode("ascii", "replace").decode()[:200]
    return data


@app.get("/api/sync/status")
def sync_status():
    with db() as c:
        meta = dict(c.execute("SELECT * FROM sync_meta WHERE id=1").fetchone())
    meta.pop("id")
    meta["status"] = "stale" if meta["last_error"] else ("ok" if meta["last_success_at"] else "never")
    meta["source_url"] = SOURCE_URL
    return meta


# --- Фронт ---------------------------------------------------------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

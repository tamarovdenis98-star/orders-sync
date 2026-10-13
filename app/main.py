import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
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


def init_db():
    with db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )


init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Пример CRUD (заменить под задание) ---------------------------------

class ItemIn(BaseModel):
    text: str


@app.get("/api/items")
def list_items():
    with db() as c:
        rows = c.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/items", status_code=201)
def create_item(item: ItemIn):
    if not item.text.strip():
        raise HTTPException(400, "text is empty")
    with db() as c:
        cur = c.execute("INSERT INTO items (text) VALUES (?)", (item.text,))
        row = c.execute("SELECT * FROM items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.delete("/api/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    with db() as c:
        cur = c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "not found")


# --- Фронт ---------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

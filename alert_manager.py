import sqlite3
import time
from typing import List, Dict, Any, Optional

DB_FILE = "alerts.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        display_ticker TEXT NOT NULL,
        condition TEXT NOT NULL,
        target_price REAL NOT NULL,
        user_name TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_triggered_at REAL DEFAULT 0
    )
    """)
    # Pastikan kolom user_name ada jika database lama sudah terbentuk
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN user_name TEXT DEFAULT ''")
    except Exception:
        pass

    conn.commit()
    conn.close()

def add_alert(chat_id: str, ticker: str, display_ticker: str, condition: str, target_price: float, user_name: str = "") -> int:
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Hapus alert yang sama jika sudah pernah ada untuk chat_id dan ticker yang sama
    cursor.execute(
        "DELETE FROM alerts WHERE chat_id = ? AND ticker = ? AND condition = ?",
        (str(chat_id), ticker, condition)
    )
    
    cursor.execute("""
        INSERT INTO alerts (chat_id, ticker, display_ticker, condition, target_price, user_name, last_triggered_at)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (str(chat_id), ticker, display_ticker, condition, target_price, user_name))
    
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id

def list_alerts(chat_id: str) -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE chat_id = ? ORDER BY id DESC", (str(chat_id),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def remove_alert(chat_id: str, ticker: str) -> int:
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE chat_id = ? AND display_ticker = ?", (str(chat_id), ticker.upper()))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def get_all_alerts() -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_triggered_time(alert_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET last_triggered_at = ? WHERE id = ?", (time.time(), alert_id))
    conn.commit()
    conn.close()

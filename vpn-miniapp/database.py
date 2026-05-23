"""
database.py — SQLite helpers для vpn_users.db.

Путь к БД берётся из .env (DB_PATH).
При SQLITE_BUSY — retry с экспоненциальной задержкой (до 5 попыток).
"""
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

DB_PATH: str = os.getenv("DB_PATH", "/root/vpn-bot/vpn_users.db")
_MAX_RETRIES = 5


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def _retry(fn, *args, **kwargs):
    """Выполняет fn(), повторяя при 'database is locked'."""
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "database is locked" in str(exc) and attempt < _MAX_RETRIES - 1:
                time.sleep(0.1 * (2 ** attempt))  # 0.1, 0.2, 0.4, 0.8 сек
                last_exc = exc
                continue
            raise
    raise last_exc


def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает пользователя по telegram_id или None."""
    def _q():
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT telegram_id, xray_uuid, email, trial_end_date, "
                "traffic_used, status, proxy_enabled FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    return _retry(_q)


def update_proxy(telegram_id: int, enabled: bool) -> bool:
    """Устанавливает proxy_enabled. Возвращает True при успехе."""
    def _u():
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET proxy_enabled = ? WHERE telegram_id = ?",
                (1 if enabled else 0, telegram_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    try:
        return _retry(_u)
    except Exception:
        return False


def extend_subscription(telegram_id: int, days: int) -> bool:
    """
    Продлевает подписку на `days` дней.
    Если trial_end_date в будущем — продлевает от него.
    Если истёк — продлевает от сегодня.
    Всегда устанавливает status = 'active'.
    """
    def _e():
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT trial_end_date FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = cur.fetchone()
            if not row:
                return False

            try:
                current_end = datetime.strptime(row["trial_end_date"], "%Y-%m-%d")
            except ValueError:
                current_end = datetime.now()

            base = max(current_end, datetime.now())
            new_end_str = (base + timedelta(days=days)).strftime("%Y-%m-%d")

            cur.execute(
                "UPDATE users SET trial_end_date = ?, status = 'active' WHERE telegram_id = ?",
                (new_end_str, telegram_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    try:
        return _retry(_e)
    except Exception:
        return False

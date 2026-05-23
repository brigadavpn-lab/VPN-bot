"""
main.py — FastAPI бэкенд для VPN Mini App.

Запуск для теста:
    cd /root/vpn-miniapp
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload

Swagger: http://127.0.0.1:8000/docs
"""
import json
import os
import sys
import urllib.parse
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ── Импорт proxy_routing из bot-директории ────────────────────────────────
sys.path.insert(0, "/root/vpn-bot")

try:
    from proxy_routing import update_xray_proxy_routing
    _PROXY_OK = True
except ImportError as _e:
    _PROXY_OK = False
    print(f"[WARN] proxy_routing import failed: {_e}")
    print("[WARN] Proxy toggle: DB-only, Xray не перезапустится")

from auth import validate_init_data
from database import extend_subscription, get_user, update_proxy
from payments import PLANS, create_invoice, get_plan, verify_webhook

# ── Конфигурация ──────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

# VLESS — те же параметры что в bot.py
_VPS_ADDR     = os.getenv("SERVER_ADDRESS",     "141.105.143.224")
_VPS_PORT     = int(os.getenv("SERVER_PORT",    "443"))
_REALITY_PBK  = os.getenv("REALITY_PUBLIC_KEY", "O_actbJXCoMijlOyrLMWWKQQ7a3tEYZe3Hix86Yr3kM")
_REALITY_SID  = os.getenv("REALITY_SHORT_ID",   "a028507ab5b114b4")
_REALITY_SNI  = os.getenv("REALITY_SNI",        "www.yahoo.com")


def _vless_link(xray_uuid: str) -> str:
    params = urllib.parse.urlencode({
        "security": "reality",
        "sni":      _REALITY_SNI,
        "pbk":      _REALITY_PBK,
        "sid":      _REALITY_SID,
        "flow":     "xtls-rprx-vision",
        "type":     "tcp",
    })
    return f"vless://{xray_uuid}@{_VPS_ADDR}:{_VPS_PORT}?{params}#olegych"


def _notify_user_paid(tg_id: int, plan_name: str, end_date: str) -> None:
    """
    Уведомляет пользователя в Telegram об успешной оплате.
    Прямой HTTPS POST на Bot API — без импорта telebot.
    Сбой уведомления не должен ломать webhook-ответ CryptoPay.
    """
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":    tg_id,
                "text":       (
                    f"✅ *Оплата прошла!*\n\n"
                    f"Тариф: *{plan_name}*\n"
                    f"Подписка активна до: *{end_date}*"
                ),
                "parse_mode": "Markdown",
            },
            timeout=5,
        )
    except Exception as exc:
        print(f"[WARN] notify_user_paid failed for {tg_id}: {exc}")


# ── FastAPI ────────────────────────────────────────────────────────────────
app = FastAPI(title="VPN Mini App API", version="1.0.0", docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # credentials=False обязательно при origins=["*"] по спеке CORS.
    # Авторизация идёт через заголовок X-Telegram-Init-Data, cookies не нужны.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Статика — FastAPI отдаёт напрямую (удобно без nginx в dev-режиме).
# В prod nginx отдаёт /app/ статику сам (быстрее).
_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/app", StaticFiles(directory=_static, html=True), name="static")


# ── Dependency ────────────────────────────────────────────────────────────
async def current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
) -> dict:
    """Валидирует initData, возвращает user dict."""
    return validate_init_data(x_telegram_init_data, BOT_TOKEN)


# ── Pydantic models ───────────────────────────────────────────────────────
class ProxyToggleBody(BaseModel):
    enabled: bool


class PaymentCreateBody(BaseModel):
    plan_id: int
    asset: Optional[str] = "USDT"


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Healthcheck. Без авторизации."""
    return {"status": "ok", "proxy_routing_available": _PROXY_OK}


@app.get("/api/plans")
async def plans_list():
    """Список тарифных планов. Без авторизации."""
    return {"plans": PLANS}


@app.get("/api/user/me")
async def user_me(user: dict = Depends(current_user)):
    """
    Профиль пользователя.
    Header: X-Telegram-Init-Data: <window.Telegram.WebApp.initData>
    """
    tg_id: int = user["id"]
    db_user = get_user(tg_id)

    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден. Зарегистрируйтесь через бота: /start",
        )

    return {
        "telegram_id":    db_user["telegram_id"],
        "first_name":     user.get("first_name", ""),
        "username":       user.get("username", ""),
        "status":         db_user["status"],
        "trial_end_date": db_user["trial_end_date"],
        "proxy_enabled":  bool(db_user["proxy_enabled"]),
        "traffic_used":   db_user.get("traffic_used", 0),
    }


@app.get("/api/user/key")
async def user_key(user: dict = Depends(current_user)):
    """
    VLESS ссылка пользователя.
    Возвращает 403 если подписка неактивна.
    """
    tg_id: int = user["id"]
    db_user = get_user(tg_id)

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user["status"] != "active":
        raise HTTPException(
            status_code=403,
            detail="Подписка неактивна. Оплатите тариф для получения ключа.",
        )

    return {"vless_link": _vless_link(db_user["xray_uuid"])}


@app.post("/api/proxy/toggle")
async def proxy_toggle(body: ProxyToggleBody, user: dict = Depends(current_user)):
    """
    Включает/выключает ротационный прокси.
    1. Обновляет proxy_enabled в БД
    2. Вызывает update_xray_proxy_routing() → перестраивает Xray routing для ВСЕХ users
    """
    tg_id: int = user["id"]

    if not get_user(tg_id):
        raise HTTPException(status_code=404, detail="User not found")

    if not update_proxy(tg_id, body.enabled):
        raise HTTPException(status_code=500, detail="DB update failed")

    xray_ok = False
    if _PROXY_OK:
        try:
            xray_ok = update_xray_proxy_routing()
        except Exception as exc:
            # DB уже обновлена — не роллбэчим, логируем
            print(f"[ERROR] update_xray_proxy_routing: {exc}")

    return {"proxy_enabled": body.enabled, "xray_updated": xray_ok}


@app.post("/api/payment/create")
async def payment_create(body: PaymentCreateBody, user: dict = Depends(current_user)):
    """
    Создаёт инвойс CryptoPay.
    Возвращает invoice_id, pay_url, amount, currency, plan_name.
    """
    tg_id: int = user["id"]

    if not get_plan(body.plan_id):
        raise HTTPException(status_code=400, detail=f"Unknown plan_id: {body.plan_id}")

    allowed = {"USDT", "TON", "USDC"}
    asset = (body.asset or "USDT").upper()
    if asset not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported asset: {asset}")

    result = create_invoice(tg_id, body.plan_id, asset)
    if not result:
        raise HTTPException(
            status_code=502,
            detail="Ошибка создания инвойса. Проверь CRYPTOPAY_TOKEN в .env",
        )

    return result


@app.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    """
    CryptoPay webhook при оплате.
    Верифицирует HMAC подпись → продлевает подписку → шлёт уведомление в Telegram.
    Заголовок: crypto-pay-api-signature
    """
    body = await request.body()
    sig  = request.headers.get("crypto-pay-api-signature", "")

    if not verify_webhook(body, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("update_type") != "invoice_paid":
        return {"ok": True, "skipped": True}

    # payload = "{user_id}:{plan_id}"
    raw_payload = data.get("payload", {}).get("payload", "")
    try:
        user_id_str, plan_id_str = raw_payload.split(":", 1)
        tg_id   = int(user_id_str)
        plan_id = int(plan_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Bad payload: {raw_payload!r}")

    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan_id: {plan_id}")

    if not extend_subscription(tg_id, plan["days"]):
        raise HTTPException(status_code=500, detail="Subscription extension failed")

    # Уведомление пользователя — не критично для webhook-ответа.
    updated = get_user(tg_id)
    end_date = updated["trial_end_date"] if updated else "?"
    _notify_user_paid(tg_id, plan["name"], end_date)

    print(f"[INFO] Paid: user={tg_id}, plan={plan['name']}, +{plan['days']}d")
    return {"ok": True}

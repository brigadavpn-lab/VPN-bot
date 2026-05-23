"""
payments.py — CryptoPay API интеграция.

Для теста: CRYPTOPAY_API_URL=https://testnet-pay.crypt.bot/api  (@CryptoTestnetBot)
Для prod:  CRYPTOPAY_API_URL=https://pay.crypt.bot/api           (@CryptoBot)
"""
import hashlib
import hmac
import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

CRYPTOPAY_TOKEN: str   = os.getenv("CRYPTOPAY_TOKEN", "")
CRYPTOPAY_API_URL: str = os.getenv("CRYPTOPAY_API_URL", "https://pay.crypt.bot/api")

# Тарифные планы — ЦЕНЫ-ЗАГЛУШКИ, замени перед запуском
PLANS: List[Dict] = [
    {"id": 1, "name": "1 месяц",   "days": 30,  "price": "3.00",  "currency": "USDT"},
    {"id": 2, "name": "3 месяца",  "days": 90,  "price": "8.00",  "currency": "USDT"},
    {"id": 3, "name": "6 месяцев", "days": 180, "price": "14.00", "currency": "USDT"},
]


def get_plan(plan_id: int) -> Optional[Dict]:
    return next((p for p in PLANS if p["id"] == plan_id), None)


def create_invoice(user_id: int, plan_id: int, asset: str = "USDT") -> Optional[Dict]:
    """
    Создаёт инвойс CryptoPay.
    payload инвойса: "{user_id}:{plan_id}" — вернётся в webhook.
    Возвращает dict(invoice_id, pay_url, amount, currency, plan_name) или None.
    """
    if not CRYPTOPAY_TOKEN:
        return None

    plan = get_plan(plan_id)
    if not plan:
        return None

    try:
        resp = requests.post(
            f"{CRYPTOPAY_API_URL}/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTOPAY_TOKEN},
            json={
                "asset":       asset,
                "amount":      plan["price"],
                "description": f"BrigadaVPN — {plan['name']}",
                "payload":     f"{user_id}:{plan_id}",
                "expires_in":  3600,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            return None

        r = data["result"]
        return {
            "invoice_id": r["invoice_id"],
            "pay_url":    r.get("bot_invoice_url") or r.get("pay_url"),
            "amount":     plan["price"],
            "currency":   asset,
            "plan_name":  plan["name"],
        }
    except Exception as exc:
        print(f"[CryptoPay] create_invoice error: {exc}")
        return None


def verify_webhook(body: bytes, signature: str) -> bool:
    """
    Верифицирует HMAC-SHA256 подпись из заголовка crypto-pay-api-signature.
    Algorithm: HMAC-SHA256(key=SHA256(token), msg=body)
    """
    if not CRYPTOPAY_TOKEN or not signature:
        return False
    try:
        secret = hashlib.sha256(CRYPTOPAY_TOKEN.encode()).digest()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.lower())
    except Exception:
        return False

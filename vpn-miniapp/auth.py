"""
auth.py — Валидация Telegram WebApp initData (HMAC-SHA256).

Алгоритм: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import urllib.parse

from fastapi import HTTPException


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """
    Проверяет подпись Telegram initData.
    Возвращает dict пользователя или raises HTTPException(401).
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="initData is empty")

    try:
        params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        hash_value = params.pop("hash", None)

        if not hash_value:
            raise HTTPException(status_code=401, detail="hash field missing in initData")

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )

        # secret_key = HMAC-SHA256(key=b"WebAppData", msg=bot_token)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        # expected_hash = HMAC-SHA256(key=secret_key, msg=data_check_string)
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, hash_value):
            raise HTTPException(status_code=401, detail="initData hash mismatch")

        user = json.loads(params.get("user", "{}"))

        if not user.get("id"):
            raise HTTPException(status_code=401, detail="user.id missing in initData")

        return user

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Auth error: {exc}") from exc

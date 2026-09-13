import os
import json
import hmac
import hashlib
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore


app = FastAPI(title="OXISA API", version="1.0.0")


# =========================
# Firebase
# =========================

firebase_credentials = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

if not firebase_credentials:
    raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is not configured")

cred = credentials.Certificate(json.loads(firebase_credentials))

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()


# =========================
# Telegram WebApp Auth
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")


def verify_telegram_init_data(init_data: str) -> dict:
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        received_hash = parsed.pop("hash", None)

        if not received_hash:
            raise ValueError("Telegram hash missing")

        data_check_string = "\n".join(
            f"{key}={parsed[key]}"
            for key in sorted(parsed)
        )

        secret_key = hmac.new(
            b"WebAppData",
            TELEGRAM_BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise ValueError("Invalid Telegram authentication")

        if "user" not in parsed:
            raise ValueError("Telegram user data missing")

        return json.loads(parsed["user"])

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Telegram authentication failed: {str(e)}"
        )


# =========================
# Request Model
# =========================

class TelegramAuthRequest(BaseModel):
    initData: str


# =========================
# Health Check
# =========================

@app.get("/")
def root():
    return {
        "status": "online",
        "app": "OXISA",
        "version": "1.0.0"
    }


# =========================
# Automatic User Registration
# =========================

@app.post("/api/auth/telegram")
def telegram_login(data: TelegramAuthRequest):

    telegram_user = verify_telegram_init_data(data.initData)

    telegram_id = telegram_user.get("id")

    if not telegram_id:
        raise HTTPException(
            status_code=400,
            detail="Telegram user ID missing"
        )

    user_ref = db.collection("users").document(str(telegram_id))
    user_doc = user_ref.get()

    user_data = {
        "telegramId": int(telegram_id),
        "username": telegram_user.get("username", ""),
        "firstName": telegram_user.get("first_name", ""),
        "lastName": telegram_user.get("last_name", ""),
        "photoUrl": "",
        "languageCode": telegram_user.get("language_code", ""),
        "isActive": True,
        "isBanned": False,
        "lastActiveAt": firestore.SERVER_TIMESTAMP,
    }

    if not user_doc.exists:

        user_data["isAdmin"] = False
        user_data["createdAt"] = firestore.SERVER_TIMESTAMP

        user_ref.set(user_data)

        return {
            "success": True,
            "newUser": True,
            "user": {
                "telegramId": int(telegram_id),
                "username": user_data["username"],
                "firstName": user_data["firstName"],
                "lastName": user_data["lastName"]
            }
        }

    else:

        user_ref.update({
            "username": user_data["username"],
            "firstName": user_data["firstName"],
            "lastName": user_data["lastName"],
            "languageCode": user_data["languageCode"],
            "isActive": True,
            "lastActiveAt": firestore.SERVER_TIMESTAMP
        })

        existing_user = user_doc.to_dict()

        if existing_user.get("isBanned", False):
            raise HTTPException(
                status_code=403,
                detail="User is banned"
            )

        return {
            "success": True,
            "newUser": False,
            "user": {
                "telegramId": int(telegram_id),
                "username": user_data["username"],
                "firstName": user_data["firstName"],
                "lastName": user_data["lastName"]
            }
}

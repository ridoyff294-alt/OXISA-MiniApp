import os
import json
import hmac
import hashlib
import time
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import firebase_admin
from firebase_admin import credentials, firestore


# =========================================================
# OXISA API
# =========================================================

app = FastAPI(
    title="OXISA API",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ridoyff294-alt.github.io"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# =========================================================
# Firebase
# =========================================================

firebase_credentials = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_JSON"
)

if not firebase_credentials:
    raise RuntimeError(
        "FIREBASE_SERVICE_ACCOUNT_JSON is not configured"
    )

try:
    firebase_config = json.loads(firebase_credentials)

    cred = credentials.Certificate(firebase_config)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    db = firestore.client()

except Exception as e:
    raise RuntimeError(
        f"Firebase initialization failed: {str(e)}"
    )


# =========================================================
# Telegram Bot Token
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is not configured"
    )


# =========================================================
# Telegram WebApp Authentication
# =========================================================

def verify_telegram_init_data(init_data: str) -> dict:

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Telegram authentication data missing"
        )

    try:

        # Parse Telegram initData
        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )

        # Get Telegram hash
        received_hash = parsed.pop("hash", None)

        if not received_hash:
            raise ValueError(
                "Telegram hash missing"
            )

        # -------------------------------------------------
        # Check auth_date
        # -------------------------------------------------

        auth_date = parsed.get("auth_date")

        if not auth_date:
            raise ValueError(
                "Telegram auth_date missing"
            )

        try:
            auth_timestamp = int(auth_date)
        except ValueError:
            raise ValueError(
                "Invalid Telegram auth_date"
            )

        # Allow authentication data for 24 hours
        current_time = int(time.time())

        if current_time - auth_timestamp > 86400:
            raise ValueError(
                "Telegram authentication data expired"
            )

        # Prevent future timestamps
        if auth_timestamp - current_time > 300:
            raise ValueError(
                "Invalid Telegram authentication timestamp"
            )

        # -------------------------------------------------
        # Create data-check-string
        # -------------------------------------------------

        data_check_string = "\n".join(
            f"{key}={parsed[key]}"
            for key in sorted(parsed)
        )

        # -------------------------------------------------
        # Telegram secret key
        # -------------------------------------------------

        secret_key = hmac.new(
            b"WebAppData",
            TELEGRAM_BOT_TOKEN.encode("utf-8"),
            hashlib.sha256
        ).digest()

        # -------------------------------------------------
        # Calculate hash
        # -------------------------------------------------

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # -------------------------------------------------
        # Compare hashes securely
        # -------------------------------------------------

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):
            raise ValueError(
                "Invalid Telegram authentication"
            )

        # -------------------------------------------------
        # Telegram user data
        # -------------------------------------------------

        if "user" not in parsed:
            raise ValueError(
                "Telegram user data missing"
            )

        telegram_user = json.loads(
            parsed["user"]
        )

        if not isinstance(
            telegram_user,
            dict
        ):
            raise ValueError(
                "Invalid Telegram user data"
            )

        return telegram_user

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=401,
            detail=(
                "Telegram authentication failed: "
                + str(e)
            )
        )


# =========================================================
# Request Model
# =========================================================

class TelegramAuthRequest(BaseModel):
    initData: str


# =========================================================
# Health Check
# =========================================================

@app.get("/")
def root():

    return {
        "status": "online",
        "app": "OXISA",
        "version": "1.0.0"
    }


# =========================================================
# Telegram Login / Automatic User Registration
# =========================================================

@app.post("/api/auth/telegram")
def telegram_login(
    data: TelegramAuthRequest
):

    # -----------------------------------------------------
    # Verify Telegram
    # -----------------------------------------------------

    telegram_user = verify_telegram_init_data(
        data.initData
    )

    # -----------------------------------------------------
    # Telegram User ID
    # -----------------------------------------------------

    telegram_id = telegram_user.get("id")

    if not telegram_id:

        raise HTTPException(
            status_code=400,
            detail="Telegram user ID missing"
        )

    # -----------------------------------------------------
    # User information
    # -----------------------------------------------------

    username = telegram_user.get(
        "username",
        ""
    )

    first_name = telegram_user.get(
        "first_name",
        ""
    )

    last_name = telegram_user.get(
        "last_name",
        ""
    )

    photo_url = telegram_user.get(
        "photo_url",
        ""
    )

    language_code = telegram_user.get(
        "language_code",
        ""
    )

    # -----------------------------------------------------
    # Firestore user document
    # -----------------------------------------------------

    user_ref = (
        db.collection("users")
        .document(str(telegram_id))
    )

    user_doc = user_ref.get()

    # -----------------------------------------------------
    # Existing user: check ban BEFORE updating
    # -----------------------------------------------------

    if user_doc.exists:

        existing_user = user_doc.to_dict()

        if existing_user.get(
            "isBanned",
            False
        ):

            raise HTTPException(
                status_code=403,
                detail="User is banned"
            )

        # Update latest Telegram information
        user_ref.update({

            "username": username,

            "firstName": first_name,

            "lastName": last_name,

            "photoUrl": photo_url,

            "languageCode": language_code,

            "isActive": True,

            "lastActiveAt":
                firestore.SERVER_TIMESTAMP
        })

        return {

            "success": True,

            "newUser": False,

            "user": {

                "telegramId":
                    int(telegram_id),

                "username":
                    username,

                "firstName":
                    first_name,

                "lastName":
                    last_name,

                "photoUrl":
                    photo_url
            }
        }

    # -----------------------------------------------------
    # New user
    # -----------------------------------------------------

    user_data = {

        "telegramId":
            int(telegram_id),

        "username":
            username,

        "firstName":
            first_name,

        "lastName":
            last_name,

        "photoUrl":
            photo_url,

        "languageCode":
            language_code,

        "isActive":
            True,

        "isBanned":
            False,

        "isAdmin":
            False,

        "createdAt":
            firestore.SERVER_TIMESTAMP,

        "lastActiveAt":
            firestore.SERVER_TIMESTAMP
    }

    user_ref.set(user_data)

    return {

        "success": True,

        "newUser": True,

        "user": {

            "telegramId":
                int(telegram_id),

            "username":
                username,

            "firstName":
                first_name,

            "lastName":
                last_name,

            "photoUrl":
                photo_url
        }
    }

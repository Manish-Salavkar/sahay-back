# backend/auth/utils.py

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status
from jose import jwt

from app.config import (
    SECRET_KEY,
    TOKENALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)


ph = PasswordHasher()


# ------------------------------------------------------------------------------
# Password Hashing
# ------------------------------------------------------------------------------

async def hash_password(password: str) -> str:
    return ph.hash(password)


async def verify_password(
    hashed_password: str,
    plain_password: str,
) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password verification failed",
        )


# ------------------------------------------------------------------------------
# JWT
# ------------------------------------------------------------------------------

async def create_access_token(
    *,
    user_id: int,
    role: str,
    preferred_language: str,
):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "lang": preferred_language,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=TOKENALGORITHM,
    )
# backend/auth/services.py

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, BlacklistedTokens
from app.auth.schemas import *
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.config import SECRET_KEY, TOKENALGORITHM
from app.database import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ------------------------------------------------------------------------------
# Current User
# ------------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    blacklisted = (
        await db.execute(
            select(BlacklistedTokens).where(
                BlacklistedTokens.token == token
            )
        )
    ).scalar_one_or_none()

    if blacklisted:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[TOKENALGORITHM],
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        await db.execute(
            select(User).where(User.id == int(user_id))
        )
    ).scalar_one_or_none()

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is disabled",
        )

    return user


# ------------------------------------------------------------------------------
# Login
# ------------------------------------------------------------------------------

async def authenticate_user(
    db: AsyncSession,
    credentials: LoginInput,
):

    user = (
        await db.execute(
            select(User).where(
                User.employee_id == credentials.employee_id
            )
        )
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid employee ID or password",
        )

    if not await verify_password(
        user.password,
        credentials.password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid employee ID or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is disabled",
        )

    user.last_login = datetime.now(timezone.utc)

    token = await create_access_token(
        user_id=user.id,
        role=user.role,
        preferred_language=user.preferred_language,
    )

    await db.flush()

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


# ------------------------------------------------------------------------------
# Create User
# ------------------------------------------------------------------------------

async def create_user_service(
    db: AsyncSession,
    user: CreateUser,
):

    existing = (
        await db.execute(
            select(User).where(
                User.employee_id == user.employee_id
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Employee ID already exists",
        )

    existing_email = (
        await db.execute(
            select(User).where(
                User.email == user.email
            )
        )
    ).scalar_one_or_none()

    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="Email already exists",
        )

    hashed = await hash_password(user.password)

    db_user = User(
        employee_id=user.employee_id,
        full_name=user.full_name,
        email=user.email,
        password=hashed,
        role=user.role,
        department=user.department,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
    )

    db.add(db_user)

    await db.flush()
    await db.refresh(db_user)

    return {
        "message": "User created successfully",
        "data": UserOut.model_validate(db_user),
    }


# ------------------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------------------

async def blacklist_token_service(
    db: AsyncSession,
    data: BlacklistedTokenSubmit,
):

    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid token",
    )

    try:

        payload = jwt.decode(
            data.token,
            SECRET_KEY,
            algorithms=[TOKENALGORITHM],
        )

        user_id = payload.get("sub")
        exp = payload.get("exp")

        if user_id is None or exp is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    db.add(
        BlacklistedTokens(
            token=data.token,
            expires_at=datetime.fromtimestamp(
                exp,
                tz=timezone.utc,
            ),
            reason=data.reason,
            user_id=int(user_id),
        )
    )

    await db.flush()

    return {
        "message": "Logged out successfully"
    }


# ------------------------------------------------------------------------------
# Toggle User Status
# ------------------------------------------------------------------------------

async def toggle_user_status_service(
    db: AsyncSession,
    user_id: int,
):

    user = (
        await db.execute(
            select(User).where(
                User.id == user_id
            )
        )
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.is_active = not user.is_active

    await db.flush()
    await db.refresh(user)

    return {
        "message": "User status updated",
        "data": UserOut.model_validate(user),
    }
# backend/auth/services.py

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, BlacklistedTokens, RolePermission
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

    # =====================================================================
    # BACKEND/APP CHANGE SEPARATOR: USER APPROVAL LOGIN CHECK
    # =====================================================================
    if hasattr(user, "is_approved") and not user.is_approved:
        raise HTTPException(
            status_code=403,
            detail="Your account is pending admin approval.",
        )
    # =====================================================================
    # END OF BACKEND/APP CHANGE SEPARATOR
    # =====================================================================

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

    # =====================================================================
    # BACKEND/APP CHANGE SEPARATOR: ALL NEW REGISTRATIONS REQUIRE APPROVAL
    # =====================================================================
    db_user = User(
        employee_id=user.employee_id,
        full_name=user.full_name,
        email=user.email,
        password=hashed,
        role=user.role,
        department=user.department,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        is_approved=False,
    )
    # =====================================================================
    # END OF BACKEND/APP CHANGE SEPARATOR
    # =====================================================================

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


# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: RBAC ADMIN SERVICES
# =====================================================================

async def get_all_users_service(db: AsyncSession):
    result = await db.execute(select(User).order_by(User.id.desc()))
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]


async def approve_user_service(db: AsyncSession, user_id: int, is_approved: bool):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_approved = is_approved
    await db.flush()
    await db.refresh(user)
    return {"message": "User approval status updated", "data": UserOut.model_validate(user)}


async def update_user_role_service(db: AsyncSession, user_id: int, role: str):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.role = role
    await db.flush()
    await db.refresh(user)
    return {"message": "User role updated successfully", "data": UserOut.model_validate(user)}


# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: RBAC DEFAULT SERVICES LIST
# =====================================================================
# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: RBAC DEFAULT SERVICES LIST
# =====================================================================
DEFAULT_SERVICES = ["chatbot", "dashboard", "translation", "review"]
DEFAULT_ROLES = ["officer", "reviewer", "translator"]
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================

async def seed_default_permissions_if_empty(db: AsyncSession):
    existing = (await db.execute(select(RolePermission))).scalars().all()
    if not existing:
        for r in DEFAULT_ROLES:
            for s in DEFAULT_SERVICES:
                perm = RolePermission(role=r, service=s, is_enabled=True)
                db.add(perm)
        await db.flush()


async def get_role_permissions_service(db: AsyncSession):
    await seed_default_permissions_if_empty(db)
    result = await db.execute(select(RolePermission))
    perms = result.scalars().all()
    return [RolePermissionSchema.model_validate(p) for p in perms]


async def toggle_role_permission_service(db: AsyncSession, role: str, service: str, is_enabled: bool):
    await seed_default_permissions_if_empty(db)
    perm = (await db.execute(
        select(RolePermission).where(
            RolePermission.role == role,
            RolePermission.service == service
        )
    )).scalar_one_or_none()

    if not perm:
        perm = RolePermission(role=role, service=service, is_enabled=is_enabled)
        db.add(perm)
    else:
        perm.is_enabled = is_enabled
    
    await db.flush()
    await db.refresh(perm)
    return {"message": "Role permission updated", "data": RolePermissionSchema.model_validate(perm)}


async def get_user_accessible_services(db: AsyncSession, current_user: User):
    if current_user.role == "admin":
        return {"role": current_user.role, "services": DEFAULT_SERVICES}
    
    await seed_default_permissions_if_empty(db)
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role == current_user.role,
            RolePermission.is_enabled == True
        )
    )
    enabled_perms = result.scalars().all()
    services = [p.service for p in enabled_perms]
    return {"role": current_user.role, "services": services}


# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: INITIAL SEED ADMIN CREATION
# =====================================================================
async def seed_initial_admin_service(db: AsyncSession):
    existing_admin = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
    if not existing_admin:
        hashed = await hash_password("admin123")
        admin_user = User(
            employee_id="ADMIN-001",
            full_name="System Administrator",
            email="admin@gov.in",
            password=hashed,
            role="admin",
            department="IT Administration",
            preferred_language="en",
            is_active=True,
            is_approved=True,
        )
        db.add(admin_user)
        await db.commit()
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
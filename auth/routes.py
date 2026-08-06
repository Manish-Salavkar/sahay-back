from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from app.auth.models import User
from app.auth.schemas import (
    CreateUser,
    LoginInput,
    BlacklistedTokenSubmit,
)
from app.auth.services import (
    create_user_service,
    authenticate_user,
    blacklist_token_service,
    toggle_user_status_service,
    get_current_user,
)

from app.auth.schemas import UserOut


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ------------------------------------------------------------------------------
# Register User
# ------------------------------------------------------------------------------

@router.post("/register", status_code=201)
async def register_user(
    user: CreateUser,
    db: AsyncSession = Depends(get_db),
):

    result = await create_user_service(db, user)

    await db.commit()

    return result


# ------------------------------------------------------------------------------
# Login
# ------------------------------------------------------------------------------

@router.post("/login")
async def login(
    credentials: LoginInput,
    db: AsyncSession = Depends(get_db),
):

    result = await authenticate_user(db, credentials)

    await db.commit()

    return result


# ------------------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------------------

@router.post("/logout")
async def logout(
    data: BlacklistedTokenSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    result = await blacklist_token_service(db, data)

    await db.commit()

    return result


# ------------------------------------------------------------------------------
# Current User
# ------------------------------------------------------------------------------

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):

    return UserOut.model_validate(current_user)


# ------------------------------------------------------------------------------
# Toggle Active Status (Admin)
# ------------------------------------------------------------------------------

@router.patch("/toggle-status/{user_id}")
async def toggle_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    # Uncomment when admin authorization is added.
    #
    # if current_user.role != "admin":
    #     raise HTTPException(
    #         status_code=403,
    #         detail="Only admins can perform this action",
    #     )

    result = await toggle_user_status_service(
        db,
        user_id,
    )

    await db.commit()

    return result


# ------------------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------------------

@router.get("/protected")
async def protected_route(
    current_user: User = Depends(get_current_user),
):

    return {
        "message": "Authentication successful.",
        "user": current_user.full_name,
        "role": current_user.role,
    }
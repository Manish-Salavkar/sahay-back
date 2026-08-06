from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from app.auth.models import User
from app.auth.schemas import (
    CreateUser,
    LoginInput,
    BlacklistedTokenSubmit,
    UserOut,
    ApproveUserSchema,
    UpdateUserRoleSchema,
    TogglePermissionSchema,
)
from app.auth.services import (
    create_user_service,
    authenticate_user,
    blacklist_token_service,
    toggle_user_status_service,
    get_current_user,
    get_all_users_service,
    approve_user_service,
    update_user_role_service,
    get_role_permissions_service,
    toggle_role_permission_service,
    get_user_accessible_services,
)


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


# =====================================================================
# BACKEND/APP CHANGE SEPARATOR: RBAC ADMIN ENDPOINTS
# =====================================================================

def check_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")

@router.get("/admin/users")
async def get_admin_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin(current_user)
    return await get_all_users_service(db)


@router.patch("/admin/users/{user_id}/approve")
async def approve_user_route(
    user_id: int,
    body: ApproveUserSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin(current_user)
    res = await approve_user_service(db, user_id, body.is_approved)
    await db.commit()
    return res


@router.patch("/admin/users/{user_id}/role")
async def update_user_role_route(
    user_id: int,
    body: UpdateUserRoleSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin(current_user)
    res = await update_user_role_service(db, user_id, body.role)
    await db.commit()
    return res


@router.get("/admin/permissions")
async def get_admin_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin(current_user)
    return await get_role_permissions_service(db)


@router.post("/admin/permissions")
async def toggle_admin_permission(
    body: TogglePermissionSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check_admin(current_user)
    res = await toggle_role_permission_service(db, body.role, body.service, body.is_enabled)
    await db.commit()
    return res


@router.get("/services/me")
async def get_my_services(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_accessible_services(db, current_user)

# =====================================================================
# END OF BACKEND/APP CHANGE SEPARATOR
# =====================================================================
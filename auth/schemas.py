from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ------------------------------------------------------------------------------
# Base User Schema
# ------------------------------------------------------------------------------

class UserBase(BaseModel):
    employee_id: str = Field(..., min_length=3, max_length=20)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr

    role: Literal[
        "admin",
        "officer",
        "reviewer",
        "translator"
    ] = "officer"

    department: str | None = None

    preferred_language: Literal[
        "en",
        "mr",
        "hi"
    ] = "en"

    is_active: bool = True


# ------------------------------------------------------------------------------
# Create User
# ------------------------------------------------------------------------------

class CreateUser(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


# ------------------------------------------------------------------------------
# User Response
# ------------------------------------------------------------------------------

class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    last_login: datetime | None = None


# ------------------------------------------------------------------------------
# Update User
# ------------------------------------------------------------------------------

class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)

    email: EmailStr | None = None

    password: str | None = Field(default=None, min_length=8, max_length=128)

    role: Literal[
        "admin",
        "officer",
        "reviewer",
        "translator"
    ] | None = None

    department: str | None = None

    preferred_language: Literal[
        "en",
        "mr",
        "hi"
    ] | None = None

    is_active: bool | None = None


# ------------------------------------------------------------------------------
# Login
# ------------------------------------------------------------------------------

class LoginInput(BaseModel):
    employee_id: str
    password: str


# ------------------------------------------------------------------------------
# JWT Response
# ------------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ------------------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------------------

class BlacklistedTokenSubmit(BaseModel):
    token: str
    reason: str | None = None


# ------------------------------------------------------------------------------
# Generic Response
# ------------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str


# ------------------------------------------------------------------------------
# Login Response
# ------------------------------------------------------------------------------

class LoginResponse(BaseModel):
    access_token: str
    token_type: str

    user: UserOut


class FeedbackCreate(BaseModel):
    message_id: Optional[int] = None
    session_id: Optional[int] = None
    answered: Optional[str] = None
    accuracy: Optional[int] = None
    citations_relevant: Optional[str] = None
    comments: Optional[str] = None
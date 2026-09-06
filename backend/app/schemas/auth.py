"""Authentication request/response schemas (TRD 12.1).

`extra="forbid"` on every request model: unknown fields are rejected rather than
silently ignored (TRD 29.3).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.rbac import UserRole

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    """Self-registration.

    Self-service registration always creates a FARMER (TRD 12.1). Privileged accounts
    are created by an admin, so there is deliberately no `role` field here.
    """

    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(max_length=20)
    password: str = Field(min_length=8, max_length=128)
    preferred_language: str = Field(default="en", pattern="^(en|hi|mr)$")
    village: str | None = Field(default=None, max_length=120)
    taluka: str | None = Field(default=None, max_length=120)
    district_code: str | None = Field(default=None, max_length=20)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        normalised = v.strip().replace(" ", "").replace("-", "")
        if not PHONE_RE.match(normalised):
            raise ValueError("phone must be 7-15 digits, optionally prefixed with '+'")
        return normalised


class LoginRequest(StrictModel):
    """`identifier` accepts phone, email or username (TRD 12.1)."""

    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=10, max_length=512)


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str | None
    # Deliberately `str`, not `EmailStr`: this is an OUTPUT model. Re-running strict
    # input validation on the way out turns any already-stored value the validator
    # dislikes into a 500. Email format is validated on input, where it belongs.
    email: str | None
    username: str | None
    role: UserRole
    preferred_language: str
    district_code: str | None
    is_active: bool
    created_at: datetime


class MeOut(BaseModel):
    user: UserOut
    farmer_id: uuid.UUID | None
    permissions: list[str]


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterResponse(BaseModel):
    user: UserOut
    tokens: TokenPair

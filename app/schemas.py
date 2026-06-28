"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import PaymentStatus, Role, TicketStatus

# --------------------------------------------------------------------------- #
# Users / auth
# --------------------------------------------------------------------------- #


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role
    created_at: datetime


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------------------------------------------------------------------------- #
# Tickets
# --------------------------------------------------------------------------- #


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TicketStatus
    created_at: datetime
    confirmed_at: datetime | None = None
    checked_in_at: datetime | None = None
    # Present only once the ticket is confirmed.
    ticket_code: str | None = None
    qr_png_base64: str | None = None


class RegisterResponse(BaseModel):
    user: UserOut
    ticket: TicketOut
    access_token: str
    token_type: str = "bearer"


class JobAccepted(BaseModel):
    job_id: str
    status: str = "pending"
    status_url: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending | completed | failed
    result: RegisterResponse | None = None
    error: dict | None = None


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #


class OrderResponse(BaseModel):
    order_id: str
    amount: int = Field(description="Amount in the smallest currency unit (paise).")
    currency: str
    status: PaymentStatus


class WebhookRequest(BaseModel):
    order_id: str
    status: str = Field(description="Gateway result: 'paid' or 'failed'.")
    signature: str = Field(description="HMAC-SHA256 of 'order_id:status' using the webhook secret.")


class WebhookResponse(BaseModel):
    order_id: str
    payment_status: PaymentStatus
    ticket_status: TicketStatus


# --------------------------------------------------------------------------- #
# Check-in
# --------------------------------------------------------------------------- #


class CheckinRequest(BaseModel):
    ticket_code: str = Field(min_length=1, description="The signed token encoded in the ticket QR.")


class CheckedInStudent(BaseModel):
    id: int
    name: str
    email: EmailStr


class CheckinResponse(BaseModel):
    ticket_id: int
    status: TicketStatus
    student: CheckedInStudent
    checked_in_at: datetime


# --------------------------------------------------------------------------- #
# Volunteer / admin
# --------------------------------------------------------------------------- #


class RegistrationItem(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    ticket_id: int
    ticket_status: TicketStatus
    registered_at: datetime
    checked_in_at: datetime | None = None


class RegistrationsPage(BaseModel):
    items: list[RegistrationItem]
    total: int
    page: int
    page_size: int


class StatsResponse(BaseModel):
    event: str
    capacity: int
    total_registered: int
    paid: int  # confirmed + checked_in
    checked_in: int
    remaining: int

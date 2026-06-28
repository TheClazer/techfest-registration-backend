"""Payment endpoints: create an order and receive the (mock) gateway webhook."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import OrderResponse, WebhookRequest, WebhookResponse
from ..services.payments import create_order, process_webhook

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/order", response_model=OrderResponse, summary="Create (or fetch) a payment order for your ticket")
def create_payment_order(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    payment = create_order(db, user=user)
    return OrderResponse(
        order_id=payment.order_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
    )


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Mock payment-gateway webhook (HMAC-signed, idempotent)",
)
def payment_webhook(payload: WebhookRequest, db: Session = Depends(get_db)) -> WebhookResponse:
    payment, ticket = process_webhook(
        db, order_id=payload.order_id, status=payload.status, signature=payload.signature
    )
    return WebhookResponse(
        order_id=payment.order_id,
        payment_status=payment.status,
        ticket_status=ticket.status,
    )

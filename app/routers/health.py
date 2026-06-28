"""Liveness / health endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}

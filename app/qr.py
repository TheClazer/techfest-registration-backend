"""QR code generation for ticket tokens."""
from __future__ import annotations

import base64
import io

import qrcode


def make_qr_png_bytes(data: str) -> bytes:
    img = qrcode.make(data)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def make_qr_png_base64(data: str) -> str:
    return base64.b64encode(make_qr_png_bytes(data)).decode("ascii")

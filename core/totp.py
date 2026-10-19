"""Minimal RFC 6238 TOTP (time-based one-time passwords), no external deps.

Implements HMAC-SHA1, a 30-second time step, and 6 digits by default, matching
the parameters every authenticator app uses. Only the standard library is used
so the project keeps a small dependency surface.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
import time

DIGITS = 6
STEP_SECONDS = 30
WINDOW = 1  # accept the previous and next step to tolerate clock drift


class TotpError(ValueError):
    """Raised when a TOTP secret is not valid base32."""


def generate_secret(length: int = 20) -> str:
    """Returns a new base32 secret (default 160 bits, the RFC 4226 recommendation)."""
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    if not secret or not secret.strip():
        raise TotpError("empty TOTP secret")
    cleaned = secret.strip().replace(" ", "").upper()
    padding = "=" * (-len(cleaned) % 8)
    try:
        return base64.b32decode(cleaned + padding, casefold=True)
    except (binascii.Error, ValueError) as exc:
        raise TotpError(f"invalid base32 TOTP secret: {exc}") from exc


def _hotp(key: bytes, counter: int, digits: int = DIGITS) -> str:
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10**digits)).zfill(digits)


def now_code(secret: str, at: float | None = None, digits: int = DIGITS) -> str:
    """Returns the code valid for ``at`` (default: now)."""
    key = _normalize_secret(secret)
    counter = int((at if at is not None else time.time()) // STEP_SECONDS)
    return _hotp(key, counter, digits)


def verify(
    secret: str,
    code: str,
    at: float | None = None,
    digits: int = DIGITS,
    window: int = WINDOW,
) -> bool:
    """Constant-time check of ``code`` against ``secret`` within +/- ``window`` steps."""
    if not code:
        return False
    candidate = code.strip().replace(" ", "")
    if not candidate.isdigit() or len(candidate) != digits:
        return False
    try:
        key = _normalize_secret(secret)
    except TotpError:
        return False
    counter = int((at if at is not None else time.time()) // STEP_SECONDS)
    matched = False
    for offset in range(-window, window + 1):
        expected = _hotp(key, counter + offset, digits)
        # No early exit: keep the comparison constant-time across the window.
        matched |= hmac.compare_digest(expected, candidate)
    return matched

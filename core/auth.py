"""Authentication modes and session handling for the OmniAssist GUI server.

Three modes, selected by the launch flag (carried in ``OMNIASSIST_AUTH_MODE``):

``open``   (:8000) no credential required.
``totp``   (:8001) a 6-digit TOTP from a static secret in ``.env``.
``token``  (:8002) the GUI Omni bearer token (paste-to-detect in the UI).

Security rule for ``totp``: if no secret is configured the mode is *locked*, not
open. No code can ever be valid, so the UI stays on the 6-digit box forever.
Only the ``token`` and ``open`` modes fall back to open access when unset.
"""

from __future__ import annotations

import hmac
import os
import secrets
import time
from enum import Enum

from core.totp import verify as totp_verify

DEFAULT_PORTS = {"open": 8000, "totp": 8001, "token": 8002}
SESSION_TTL_SECONDS = 8 * 60 * 60
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


class AuthMode(str, Enum):
    OPEN = "open"
    TOTP = "totp"
    TOKEN = "token"

    @classmethod
    def from_env(cls, value: str | None = None) -> "AuthMode":
        raw = (value if value is not None else os.environ.get("OMNIASSIST_AUTH_MODE", "open"))
        try:
            return cls((raw or "open").strip().lower())
        except ValueError:
            return cls.OPEN

    @property
    def default_port(self) -> int:
        return DEFAULT_PORTS[self.value]


class AuthManager:
    """Holds the active mode, the issued sessions, and the failed-attempt throttle."""

    def __init__(
        self,
        mode: AuthMode = AuthMode.OPEN,
        api_token: str | None = None,
        totp_secret: str | None = None,
        ttl: int = SESSION_TTL_SECONDS,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        lockout: int = LOCKOUT_SECONDS,
    ):
        self.mode = mode
        self.api_token = api_token or None
        self.totp_secret = totp_secret or None
        self.ttl = ttl
        self.max_attempts = max_attempts
        self.lockout = lockout
        self._sessions: dict[str, float] = {}
        self._failures: dict[str, tuple[int, float]] = {}

    # -- mode helpers -----------------------------------------------------
    @property
    def requires_credential(self) -> bool:
        """True when a credential must be presented to reach the API."""
        if self.mode is AuthMode.OPEN:
            return False
        if self.mode is AuthMode.TOTP:
            # Locked even without a secret: the UI must never fall through.
            return True
        return bool(self.api_token)  # token mode falls back to open when unset

    @property
    def totp_configured(self) -> bool:
        return bool(self.totp_secret)

    def describe(self) -> dict:
        """Public, secret-free description for the UI (GET /api/auth)."""
        return {
            "mode": self.mode.value,
            "requires_credential": self.requires_credential,
            "totp_configured": self.totp_configured,
            "default_port": self.mode.default_port,
        }

    # -- throttling -------------------------------------------------------
    def is_locked_out(self, ip: str, now: float | None = None) -> bool:
        count, until = self._failures.get(ip, (0, 0.0))
        return count >= self.max_attempts and (now or time.time()) < until

    def _record_failure(self, ip: str, now: float | None = None) -> None:
        now = now or time.time()
        count, _ = self._failures.get(ip, (0, 0.0))
        count += 1
        self._failures[ip] = (count, now + self.lockout)

    def _clear_failures(self, ip: str) -> None:
        self._failures.pop(ip, None)

    # -- credential checks ------------------------------------------------
    def check_token(self, token: str | None) -> bool:
        if not self.api_token:
            return True
        return bool(token) and hmac.compare_digest(token, self.api_token)

    def check_totp(self, code: str | None) -> bool:
        if not self.totp_secret:
            return False  # locked: no secret means no valid code, ever
        return totp_verify(self.totp_secret, code or "")

    # -- sessions ---------------------------------------------------------
    def issue_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = time.time() + self.ttl
        self._prune()
        return token

    def is_valid_session(self, token: str | None) -> bool:
        if not token:
            return False
        expiry = self._sessions.get(token)
        if expiry is None:
            return False
        if expiry < time.time():
            self._sessions.pop(token, None)
            return False
        return True

    def revoke(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)

    def _prune(self) -> None:
        now = time.time()
        for token in [t for t, exp in self._sessions.items() if exp < now]:
            self._sessions.pop(token, None)


def build_manager_from_env() -> AuthManager:
    """Constructs the AuthManager from the process environment."""
    return AuthManager(
        mode=AuthMode.from_env(),
        api_token=os.environ.get("OMNIASSIST_API_TOKEN"),
        totp_secret=os.environ.get("OMNIASSIST_TOTP_SECRET"),
    )

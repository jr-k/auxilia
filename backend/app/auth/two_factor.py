"""TOTP and recovery-code primitives for account two-factor authentication."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from urllib.parse import quote
from uuid import UUID

import qrcode
from jose import JWTError, jwt

from app.auth.settings import auth_settings


TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
BACKUP_CODE_COUNT = 10


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def build_otpauth_uri(secret: str, email: str) -> str:
    issuer = "auxilia"
    label = quote(f"{issuer}:{email}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


def build_qr_code_data_url(uri: str) -> str:
    image = qrcode.make(uri)
    output = BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def _totp_at(secret: str, counter: int) -> str:
    padding = "=" * (-len(secret) % 8)
    key = base64.b32decode(secret + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, *, at: int | None = None) -> bool:
    normalized = code.replace(" ", "")
    if len(normalized) != TOTP_DIGITS or not normalized.isdigit():
        return False
    counter = (at if at is not None else int(time.time())) // TOTP_PERIOD_SECONDS
    return any(
        hmac.compare_digest(_totp_at(secret, counter + offset), normalized)
        for offset in (-1, 0, 1)
    )


def generate_backup_codes() -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return [
        f"{''.join(secrets.choice(alphabet) for _ in range(4))}-"
        f"{''.join(secrets.choice(alphabet) for _ in range(4))}"
        for _ in range(BACKUP_CODE_COUNT)
    ]


def hash_backup_code(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    return hmac.new(
        auth_settings.JWT_SECRET_KEY.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()


def find_backup_code(code: str, hashes: list[str]) -> int | None:
    candidate = hash_backup_code(code)
    for index, stored in enumerate(hashes):
        if hmac.compare_digest(candidate, stored):
            return index
    return None


def create_scoped_token(
    user_id: UUID,
    scope: str,
    *,
    secret: str | None = None,
    expires_minutes: int = 10,
) -> str:
    payload: dict[str, object] = {
        "sub": str(user_id),
        "scope": scope,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=expires_minutes),
    }
    if secret is not None:
        payload["secret"] = secret
    return jwt.encode(
        payload,
        auth_settings.JWT_SECRET_KEY,
        algorithm=auth_settings.JWT_ALGORITHM,
    )


def decode_scoped_token(token: str, scope: str) -> tuple[UUID, str | None] | None:
    try:
        payload = jwt.decode(
            token,
            auth_settings.JWT_SECRET_KEY,
            algorithms=[auth_settings.JWT_ALGORITHM],
        )
        if payload.get("scope") != scope:
            return None
        return UUID(payload["sub"]), payload.get("secret")
    except (JWTError, KeyError, TypeError, ValueError):
        return None

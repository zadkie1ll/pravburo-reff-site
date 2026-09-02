import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote

PERIOD_SECONDS = 30
DIGITS = 6


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded)
    digest = hmac.new(key, struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % 10**DIGITS
    return f"{code:0{DIGITS}d}"


def totp_now(secret: str, *, for_time: float | None = None) -> str:
    counter = int((for_time if for_time is not None else time.time()) // PERIOD_SECONDS)
    return _hotp(secret, counter)


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    code = code.strip()
    if len(code) != DIGITS or not code.isdigit():
        return False
    now = time.time()
    for offset in range(-window, window + 1):
        expected = totp_now(secret, for_time=now + offset * PERIOD_SECONDS)
        if hmac.compare_digest(expected, code):
            return True
    return False


def provisioning_uri(secret: str, email: str, issuer: str = "Правбюро") -> str:
    label = quote(f"{issuer}:{email}")
    query = (
        f"secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}"
        f"&period={PERIOD_SECONDS}"
    )
    return f"otpauth://totp/{label}?{query}"

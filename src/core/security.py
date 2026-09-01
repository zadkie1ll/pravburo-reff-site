import base64
import hashlib
import hmac
import os
import re
import secrets
import time

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def valid_email(value: str) -> bool:
    return len(value) <= 254 and EMAIL_RE.fullmatch(normalize_email(value)) is not None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return "$".join(
        (
            "pbkdf2_sha256",
            "260000",
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            base64.b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(token: str, code: str) -> str:
    return hashlib.sha256(f"{token}:{code}".encode()).hexdigest()


def csrf_token(session: dict) -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_csrf(session: dict, submitted: str) -> bool:
    expected = session.get("csrf_token", "")
    return bool(expected and submitted and hmac.compare_digest(expected, submitted))


def normalize_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Укажите корректный номер телефона")
    return f"+{digits}"


def masked_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if len(digits) < 4:
        return "***"
    return f"+{digits[0]} *** ***-{digits[-4:-2]}-{digits[-2:]}"


def verify_telegram_login(payload: dict[str, str], bot_token: str, max_age: int) -> bool:
    received_hash = payload.get("hash", "")
    try:
        age = time.time() - int(payload.get("auth_date", "0"))
    except ValueError:
        return False
    if not received_hash or age < -30 or age > max_age:
        return False
    check = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()) if key != "hash")
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_hash, expected)

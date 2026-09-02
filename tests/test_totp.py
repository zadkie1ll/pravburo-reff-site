import time

from src.core.totp import generate_secret, totp_now, verify_totp


def test_generate_secret_is_base32_and_reasonably_long() -> None:
    secret = generate_secret()
    assert len(secret) >= 16
    assert all(char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for char in secret)


def test_verify_totp_accepts_current_code() -> None:
    secret = generate_secret()
    assert verify_totp(secret, totp_now(secret)) is True


def test_verify_totp_rejects_wrong_code() -> None:
    secret = generate_secret()
    current = totp_now(secret)
    wrong = f"{(int(current) + 1) % 1_000_000:06d}"
    assert verify_totp(secret, wrong) is False


def test_verify_totp_rejects_malformed_code() -> None:
    secret = generate_secret()
    assert verify_totp(secret, "abc123") is False
    assert verify_totp(secret, "12345") is False
    assert verify_totp(secret, "") is False


def test_verify_totp_accepts_previous_time_step_within_window() -> None:
    secret = generate_secret()
    previous_step_code = totp_now(secret, for_time=time.time() - 30)
    assert verify_totp(secret, previous_step_code) is True


def test_verify_totp_rejects_code_outside_window() -> None:
    secret = generate_secret()
    far_past_code = totp_now(secret, for_time=time.time() - 300)
    assert verify_totp(secret, far_past_code) is False

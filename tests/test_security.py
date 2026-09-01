from src.core.security import (
    hash_password,
    masked_phone,
    normalize_phone,
    verify_password,
)


def test_password_hash_is_compatible_and_salted() -> None:
    first = hash_password("secret123")
    second = hash_password("secret123")

    assert first != second
    assert verify_password("secret123", first)
    assert not verify_password("wrong", first)


def test_russian_phone_variants_have_one_identity() -> None:
    assert normalize_phone("8 (999) 123-45-67") == "+79991234567"
    assert normalize_phone("+7 999 123 45 67") == "+79991234567"
    assert masked_phone("+79991234567") == "+7 *** ***-45-67"

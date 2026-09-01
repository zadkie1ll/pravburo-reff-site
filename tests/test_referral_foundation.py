from urllib.parse import parse_qs, urlparse

from pravburo_ref_common.models import Agent, ReferralApplication, Reward

from src.services.social_auth import yandex_authorize_url


def test_database_constraints_enforce_first_attribution_and_one_reward() -> None:
    assert ReferralApplication.__table__.c.phone_normalized.unique is None
    assert any(
        constraint.name == "uq_referral_application_phone"
        for constraint in ReferralApplication.__table__.constraints
    )
    assert any(
        constraint.name == "uq_rewards_deal_id" for constraint in Reward.__table__.constraints
    )
    assert Agent.__table__.schema == "referral"


def test_yandex_authorize_url_contains_state(monkeypatch) -> None:
    from src.services import social_auth

    settings = social_auth.get_settings()
    monkeypatch.setattr(settings, "yandex_client_id", "client-id")
    query = parse_qs(urlparse(yandex_authorize_url("state-value")).query)

    assert query["client_id"] == ["client-id"]
    assert query["state"] == ["state-value"]

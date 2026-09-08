from urllib.parse import parse_qs, urlparse

from pravburo_ref_common.models import Agent, ReferralApplication, Reward

from src.services.social_auth import yandex_authorize_url


def test_database_constraints_enforce_one_reward_per_deal() -> None:
    # phone_normalized is intentionally NOT unique anymore - client-agent
    # fixation expires after 180 days (see test_referral_fixation_expiry.py),
    # so the same phone can have more than one ReferralApplication over time.
    assert ReferralApplication.__table__.c.phone_normalized.unique is None
    assert not any(
        constraint.name == "uq_referral_application_phone"
        for constraint in ReferralApplication.__table__.constraints
    )
    assert any(
        index.name == "uq_rewards_deal_id_reward_type_agent_id"
        for index in Reward.__table__.indexes
    )
    assert Agent.__table__.schema == "referral"


def test_yandex_authorize_url_contains_state(monkeypatch) -> None:
    from src.services import social_auth

    settings = social_auth.get_settings()
    monkeypatch.setattr(settings, "yandex_client_id", "client-id")
    query = parse_qs(urlparse(yandex_authorize_url("state-value")).query)

    assert query["client_id"] == ["client-id"]
    assert query["state"] == ["state-value"]

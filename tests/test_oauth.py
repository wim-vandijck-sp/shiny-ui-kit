import time

import pytest

from auth.oauth_handler import OAuthConfig, OAuthHandler, TokenSet


@pytest.fixture
def config() -> OAuthConfig:
    return OAuthConfig(
        client_id="test_client",
        client_secret="test_secret",
        authorization_url="https://tenant.api.identitynow.com/oauth/authorize",
        token_url="https://tenant.api.identitynow.com/oauth/token",
        redirect_uri="http://localhost:8000/oauth/callback",
    )


@pytest.fixture
def handler(config: OAuthConfig) -> OAuthHandler:
    return OAuthHandler(config)


def test_generate_authorization_url_contains_client_id(handler: OAuthHandler) -> None:
    url, state = handler.generate_authorization_url()
    assert "test_client" in url
    assert state in url


def test_generate_authorization_url_returns_unique_states(
    handler: OAuthHandler,
) -> None:
    _, state1 = handler.generate_authorization_url()
    _, state2 = handler.generate_authorization_url()
    assert state1 != state2


def test_validate_state_valid(handler: OAuthHandler) -> None:
    _, state = handler.generate_authorization_url()
    assert handler.validate_state(state) is True


def test_validate_state_invalid(handler: OAuthHandler) -> None:
    assert handler.validate_state("not_a_real_state") is False


def test_validate_state_consumed(handler: OAuthHandler) -> None:
    _, state = handler.generate_authorization_url()
    handler.validate_state(state)
    assert handler.validate_state(state) is False


def test_token_set_expiry() -> None:
    token = TokenSet(
        access_token="tok",
        refresh_token=None,
        expires_at=time.time() - 10,
    )
    assert token.is_expired is True


def test_token_set_not_expired() -> None:
    token = TokenSet(
        access_token="tok",
        refresh_token=None,
        expires_at=time.time() + 3600,
    )
    assert token.is_expired is False


def test_token_set_from_response() -> None:
    data = {
        "access_token": "abc",
        "refresh_token": "def",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    token = TokenSet.from_response(data)
    assert token.access_token == "abc"
    assert token.refresh_token == "def"
    assert not token.is_expired


def test_csrf_token_unique() -> None:
    t1 = OAuthHandler.generate_csrf_token()
    t2 = OAuthHandler.generate_csrf_token()
    assert t1 != t2
    assert len(t1) == 64  # 32 bytes hex

import pytest

from config.settings import Settings


def test_settings_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAIL_BASE_URL", "https://test.api.identitynow.com")
    monkeypatch.setenv("SAIL_CLIENT_ID", "client_id")
    monkeypatch.setenv("SAIL_CLIENT_SECRET", "client_secret")
    monkeypatch.setenv("SESSION_SECRET", "session_secret")

    settings = Settings()
    assert settings.sail_base_url == "https://test.api.identitynow.com"
    assert settings.sail_client_id == "client_id"
    assert not settings.is_production


def test_oauth_authorization_url_uses_login_sailpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAIL_BASE_URL", "https://myorg.api.identitynow.com")
    monkeypatch.setenv("SAIL_CLIENT_ID", "cid")
    monkeypatch.setenv("SAIL_CLIENT_SECRET", "cs")
    monkeypatch.setenv("SESSION_SECRET", "ss")
    monkeypatch.delenv("OAUTH_AUTHORIZATION_URL", raising=False)

    settings = Settings()
    assert settings.oauth_authorization_url == "https://myorg.login.sailpoint.com/oauth/authorize"


def test_oauth_authorization_url_works_for_demo_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAIL_BASE_URL", "https://company19386-poc.api.identitynow-demo.com")
    monkeypatch.setenv("SAIL_CLIENT_ID", "cid")
    monkeypatch.setenv("SAIL_CLIENT_SECRET", "cs")
    monkeypatch.setenv("SESSION_SECRET", "ss")
    monkeypatch.delenv("OAUTH_AUTHORIZATION_URL", raising=False)

    settings = Settings()
    assert settings.oauth_authorization_url == "https://company19386-poc.login.sailpoint.com/oauth/authorize"


def test_oauth_authorization_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAIL_BASE_URL", "https://myorg.api.identitynow.com")
    monkeypatch.setenv("SAIL_CLIENT_ID", "cid")
    monkeypatch.setenv("SAIL_CLIENT_SECRET", "cs")
    monkeypatch.setenv("SESSION_SECRET", "ss")
    monkeypatch.setenv("OAUTH_AUTHORIZATION_URL", "https://custom.example.com/oauth/authorize")

    settings = Settings()
    assert settings.oauth_authorization_url == "https://custom.example.com/oauth/authorize"


def test_oauth_token_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAIL_BASE_URL", "https://myorg.api.identitynow.com")
    monkeypatch.setenv("SAIL_CLIENT_ID", "cid")
    monkeypatch.setenv("SAIL_CLIENT_SECRET", "cs")
    monkeypatch.setenv("SESSION_SECRET", "ss")

    settings = Settings()
    assert settings.oauth_token_url == "https://myorg.api.identitynow.com/oauth/token"


def test_settings_production_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAIL_BASE_URL", "https://test.api.identitynow.com")
    monkeypatch.setenv("SAIL_CLIENT_ID", "cid")
    monkeypatch.setenv("SAIL_CLIENT_SECRET", "cs")
    monkeypatch.setenv("SESSION_SECRET", "ss")
    monkeypatch.setenv("APP_ENV", "production")

    settings = Settings()
    assert settings.is_production is True

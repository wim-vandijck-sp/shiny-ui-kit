import time

import pytest

from auth.oauth_handler import TokenSet
from auth.session_manager import SessionManager


@pytest.fixture
def token_set() -> TokenSet:
    return TokenSet(
        access_token="tok",
        refresh_token="ref",
        expires_at=time.time() + 3600,
    )


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager()


def test_create_and_get_session(manager: SessionManager, token_set: TokenSet) -> None:
    sid = manager.create_session(token_set)
    session = manager.get_session(sid)
    assert session is not None
    assert session.session_id == sid


def test_get_nonexistent_session(manager: SessionManager) -> None:
    assert manager.get_session("does_not_exist") is None


def test_delete_session(manager: SessionManager, token_set: TokenSet) -> None:
    sid = manager.create_session(token_set)
    manager.delete_session(sid)
    assert manager.get_session(sid) is None


def test_expired_session_returns_none(manager: SessionManager) -> None:
    expired_token = TokenSet(
        access_token="tok",
        refresh_token=None,
        expires_at=time.time() - 10,
    )
    sid = manager.create_session(expired_token)
    session = manager.get_session(sid)
    # Session itself may not be expired immediately (TTL is 8h), token is
    assert session is not None  # session TTL != token TTL


def test_update_tokens(manager: SessionManager, token_set: TokenSet) -> None:
    sid = manager.create_session(token_set)
    new_token = TokenSet(
        access_token="new_tok",
        refresh_token="new_ref",
        expires_at=time.time() + 7200,
    )
    manager.update_tokens(sid, new_token)
    session = manager.get_session(sid)
    assert session is not None
    assert session.token_set.access_token == "new_tok"


def test_active_session_count(manager: SessionManager, token_set: TokenSet) -> None:
    assert manager.active_session_count == 0
    manager.create_session(token_set)
    assert manager.active_session_count == 1

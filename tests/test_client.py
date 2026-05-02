"""Tests for isc/client.py and isc/oauth_client.py."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from auth.oauth_handler import TokenSet
from auth.session_manager import Session
from isc.client import SailPointClient, SailPointError
from isc.oauth_client import _client_cache, _lock, evict_client, get_client_for_session


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_token(expired: bool = False) -> TokenSet:
    return TokenSet(
        access_token="tok-fresh" if not expired else "tok-expired",
        refresh_token="rtok",
        expires_at=time.time() + (3600 if not expired else -100),
    )


def _make_session(session_id: str = "sess-1", expired: bool = False) -> Session:
    return Session(session_id=session_id, token_set=_make_token(expired=expired))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate the module-level client cache between every test."""
    with _lock:
        for c in list(_client_cache.values()):
            c.close()
        _client_cache.clear()
    yield
    with _lock:
        for c in list(_client_cache.values()):
            c.close()
        _client_cache.clear()


@pytest.fixture
def mock_sdk():
    """Patch the three SDK constructors used by SailPointClient.__init__."""
    with (
        patch("isc.client.ConfigurationParams") as mock_params_cls,
        patch("isc.client.Configuration") as mock_cfg_cls,
        patch("isc.client.ApiClient") as mock_api_client_cls,
    ):
        mock_params = MagicMock()
        mock_params_cls.return_value = mock_params
        yield {
            "params_cls": mock_params_cls,
            "params": mock_params,
            "cfg_cls": mock_cfg_cls,
            "api_client_cls": mock_api_client_cls,
            "api_client": mock_api_client_cls.return_value,
        }


@pytest.fixture
def client(mock_sdk) -> SailPointClient:
    return SailPointClient(
        base_url="https://example.api.identitynow.com",
        access_token="tok-abc",
    )


@pytest.fixture
def mock_settings():
    with patch(
        "isc.oauth_client.get_settings",
        return_value=MagicMock(sail_base_url="https://example.api.identitynow.com"),
    ):
        yield


# ---------------------------------------------------------------------------
# SailPointClient — construction
# ---------------------------------------------------------------------------


class TestSailPointClientInit:
    def test_stores_access_token(self, mock_sdk):
        c = SailPointClient("https://example.com", "my-token")
        assert c.access_token == "my-token"

    def test_sets_base_url_on_params(self, mock_sdk):
        SailPointClient("https://example.com", "my-token")
        assert mock_sdk["params"].base_url == "https://example.com"

    def test_sets_access_token_on_params(self, mock_sdk):
        SailPointClient("https://example.com", "my-token")
        assert mock_sdk["params"].access_token == "my-token"

    def test_passes_configuration_to_api_client(self, mock_sdk):
        SailPointClient("https://example.com", "tok")
        mock_sdk["api_client_cls"].assert_called_once_with(
            mock_sdk["cfg_cls"].return_value
        )


# ---------------------------------------------------------------------------
# SailPointClient — API methods
# ---------------------------------------------------------------------------


class TestListIdentities:
    def test_calls_sdk_with_kwargs(self, client, mock_sdk):
        with patch("isc.client.IdentitiesApi") as mock_api_cls:
            mock_api_cls.return_value.list_identities.return_value = ["id1"]
            result = client.list_identities(limit=50, offset=10, filters='name eq "Alice"')

        mock_api_cls.return_value.list_identities.assert_called_once_with(
            limit=50, offset=10, filters='name eq "Alice"', sorters=None
        )
        assert result == ["id1"]

    def test_defaults(self, client, mock_sdk):
        with patch("isc.client.IdentitiesApi") as mock_api_cls:
            mock_api_cls.return_value.list_identities.return_value = []
            client.list_identities()

        _, kwargs = mock_api_cls.return_value.list_identities.call_args
        assert kwargs["limit"] == 250
        assert kwargs["offset"] == 0


class TestGetIdentity:
    def test_passes_id_kwarg(self, client, mock_sdk):
        with patch("isc.client.IdentitiesApi") as mock_api_cls:
            mock_api_cls.return_value.get_identity.return_value = "identity-obj"
            result = client.get_identity("abc-123")

        mock_api_cls.return_value.get_identity.assert_called_once_with(id="abc-123")
        assert result == "identity-obj"


class TestSearchIdentities:
    def test_delegates_to_search_post(self, client, mock_sdk):
        with patch.object(client, "search_post", return_value=["r"]) as mock_sp:
            result = client.search_identities("Alice", limit=30)

        mock_sp.assert_called_once_with(
            indices=["identities"], query="Alice", limit=30
        )
        assert result == ["r"]


class TestListAccounts:
    def test_calls_sdk_with_kwargs(self, client, mock_sdk):
        with patch("isc.client.AccountsApi") as mock_api_cls:
            mock_api_cls.return_value.list_accounts.return_value = ["acct"]
            result = client.list_accounts(limit=100, filters='sourceId eq "x"')

        mock_api_cls.return_value.list_accounts.assert_called_once_with(
            limit=100, offset=0, filters='sourceId eq "x"', sorters=None
        )
        assert result == ["acct"]


class TestSearchPost:
    def test_calls_sdk_and_returns_results(self, client, mock_sdk):
        with (
            patch("isc.client.SearchApi") as mock_api_cls,
            patch("isc.client.Search"),
            patch("isc.client.Query"),
        ):
            mock_api_cls.return_value.search_post.return_value = ["r1", "r2"]
            result = client.search_post(["identities", "accounts"], "Alice", limit=50)

        mock_api_cls.return_value.search_post.assert_called_once()
        assert result == ["r1", "r2"]

    def test_passes_offset(self, client, mock_sdk):
        with (
            patch("isc.client.SearchApi") as mock_api_cls,
            patch("isc.client.Search"),
            patch("isc.client.Query"),
        ):
            mock_api_cls.return_value.search_post.return_value = []
            client.search_post(["identities"], "q", offset=100)

        _, kwargs = mock_api_cls.return_value.search_post.call_args
        assert kwargs["offset"] == 100


# ---------------------------------------------------------------------------
# SailPointClient — error handling via _call()
# ---------------------------------------------------------------------------


class TestCallErrorHandling:
    def test_api_exception_becomes_sailpoint_error(self, client, mock_sdk):
        from sailpoint.v2025.exceptions import ApiException

        exc = ApiException(status=403, reason="Forbidden")
        with patch("isc.client.IdentitiesApi") as mock_api_cls:
            mock_api_cls.return_value.list_identities.side_effect = exc
            with pytest.raises(SailPointError) as exc_info:
                client.list_identities()

        err = exc_info.value
        assert err.status == 403
        assert err.reason == "Forbidden"

    def test_sailpoint_error_is_chained(self, client, mock_sdk):
        from sailpoint.v2025.exceptions import ApiException

        exc = ApiException(status=500, reason="Server Error")
        with patch("isc.client.IdentitiesApi") as mock_api_cls:
            mock_api_cls.return_value.list_identities.side_effect = exc
            with pytest.raises(SailPointError) as exc_info:
                client.list_identities()

        assert exc_info.value.__cause__ is exc

    def test_non_api_exceptions_propagate_unchanged(self, client, mock_sdk):
        with patch("isc.client.IdentitiesApi") as mock_api_cls:
            mock_api_cls.return_value.list_identities.side_effect = ValueError("boom")
            with pytest.raises(ValueError, match="boom"):
                client.list_identities()

    def test_sailpoint_error_str_includes_status_and_reason(self):
        err = SailPointError(404, "Not Found")
        assert "404" in str(err)
        assert "Not Found" in str(err)


# ---------------------------------------------------------------------------
# SailPointClient — lifecycle
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_calls_exit_on_api_client(self, client, mock_sdk):
        client.close()
        mock_sdk["api_client"].__exit__.assert_called_once_with(None, None, None)


# ---------------------------------------------------------------------------
# oauth_client — get_client_for_session
# ---------------------------------------------------------------------------


class TestGetClientForSession:
    def test_returns_new_client_for_fresh_session(self, mock_settings):
        sess = _make_session()
        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            mock_cls.return_value = MagicMock(access_token=sess.token_set.access_token)
            client = get_client_for_session(sess)

        assert client is mock_cls.return_value
        mock_cls.assert_called_once()

    def test_caches_client_on_second_call(self, mock_settings):
        sess = _make_session()
        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            mock_cls.return_value = MagicMock(access_token=sess.token_set.access_token)
            c1 = get_client_for_session(sess)
            c2 = get_client_for_session(sess)

        assert c1 is c2
        assert mock_cls.call_count == 1

    def test_rebuilds_when_access_token_changes(self, mock_settings):
        sess = _make_session()
        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            old_client = MagicMock(access_token="tok-fresh")
            new_client = MagicMock(access_token="tok-refreshed")
            mock_cls.side_effect = [old_client, new_client]

            get_client_for_session(sess)

            # Simulate token refresh updating the session
            sess.token_set = _make_token()
            sess.token_set.access_token = "tok-refreshed"

            c2 = get_client_for_session(sess)

        assert c2 is new_client
        assert mock_cls.call_count == 2

    def test_evicts_old_client_on_rebuild(self, mock_settings):
        sess = _make_session()
        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            old_client = MagicMock(access_token="tok-fresh")
            new_client = MagicMock(access_token="tok-new")
            mock_cls.side_effect = [old_client, new_client]

            get_client_for_session(sess)
            sess.token_set.access_token = "tok-new"
            get_client_for_session(sess)

        old_client.close.assert_called_once()

    def test_refreshes_token_when_expired_and_handler_supplied(self, mock_settings):
        sess = _make_session(expired=True)
        original_token = sess.token_set  # capture before _refresh_token mutates it
        handler = MagicMock()
        refreshed_token = _make_token()
        handler.refresh_token.return_value = refreshed_token

        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            mock_cls.return_value = MagicMock(access_token=refreshed_token.access_token)
            get_client_for_session(sess, oauth_handler=handler)

        handler.refresh_token.assert_called_once_with(original_token)
        assert sess.token_set is refreshed_token

    def test_raises_when_token_expired_and_no_handler(self, mock_settings):
        sess = _make_session(expired=True)
        with pytest.raises(RuntimeError, match="oauth_handler"):
            get_client_for_session(sess, oauth_handler=None)

    def test_raises_when_refresh_fails(self, mock_settings):
        sess = _make_session(expired=True)
        handler = MagicMock()
        handler.refresh_token.side_effect = Exception("network error")

        with pytest.raises(Exception, match="network error"):
            get_client_for_session(sess, oauth_handler=handler)


# ---------------------------------------------------------------------------
# oauth_client — evict_client
# ---------------------------------------------------------------------------


class TestEvictClient:
    def test_closes_cached_client(self, mock_settings):
        sess = _make_session()
        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            mock_client = MagicMock(access_token=sess.token_set.access_token)
            mock_cls.return_value = mock_client
            get_client_for_session(sess)

        evict_client(sess.session_id)
        mock_client.close.assert_called_once()

    def test_removes_from_cache(self, mock_settings):
        sess = _make_session()
        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            mock_cls.return_value = MagicMock(access_token=sess.token_set.access_token)
            get_client_for_session(sess)

        evict_client(sess.session_id)
        assert sess.session_id not in _client_cache

    def test_evict_nonexistent_is_silent(self):
        evict_client("no-such-session")  # must not raise


# ---------------------------------------------------------------------------
# oauth_client — thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_calls_produce_one_client(self, mock_settings):
        sess = _make_session()
        results: list[SailPointClient] = []

        with patch("isc.oauth_client.SailPointClient") as mock_cls:
            shared = MagicMock(access_token=sess.token_set.access_token)
            mock_cls.return_value = shared

            def call():
                results.append(get_client_for_session(sess))

            threads = [threading.Thread(target=call) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # All threads receive the same cached instance
        assert all(c is shared for c in results)
        assert mock_cls.call_count == 1

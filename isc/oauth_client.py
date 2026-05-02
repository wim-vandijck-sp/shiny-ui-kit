import logging
import threading
from typing import TYPE_CHECKING

from auth.session_manager import Session
from config.settings import get_settings
from isc.client import SailPointClient

if TYPE_CHECKING:
    from auth.oauth_handler import OAuthHandler

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client_cache: dict[str, SailPointClient] = {}


def get_client_for_session(
    session: Session,
    oauth_handler: "OAuthHandler | None" = None,
) -> SailPointClient:
    """Return a SailPointClient for *session*, creating or refreshing as needed.

    A cached client is reused only when its stored access token still matches
    the session's current token.  If the token has been refreshed elsewhere
    (via SessionManager.update_tokens), the cached client is evicted and a new
    one is built with the fresh token.

    If the token is expired and *oauth_handler* is supplied, the token is
    refreshed in-place before the new client is built.
    """
    with _lock:
        cached = _client_cache.get(session.session_id)
        token_unchanged = (
            cached is not None
            and cached.access_token == session.token_set.access_token
        )
        if token_unchanged and not session.token_set.is_expired:
            return cached

        _evict_locked(session.session_id)

        if session.token_set.is_expired:
            if oauth_handler is None:
                raise RuntimeError(
                    "Session token is expired and no oauth_handler was supplied "
                    "to refresh it."
                )
            _refresh_token(session, oauth_handler)

        settings = get_settings()
        client = SailPointClient(
            base_url=settings.sail_base_url,
            access_token=session.token_set.access_token,
        )
        _client_cache[session.session_id] = client
        return client


def evict_client(session_id: str) -> None:
    with _lock:
        _evict_locked(session_id)


def _evict_locked(session_id: str) -> None:
    """Close and remove the cached client for *session_id* (caller holds _lock)."""
    client = _client_cache.pop(session_id, None)
    if client is not None:
        client.close()


def _refresh_token(session: Session, oauth_handler: "OAuthHandler") -> None:
    """Refresh the session's token set in-place (caller holds _lock)."""
    try:
        new_token_set = oauth_handler.refresh_token(session.token_set)
        session.token_set = new_token_set
        session.touch()
        logger.info("Token refreshed for session %s", session.session_id)
    except Exception as exc:
        logger.warning("Token refresh failed for session %s: %s", session.session_id, exc)
        raise

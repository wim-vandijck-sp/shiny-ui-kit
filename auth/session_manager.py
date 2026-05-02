import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from auth.oauth_handler import TokenSet

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_id: str
    token_set: TokenSet
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl: float = 3600 * 8  # 8-hour session max

    @property
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl

    def touch(self) -> None:
        self.last_accessed = time.time()

    @property
    def user_info(self) -> dict[str, Any]:
        return self.token_set.user_info


class SessionManager:
    def __init__(self, cleanup_interval: float = 300) -> None:
        self._sessions: dict[str, Session] = {}
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    def create_session(self, token_set: TokenSet) -> str:
        self._maybe_cleanup()
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = Session(session_id=session_id, token_set=token_set)
        logger.debug(
            "Session created: %s... (user=%s)",
            session_id[:8],
            token_set.user_info.get("sub", "?"),
        )
        return session_id

    def get_session(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            logger.debug("Session not found: %s...", session_id[:8])
            return None
        if session.is_expired:
            logger.debug("Session expired: %s...", session_id[:8])
            self.delete_session(session_id)
            return None
        session.touch()
        ttl_remaining = int(session.created_at + session.ttl - time.time())
        logger.debug("Session accessed: %s... (ttl=%ds)", session_id[:8], ttl_remaining)
        return session

    def update_tokens(self, session_id: str, token_set: TokenSet) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.token_set = token_set
            session.touch()
            logger.debug("Tokens updated for session: %s...", session_id[:8])

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        logger.debug("Session deleted: %s...", session_id[:8])

    def _maybe_cleanup(self) -> None:
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now

    def _cleanup(self) -> None:
        expired = [sid for sid, s in self._sessions.items() if s.is_expired]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.debug("Cleaned up %d expired session(s)", len(expired))

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

import hashlib
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from jose import jwt
from requests_oauthlib import OAuth2Session

logger = logging.getLogger(__name__)


@dataclass
class OAuthConfig:
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    redirect_uri: str
    info_url: str | None = None
    scopes: list[str] = field(default_factory=lambda: ["sp:scopes:all"])

    @property
    def scope_string(self) -> str:
        return " ".join(self.scopes)


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float
    token_type: str = "Bearer"
    user_info: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 60s buffer

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "TokenSet":
        expires_in = data.get("expires_in", 3600)
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=time.time() + expires_in,
            token_type=data.get("token_type", "Bearer"),
        )


_HTTP_SCHEME = "http://"
_oauth_info_cache: dict[str, Any] | None = None


def fetch_oauth_info(info_url: str) -> dict[str, Any]:
    global _oauth_info_cache
    if _oauth_info_cache is None:
        resp = requests.get(info_url, timeout=10)
        resp.raise_for_status()
        _oauth_info_cache = resp.json()
    return _oauth_info_cache


class OAuthHandler:
    def __init__(self, config: OAuthConfig) -> None:
        self.config = config
        self._state_store: dict[str, float] = {}

    def generate_authorization_url(self) -> tuple[str, str]:
        # Allow HTTP redirect URIs in development (oauthlib rejects non-HTTPS by default)
        if self.config.redirect_uri.startswith(_HTTP_SCHEME):
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        oauth = OAuth2Session(
            client_id=self.config.client_id,
            redirect_uri=self.config.redirect_uri,
            scope=self.config.scopes,
        )
        auth_url, state = oauth.authorization_url(self.config.authorization_url)
        self._state_store[state] = time.time() + 600  # 10-minute expiry
        logger.debug("Authorization URL generated, state=%s...", state[:8])
        return auth_url, state

    def validate_state(self, state: str) -> bool:
        expiry = self._state_store.pop(state, None)
        if expiry is None:
            logger.debug("State validation failed — unknown state %s...", state[:8])
            return False
        valid = time.time() < expiry
        logger.debug("State validation %s for %s...", "OK" if valid else "EXPIRED", state[:8])
        return valid

    def _purge_expired_states(self) -> None:
        now = time.time()
        self._state_store = {
            s: exp for s, exp in self._state_store.items() if exp > now
        }

    def exchange_code(self, code: str) -> TokenSet:
        logger.debug("Exchanging authorization code for token")
        if self.config.redirect_uri.startswith(_HTTP_SCHEME):
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        oauth = OAuth2Session(
            client_id=self.config.client_id,
            redirect_uri=self.config.redirect_uri,
        )
        # SailPoint requires token params as query string, not form body
        token_data = oauth.fetch_token(
            token_url=self.config.token_url,
            code=code,
            client_secret=self.config.client_secret,
            force_querystring=True,
        )
        token_set = TokenSet.from_response(token_data)
        token_set.user_info = self._parse_jwt_claims(token_set.access_token)
        expires_in = int(token_set.expires_at - time.time())
        logger.debug(
            "Token exchange successful — user=%s, expires_in=%ds",
            token_set.user_info.get("sub", "?"),
            expires_in,
        )
        return token_set

    def refresh_token(self, token_set: TokenSet) -> TokenSet:
        if not token_set.refresh_token:
            raise ValueError("No refresh token available")

        logger.debug("Refreshing access token for user=%s", token_set.user_info.get("sub", "?"))
        if self.config.redirect_uri.startswith(_HTTP_SCHEME):
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        oauth = OAuth2Session(client_id=self.config.client_id)
        token_data = oauth.refresh_token(
            token_url=self.config.token_url,
            refresh_token=token_set.refresh_token,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            force_querystring=True,
        )
        new_token_set = TokenSet.from_response(token_data)
        new_token_set.user_info = self._parse_jwt_claims(new_token_set.access_token)
        logger.debug(
            "Token refresh successful — expires_in=%ds",
            int(new_token_set.expires_at - time.time()),
        )
        return new_token_set

    def _parse_jwt_claims(self, token: str) -> dict[str, Any]:
        try:
            return jwt.get_unverified_claims(token)
        except Exception:
            logger.debug("Could not parse JWT claims")
            return {}

    @staticmethod
    def generate_csrf_token() -> str:
        return secrets.token_hex(32)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

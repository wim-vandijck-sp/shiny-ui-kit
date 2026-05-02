import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    sail_base_url: str = field(default_factory=lambda: os.environ["SAIL_BASE_URL"])
    sail_client_id: str = field(default_factory=lambda: os.environ["SAIL_CLIENT_ID"])
    sail_client_secret: str = field(
        default_factory=lambda: os.environ["SAIL_CLIENT_SECRET"]
    )
    oauth_redirect_uri: str = field(
        default_factory=lambda: os.getenv(
            "OAUTH_REDIRECT_URI", "http://localhost:8000/oauth/callback"
        )
    )
    # Optional explicit override; defaults to [org].login.sailpoint.com
    oauth_authorization_url_override: str | None = field(
        default_factory=lambda: os.getenv("OAUTH_AUTHORIZATION_URL")
    )
    session_secret: str = field(default_factory=lambda: os.environ["SESSION_SECRET"])
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    oauth_info_url: str = field(default="", init=False)
    redis_url: str | None = field(default_factory=lambda: os.getenv("REDIS_URL"))

    def __post_init__(self) -> None:
        env_val = os.getenv("OAUTH_INFO_URL")
        self.oauth_info_url = env_val or f"{self.sail_base_url.rstrip('/')}/oauth/info"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def oauth_authorization_url(self) -> str:
        if self.oauth_authorization_url_override:
            return self.oauth_authorization_url_override
        # Authorization always goes through login.sailpoint.com regardless of
        # whether the tenant is production or demo (identitynow-demo.com etc.).
        # Extract the org prefix (first hostname segment) from SAIL_BASE_URL.
        hostname = urlparse(self.sail_base_url).hostname or ""
        org = hostname.split(".")[0]
        return f"https://{org}.login.sailpoint.com/oauth/authorize"

    @property
    def oauth_token_url(self) -> str:
        return f"{self.sail_base_url.rstrip('/')}/oauth/token"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

import logging
from typing import Any

from sailpoint.configuration import Configuration, ConfigurationParams
from sailpoint.v2025.api.accounts_api import AccountsApi
from sailpoint.v2025.api.identities_api import IdentitiesApi
from sailpoint.v2025.api.search_api import SearchApi
from sailpoint.v2025.api_client import ApiClient
from sailpoint.v2025.exceptions import ApiException
from sailpoint.v2025.models.account import Account
from sailpoint.v2025.models.identity import Identity
from sailpoint.v2025.models.query import Query
from sailpoint.v2025.models.search import Search

logger = logging.getLogger(__name__)


def _fmt_kwargs(kw: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in kw.items() if v is not None)


class SailPointError(Exception):
    """Raised when the SailPoint API returns an error response."""

    def __init__(self, status: int | None, reason: str | None, body: str | None = None) -> None:
        self.status = status
        self.reason = reason
        self.body = body
        super().__init__(f"SailPoint API error {status}: {reason}")


class SailPointClient:
    def __init__(self, base_url: str, access_token: str) -> None:
        self.access_token = access_token
        params = ConfigurationParams()
        params.base_url = base_url
        params.access_token = access_token
        self._api_client = ApiClient(Configuration(params))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call(self, fn, *args, **kwargs):
        """Execute an SDK call and convert ApiException → SailPointError."""
        import time as _time
        fn_name = getattr(fn, "__name__", repr(fn))
        logger.debug("API call: %s(%s)", fn_name, _fmt_kwargs(kwargs))
        t0 = _time.monotonic()
        try:
            result = fn(*args, **kwargs)
            elapsed = (_time.monotonic() - t0) * 1000
            logger.debug("API call %s completed in %.0fms", fn_name, elapsed)
            return result
        except ApiException as exc:
            logger.warning("SailPoint API error %s: %s — %s", exc.status, exc.reason, exc.body)
            raise SailPointError(exc.status, exc.reason, exc.body) from exc

    # ------------------------------------------------------------------
    # Identities
    # ------------------------------------------------------------------

    def list_identities(
        self,
        limit: int = 250,
        offset: int = 0,
        filters: str | None = None,
        sorters: str | None = None,
    ) -> list[Identity]:
        api = IdentitiesApi(self._api_client)
        return self._call(
            api.list_identities,
            limit=limit,
            offset=offset,
            filters=filters,
            sorters=sorters,
        )

    def get_identity(self, identity_id: str) -> Identity:
        api = IdentitiesApi(self._api_client)
        return self._call(api.get_identity, id=identity_id)

    def search_identities(self, query: str, limit: int = 250) -> list[Any]:
        return self.search_post(indices=["identities"], query=query, limit=limit)

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def list_accounts(
        self,
        limit: int = 250,
        offset: int = 0,
        filters: str | None = None,
        sorters: str | None = None,
    ) -> list[Account]:
        api = AccountsApi(self._api_client)
        return self._call(
            api.list_accounts,
            limit=limit,
            offset=offset,
            filters=filters,
            sorters=sorters,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_post(
        self,
        indices: list[str],
        query: str,
        limit: int = 250,
        offset: int = 0,
    ) -> list[Any]:
        search = Search(indices=indices, query=Query(query=query))
        api = SearchApi(self._api_client)
        return self._call(api.search_post, search=search, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Branding
    # ------------------------------------------------------------------

    def get_branding(self) -> dict:
        """Fetch tenant branding configuration (colors and logo)."""
        from sailpoint.v2025.api.branding_api import BrandingApi

        api = BrandingApi(self._api_client)
        try:
            items = self._call(api.get_branding_list)
            if not items:
                return {}
            item = items[0]
            result: dict = {}
            for field in ("product_name", "action_button_color", "active_link_color", "navigation_color"):
                val = getattr(item, field, None)
                if val:
                    result[field] = str(val).lstrip("#")
            logo = getattr(item, "file_standard", None)
            if logo is not None:
                if isinstance(logo, (bytes, bytearray)):
                    import base64 as _b64
                    result["logo_data_url"] = "data:image/png;base64," + _b64.b64encode(bytes(logo)).decode()
                elif isinstance(logo, str) and logo.startswith(("http", "data:")):
                    result["logo_data_url"] = logo
            return result
        except Exception as e:
            logger.debug("Could not fetch branding: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._api_client.__exit__(None, None, None)

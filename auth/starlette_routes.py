import asyncio
import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from auth.oauth_handler import OAuthConfig, OAuthHandler, fetch_oauth_info
from auth.session_manager import SessionManager
from config.settings import get_settings
from isc.oauth_client import evict_client

logger = logging.getLogger(__name__)

_oauth_handler: OAuthHandler | None = None
_session_manager: SessionManager | None = None


def _get_oauth_handler() -> OAuthHandler:
    global _oauth_handler
    if _oauth_handler is None:
        settings = get_settings()
        info = fetch_oauth_info(settings.oauth_info_url)
        config = OAuthConfig(
            client_id=settings.sail_client_id,
            client_secret=settings.sail_client_secret,
            authorization_url=info["authorizeEndpoint"],
            token_url=info["tokenEndpoint"],
            redirect_uri=settings.oauth_redirect_uri,
            info_url=settings.oauth_info_url,
        )
        _oauth_handler = OAuthHandler(config)
    return _oauth_handler


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def login(request: Request) -> RedirectResponse:
    handler = _get_oauth_handler()
    auth_url, state = await asyncio.to_thread(handler.generate_authorization_url)
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        "oauth_state", state, httponly=True, samesite="lax", max_age=600
    )
    return response


async def oauth_callback(request: Request) -> RedirectResponse:
    handler = _get_oauth_handler()
    sessions = get_session_manager()

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.warning("OAuth error: %s", error)
        return RedirectResponse(url="/?error=oauth_failed", status_code=302)

    stored_state = request.cookies.get("oauth_state")
    if not state or state != stored_state or not handler.validate_state(state):
        return RedirectResponse(url="/?error=invalid_state", status_code=302)

    try:
        token_set = await asyncio.to_thread(handler.exchange_code, code)
    except Exception:
        logger.exception("Token exchange failed")
        return RedirectResponse(url="/?error=token_exchange_failed", status_code=302)

    session_id = sessions.create_session(token_set)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_production,
        max_age=3600 * 8,
    )
    response.delete_cookie("oauth_state")
    return response


async def auth_status(request: Request) -> JSONResponse:
    session_id = request.cookies.get("session_id")
    if not session_id:
        return JSONResponse({"authenticated": False})

    sessions = get_session_manager()
    session = sessions.get_session(session_id)
    if not session:
        return JSONResponse({"authenticated": False})

    return JSONResponse(
        {
            "authenticated": True,
            "user": session.user_info,
            "token_expires_at": session.token_set.expires_at,
        }
    )


async def logout(request: Request) -> JSONResponse:
    session_id = request.cookies.get("session_id")
    if session_id:
        get_session_manager().delete_session(session_id)
        evict_client(session_id)

    response = JSONResponse({"success": True})
    response.delete_cookie("session_id")
    return response


auth_router = Starlette(
    routes=[
        Route("/login", login),
        Route("/logout", logout, methods=["POST"]),
        Route("/status", auth_status),
        Route("/callback", oauth_callback, name="oauth_callback"),
    ]
)

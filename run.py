import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

from app import app as shiny_app
from auth.starlette_routes import _get_oauth_handler, auth_router, oauth_callback
from config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: ASGIApp) -> AsyncGenerator[None, None]:
    try:
        _get_oauth_handler()
        logger.info("OAuth handler initialized")
    except Exception:
        logger.exception("Failed to initialize OAuth handler at startup")
        raise
    yield


def create_app() -> Starlette:
    routes = [
        Route("/oauth/callback", oauth_callback),  # matches default OAUTH_REDIRECT_URI
        Mount("/api/auth", app=auth_router),
        Mount("/", app=shiny_app),
    ]
    return Starlette(routes=routes, lifespan=_lifespan)


def main() -> None:
    uvicorn.run(
        "run:create_app",
        host="0.0.0.0",
        port=8000,
        factory=True,
        reload=True,
    )


if __name__ == "__main__":
    main()

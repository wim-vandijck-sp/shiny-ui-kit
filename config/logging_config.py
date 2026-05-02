import logging

# Loggers that belong to this application
_APP_LOGGERS = ["isc", "auth", "components", "app", "run"]


def setup_logging() -> None:
    """Configure root handler once at process startup."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)-30s %(message)s",
        datefmt="%H:%M:%S",
    )


def set_debug_logging(enabled: bool) -> None:
    """Toggle DEBUG level on all application loggers."""
    level = logging.DEBUG if enabled else logging.INFO
    for name in _APP_LOGGERS:
        logging.getLogger(name).setLevel(level)

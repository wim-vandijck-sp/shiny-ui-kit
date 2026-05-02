from shiny import ui as shiny_ui

# Application-wide title — change here to rename everywhere.
APP_TITLE = "Shiny ISC UI Kit"

# SailPoint brand constants (used across the app)
SP_NAV_BG = "#011533"
SP_PRIMARY = "#0033a1"


def sailpoint_theme() -> shiny_ui.Theme:
    """Bootstrap theme stub — actual colors applied via CSS variables in styles.css."""
    return shiny_ui.Theme("bootstrap")

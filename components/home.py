import time
from typing import TYPE_CHECKING, Callable

from shiny import module, reactive, render, ui

from ui.theme import APP_TITLE

if TYPE_CHECKING:
    from auth.session_manager import Session
    from components.registry import ComponentRegistry
    from isc.client import SailPointClient

_NAV_JS = "document.querySelector('.nav-link[data-value=\"{label}\"]')?.click()"

_STAT_ICONS: dict[str, str] = {
    "Identities": "fa-users",
    "Accounts": "fa-shield-halved",
}

_COMP_ICONS: dict[str, str] = {
    "Identities": "fa-users",
    "Accounts": "fa-shield-halved",
    "Search": "fa-magnifying-glass",
}


# ---------------------------------------------------------------------------
# Pure rendering helpers
# ---------------------------------------------------------------------------


def _stat_card(title: str, value: str, color: str = "primary") -> ui.Tag:
    icon_cls = _STAT_ICONS.get(title, "fa-chart-bar")
    return ui.div(
        ui.div(
            ui.tags.i(class_=f"fa-solid {icon_cls} stat-card-icon text-{color}"),
            ui.tags.span(value, class_=f"display-6 fw-bold text-{color} d-block"),
            ui.p(title, class_="text-muted mb-0 small"),
            class_="card-body text-center py-3",
        ),
        class_="card shadow-sm h-100",
    )


def _shortcut_card(label: str, description: str) -> ui.Tag:
    icon_cls = _COMP_ICONS.get(label, "fa-grid")
    return ui.div(
        ui.tags.a(
            ui.div(
                ui.tags.i(class_=f"fa-solid {icon_cls} me-2 text-primary"),
                ui.tags.span(label, class_="fw-semibold"),
                ui.p(description, class_="text-muted small mb-0 mt-1"),
                class_="card-body py-3",
            ),
            href="#",
            onclick=_NAV_JS.format(label=label) + "; return false;",
            class_="text-decoration-none text-reset",
        ),
        class_="card shadow-sm h-100 card-hover",
    )


def _fetch_stats(c) -> dict[str, str]:
    ids = c.list_identities(limit=250)
    accts = c.list_accounts(limit=250)
    return {
        "identities": f"{len(ids)}+" if len(ids) == 250 else str(len(ids)),
        "accounts": f"{len(accts)}+" if len(accts) == 250 else str(len(accts)),
    }


def _build_user_card(sess) -> ui.Tag:
    info = sess.user_info
    name = info.get("name") or info.get("sub") or "Unknown"
    email = info.get("email", "")
    expires_in = max(0, int(sess.token_set.expires_at - time.time()))
    minutes, seconds = divmod(expires_in, 60)
    return ui.div(
        ui.div(
            ui.h6(
                ui.tags.i(class_="fa-solid fa-circle-user me-2 text-muted"),
                "Signed in as",
                class_="card-subtitle text-muted mb-1",
            ),
            ui.p(ui.strong(name), class_="mb-0"),
            ui.p(email, class_="text-muted small mb-1") if email else ui.div(),
            ui.p(
                ui.tags.i(class_="fa-regular fa-clock me-1 text-muted"),
                f"Token expires in {minutes}m {seconds}s",
                class_="text-muted small mb-0",
            ),
            class_="card-body py-3",
        ),
        class_="card shadow-sm mb-3",
        style="max-width:420px",
    )


def _build_stats_row(stats: dict[str, str]) -> ui.Tag:
    if not stats:
        return ui.p("Log in to see statistics.", class_="text-muted")
    return ui.div(
        ui.column(4, _stat_card("Identities", stats.get("identities", "—"), "primary")),
        ui.column(4, _stat_card("Accounts", stats.get("accounts", "—"), "success")),
        class_="row g-3 stats-grid",
    )


def _build_shortcuts_row(registry) -> ui.Tag:
    if registry is None:
        return ui.div()
    enabled = registry.get_enabled()
    if not enabled:
        return ui.p(
            ui.tags.i(class_="fa-solid fa-circle-info me-1"),
            "No components enabled. Visit Settings to enable some.",
            class_="text-muted",
        )
    cols = [ui.column(3, _shortcut_card(c.label, c.description)) for c in enabled]
    return ui.div(*cols, class_="row g-3 shortcuts-grid")


# ---------------------------------------------------------------------------
# Shiny module
# ---------------------------------------------------------------------------


@module.ui
def home_ui() -> ui.Tag:
    return ui.div(
        ui.h2(
            ui.tags.i(class_="fa-solid fa-house me-2 text-primary"),
            APP_TITLE,
            class_="mb-1",
        ),
        ui.p("Identity Security Cloud — self-service portal.", class_="text-muted mb-4"),
        ui.output_ui("user_card"),
        ui.h5(
            ui.tags.i(class_="fa-solid fa-chart-bar me-2"),
            "Quick Stats",
            class_="mt-4 mb-3",
        ),
        ui.output_ui("stats_row"),
        ui.h5(
            ui.tags.i(class_="fa-solid fa-grid me-2"),
            "Components",
            class_="mt-4 mb-3",
        ),
        ui.output_ui("shortcuts_row"),
    )


@module.server
def home_server(
    input,
    output,
    session,
    *,
    user_session: "Callable[[], Session | None]",
    client: "Callable[[], SailPointClient | None] | None" = None,
    registry: "ComponentRegistry | None" = None,
) -> None:
    @reactive.calc
    def _stats() -> dict[str, str]:
        if client is None:
            return {}
        c = client()
        if c is None:
            return {}
        try:
            return _fetch_stats(c)
        except Exception:
            return {}

    @output
    @render.ui
    def user_card() -> ui.Tag:
        sess = user_session()
        return _build_user_card(sess) if sess else ui.div()

    @output
    @render.ui
    def stats_row() -> ui.Tag:
        return _build_stats_row(_stats())

    @output
    @render.ui
    def shortcuts_row() -> ui.Tag:
        return _build_shortcuts_row(registry)

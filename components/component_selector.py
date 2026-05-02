from typing import TYPE_CHECKING

from shiny import module, reactive, render, ui

from components.registry import ComponentRegistry
from config.logging_config import set_debug_logging
from ui.theme import APP_TITLE

if TYPE_CHECKING:
    pass

_TOGGLE_PREFIX = "toggle_"

_COMP_ICONS: dict[str, str] = {
    "identities": "fa-users",
    "accounts": "fa-shield-halved",
    "search": "fa-magnifying-glass",
}

# (input_id, label, branding_api_key)
_COLOR_FIELDS: list[tuple[str, str, str]] = [
    ("nav_color", "Navigation", "navigation_color"),
    ("action_color", "Action Buttons", "action_button_color"),
    ("link_color", "Active Links", "active_link_color"),
]


def _toggle_id(name: str) -> str:
    return f"{_TOGGLE_PREFIX}{name}"


def _hex_color(data: dict, key: str, default: str) -> str:
    val = (data.get(key) or "").strip().lstrip("#")
    return val if val else default


# ---------------------------------------------------------------------------
# Branding preview
# ---------------------------------------------------------------------------


def _branding_preview(data: dict) -> ui.Tag:
    nav_bg = "#" + _hex_color(data, "navigation_color", "011533")
    action_bg = "#" + _hex_color(data, "action_button_color", "0033a1")
    link_color = "#" + _hex_color(data, "active_link_color", "0033a1")
    product_name = data.get("product_name") or APP_TITLE
    logo_url = data.get("logo_data_url")

    logo_el = (
        ui.tags.img(
            src=logo_url,
            alt="",
            style="height:16px;max-width:80px;object-fit:contain;",
            class_="me-2",
        )
        if logo_url
        else ui.tags.i(class_="fa-solid fa-shield-halved me-2", style="opacity:0.8;")
    )

    return ui.div(
        ui.div(
            ui.div(
                logo_el,
                ui.tags.span(product_name, class_="fw-semibold"),
                ui.div(
                    *[
                        ui.tags.span(lbl, class_="opacity-75 mx-1")
                        for lbl in ["Home", "Identities", "Accounts"]
                    ],
                    class_="ms-3 d-flex align-items-center",
                ),
                ui.tags.i(class_="fa-solid fa-circle-user ms-auto opacity-75"),
                class_="d-flex align-items-center px-3 py-2 text-white",
                style="font-size:0.8rem;",
            ),
            style=f"background-color:{nav_bg};",
        ),
        ui.div(
            ui.div(
                ui.tags.button(
                    ui.tags.i(class_="fa-solid fa-check me-1"),
                    "Primary action",
                    style=(
                        f"background-color:{action_bg};"
                        f"border-color:{action_bg};"
                        "color:#fff;pointer-events:none;"
                    ),
                    class_="btn btn-sm me-2",
                ),
                ui.tags.button(
                    "Secondary",
                    class_="btn btn-sm btn-outline-secondary",
                    style="pointer-events:none;",
                ),
                class_="mb-2",
            ),
            ui.tags.span(
                ui.tags.i(class_="fa-solid fa-arrow-right me-1"),
                ui.tags.a(
                    "Active link colour",
                    href="#",
                    style=f"color:{link_color};",
                    onclick="return false;",
                ),
            ),
            class_="p-3",
            style="background-color:var(--bs-body-bg);font-size:0.8rem;",
        ),
        class_="branding-preview border rounded overflow-hidden shadow-sm",
    )


# ---------------------------------------------------------------------------
# Module-level render helpers (extracted to keep server() complexity low)
# ---------------------------------------------------------------------------


def _component_list_items(registry: ComponentRegistry) -> list[ui.Tag]:
    return [
        ui.div(
            ui.input_switch(
                _toggle_id(c.name),
                ui.tags.span(
                    ui.tags.i(class_=f"fa-solid {_COMP_ICONS.get(c.name, 'fa-puzzle-piece')} me-2"),
                    c.label,
                ),
                value=c.enabled,
            ),
            ui.p(c.description, class_="text-muted small ps-4 mb-0"),
            class_="component-toggle",
        )
        for c in registry.get_all()
    ]


def _fill_tenant_btn_ui(data: "dict | None") -> ui.Tag:
    if data is None:
        return ui.p(
            ui.tags.i(class_="fa-solid fa-circle-notch fa-spin me-1 text-muted"),
            ui.tags.span("Loading tenant branding…", class_="text-muted small"),
            class_="mt-2 mb-0",
        )
    if not data:
        return ui.p(
            ui.tags.i(class_="fa-solid fa-circle-info me-1 text-muted"),
            "No branding configured for this tenant.",
            class_="text-muted small mt-2 mb-0",
        )
    return ui.div(
        ui.input_action_button(
            "fill_from_tenant",
            ui.tags.span(ui.tags.i(class_="fa-solid fa-fill-drip me-2"), "Fill from tenant branding"),
            class_="btn btn-outline-secondary btn-sm mt-2",
        )
    )


def _color_preview_ui(nav: str, action: str, link: str) -> ui.Tag:
    if not (nav or action or link):
        return ui.p(
            ui.tags.i(class_="fa-solid fa-circle-info me-1 text-muted"),
            "Enter colors above to see a live preview.",
            class_="text-muted small",
        )
    return _branding_preview({"navigation_color": nav, "action_button_color": action, "active_link_color": link})


def _read_color_inputs(input) -> dict:
    def clean(val: str) -> str:
        return (val or "").strip().lstrip("#")
    return {
        "navigation_color": clean(input.nav_color()),
        "action_button_color": clean(input.action_color()),
        "active_link_color": clean(input.link_color()),
    }


# ---------------------------------------------------------------------------
# Toggle effect helper
# ---------------------------------------------------------------------------


def _make_toggle_effect(
    input,
    registry: ComponentRegistry,
    name: str,
    updated: "reactive.Value[int]",
) -> None:
    tid = _toggle_id(name)

    @reactive.effect
    @reactive.event(input[tid], ignore_init=True)
    def _():
        if input[tid]():
            registry.enable(name)
        else:
            registry.disable(name)
        updated.set(updated.get() + 1)


# ---------------------------------------------------------------------------
# Shiny module
# ---------------------------------------------------------------------------


@module.ui
def component_selector_ui() -> ui.Tag:
    return ui.div(
        ui.h3(ui.tags.i(class_="fa-solid fa-sliders me-2 text-primary"), "Settings"),
        # ── Components ────────────────────────────────────────────────────
        ui.h5("Components", class_="mt-1 mb-1"),
        ui.p("Enable or disable components below.", class_="text-muted small"),
        ui.output_ui("component_list"),
        # ── Theme & Branding ──────────────────────────────────────────────
        ui.hr(class_="my-4"),
        ui.h5(
            ui.tags.i(class_="fa-solid fa-wand-magic-sparkles me-2"),
            "Theme & Branding",
        ),
        # Dark mode
        ui.h6(
            ui.tags.i(class_="fa-solid fa-circle-half-stroke me-2"),
            "Dark Mode",
            class_="mb-2 mt-3",
        ),
        ui.tags.button(
            ui.tags.i(class_="fa-solid fa-moon sp-theme-moon me-2"),
            ui.tags.i(class_="fa-solid fa-sun sp-theme-sun me-2"),
            "Toggle dark mode",
            onclick="spToggleTheme()",
            class_="btn btn-outline-secondary btn-sm mb-4",
        ),
        # Custom colors
        ui.h6(
            ui.tags.i(class_="fa-solid fa-palette me-2"),
            "Custom Colors",
            class_="mb-1",
        ),
        ui.p(
            "Enter 6-digit hex codes (without #). Leave blank to use defaults.",
            class_="text-muted small mb-3",
        ),
        *[ui.input_text(fid, label, placeholder="e.g. 0033a1") for fid, label, _ in _COLOR_FIELDS],
        # Tenant fill (dynamic — depends on whether API branding is available)
        ui.output_ui("fill_tenant_btn"),
        # Apply / Reset
        ui.div(
            ui.tags.button(
                ui.tags.i(class_="fa-solid fa-floppy-disk me-2"),
                "Save",
                onclick="spSaveColors()",
                class_="btn btn-primary btn-sm",
                title="Save colors so they persist after a page refresh",
            ),
            ui.tags.button(
                ui.tags.i(class_="fa-solid fa-rotate-left me-2"),
                "Reset",
                onclick="spResetColors()",
                class_="btn btn-outline-secondary btn-sm",
            ),
            class_="d-flex gap-2 mt-3",
        ),
        # Live preview
        ui.hr(class_="my-3"),
        ui.p(
            ui.tags.i(class_="fa-solid fa-eye me-1 text-muted"),
            "Preview",
            class_="small fw-semibold text-muted mb-2",
        ),
        ui.output_ui("color_preview"),
        # ── Developer ─────────────────────────────────────────────────────
        ui.hr(class_="my-4"),
        ui.h5(
            ui.tags.i(class_="fa-solid fa-bug me-2"),
            "Developer",
        ),
        ui.input_switch("debug_mode", "Enable debug logging", value=False),
        ui.p(
            "Writes verbose DEBUG messages to the server console.",
            class_="text-muted small ps-4 mt-1",
        ),
    )


@module.server
def component_selector_server(
    input,
    output,
    session,
    registry: ComponentRegistry,
    branding: "reactive.Value | None" = None,
    custom_colors: "reactive.Value[dict] | None" = None,
) -> "reactive.Value[int]":
    """Return a reactive counter that increments whenever a component is toggled."""
    updated: reactive.Value[int] = reactive.Value(0)

    @output
    @render.ui
    def component_list() -> ui.Tag:
        updated()
        return ui.div(*_component_list_items(registry))

    @output
    @render.ui
    def fill_tenant_btn() -> ui.Tag:
        return _fill_tenant_btn_ui(branding.get() if branding is not None else None)

    @output
    @render.ui
    def color_preview() -> ui.Tag:
        colors = _read_color_inputs(input)
        return _color_preview_ui(
            colors["navigation_color"],
            colors["action_button_color"],
            colors["active_link_color"],
        )

    @reactive.effect
    @reactive.event(input.fill_from_tenant)
    def _fill_from_tenant() -> None:
        data = branding.get() if branding is not None else None
        if not data:
            return
        ui.update_text("nav_color", value=data.get("navigation_color", ""))
        ui.update_text("action_color", value=data.get("action_button_color", ""))
        ui.update_text("link_color", value=data.get("active_link_color", ""))

    @reactive.effect
    def _toggle_debug() -> None:
        set_debug_logging(bool(input.debug_mode()))

    @reactive.effect
    def _sync_custom_colors() -> None:
        if custom_colors is None:
            return
        custom_colors.set(_read_color_inputs(input))

    for comp in registry.get_all():
        _make_toggle_effect(input, registry, comp.name, updated)

    return updated

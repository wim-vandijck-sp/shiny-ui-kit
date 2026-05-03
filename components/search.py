from collections.abc import Callable
from typing import TYPE_CHECKING

import pandas as pd
from shiny import module, reactive, render, ui

if TYPE_CHECKING:
    from isc.client import SailPointClient

_ALL_INDICES = [
    "identities",
    "accessprofiles",
    "roles",
    "entitlements",
    "events",
    "accountactivities",
]

_INDEX_LABELS: dict[str, str] = {
    "identities": "Identities",
    "accessprofiles": "Access Profiles",
    "roles": "Roles",
    "entitlements": "Entitlements",
    "events": "Events",
    "accountactivities": "Account Activities",
}

_INDEX_ICONS: dict[str, str] = {
    "identities": "fa-users",
    "accessprofiles": "fa-key",
    "roles": "fa-user-tag",
    "entitlements": "fa-list-check",
    "events": "fa-timeline",
    "accountactivities": "fa-clock-rotate-left",
}

_ALL_TYPES = "__all__"


def _field(r: object, *keys: str) -> str:
    for key in keys:
        val = r.get(key, "") if isinstance(r, dict) else getattr(r, key, "")
        if val:
            return str(val)
    return ""


def _make_results_frame(rows: list, type_filter: str) -> render.DataGrid:
    empty = render.DataGrid(pd.DataFrame({"type": [], "id": [], "name": []}))
    if not rows:
        return empty
    records = [
        {
            "type": _field(r, "_type"),
            "id": _field(r, "id"),
            "name": _field(r, "name", "displayName", "display_name"),
        }
        for r in rows
    ]
    df = pd.DataFrame(records)
    if type_filter and type_filter != _ALL_TYPES:
        df = df[df["type"] == type_filter]
    if df.empty:
        return empty
    return render.DataGrid(df, height="400px")


def _type_filter_choices(rows: list) -> dict[str, str]:
    choices = {_ALL_TYPES: "All types"}
    seen: set[str] = set()
    for r in rows:
        t = _field(r, "_type")
        if t and t not in seen:
            seen.add(t)
            choices[t] = _INDEX_LABELS.get(t, t.capitalize())
    return choices


def _index_checkbox(name: str) -> ui.Tag:
    icon_cls = _INDEX_ICONS.get(name, "fa-circle")
    default_on = name in {"identities", "accessprofiles", "roles"}
    return ui.div(
        ui.input_checkbox(
            f"idx_{name}",
            ui.tags.span(
                ui.tags.i(class_=f"fa-solid {icon_cls} me-1"),
                _INDEX_LABELS[name],
            ),
            value=default_on,
        ),
        class_="form-check form-check-inline",
    )


# ---------------------------------------------------------------------------
# Shiny module
# ---------------------------------------------------------------------------


@module.ui
def search_ui() -> ui.Tag:
    return ui.div(
        ui.h3(
            ui.tags.i(class_="fa-solid fa-magnifying-glass me-2 text-primary"), "Search"
        ),
        ui.row(
            ui.column(
                8,
                ui.input_text(
                    "query",
                    "Search Query",
                    placeholder="Search identities, roles, entitlements…",
                ),
            ),
            ui.column(
                4,
                ui.div(
                    ui.input_action_button(
                        "search_btn",
                        ui.tags.span(
                            ui.tags.i(class_="fa-solid fa-magnifying-glass me-1"),
                            "Search",
                        ),
                        class_="btn btn-primary w-100",
                    ),
                    class_="mt-4",
                ),
            ),
        ),
        ui.div(
            ui.p(
                ui.tags.i(class_="fa-solid fa-database me-1"),
                "Search in:",
                class_="mb-1 fw-semibold small",
            ),
            ui.div(
                *[_index_checkbox(name) for name in _ALL_INDICES],
                class_="d-flex flex-wrap gap-2 mb-3",
            ),
        ),
        ui.output_ui("type_filter_ui"),
        ui.output_data_frame("search_results"),
    )


@module.server
def search_server(
    input, output, session, *, client: "Callable[[], SailPointClient | None]"
) -> None:
    _last_results: reactive.Value[list] = reactive.Value([])

    def _selected_indices() -> list[str]:
        return [name for name in _ALL_INDICES if input[f"idx_{name}"]()]

    @reactive.calc
    def _results() -> list:
        input.search_btn()
        with reactive.isolate():
            query = input.query().strip()
            indices = _selected_indices()
        if not query or not indices:
            return []
        c = client()
        if c is None:
            return []
        try:
            rows = c.search_post(indices=indices, query=query, limit=100)
            _last_results.set(rows)
            return rows
        except Exception:
            return []

    @output
    @render.ui
    def type_filter_ui() -> ui.Tag:
        rows = _last_results.get()
        if not rows:
            return ui.div()
        choices = _type_filter_choices(rows)
        return ui.div(
            ui.input_select(
                "type_filter", "Filter by type", choices=choices, selected=_ALL_TYPES
            ),
            class_="mb-2",
        )

    @output
    @render.data_frame
    def search_results():
        rows = _results()
        type_filter = (
            input.type_filter() if hasattr(input, "type_filter") else _ALL_TYPES
        )
        return _make_results_frame(rows, type_filter)

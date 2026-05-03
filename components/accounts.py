from collections.abc import Callable
from typing import TYPE_CHECKING

import pandas as pd
from shiny import module, reactive, render, ui

if TYPE_CHECKING:
    from isc.client import SailPointClient

_PAGE_SIZES = [25, 50, 100, 250]
_ALL_SOURCES = "__all__"


# ---------------------------------------------------------------------------
# Pure helpers (no reactive context required)
# ---------------------------------------------------------------------------


def _attr(obj: object, *keys: str, default: str = "") -> str:
    for key in keys:
        val = getattr(obj, key, None)
        if val is not None and val != "":
            return str(val)
    return default


def _detail_row(label: str, value: str) -> ui.Tag:
    if not value:
        return ui.div()
    return ui.div(
        ui.span(f"{label}:", class_="fw-semibold me-2"),
        ui.span(value),
        class_="mb-2",
    )


def _bool_label(obj: object, attr: str) -> str:
    val = getattr(obj, attr, None)
    if val is None:
        return ""
    return "Yes" if val else "No"


def _build_filters(name_query: str, source: str) -> str | None:
    parts: list[str] = []
    if name_query:
        parts.append(f'name sw "{name_query}"')
    if source and source != _ALL_SOURCES:
        parts.append(f'sourceName eq "{source}"')
    return " and ".join(parts) if parts else None


def _get_source(input) -> str:
    return input.source() if hasattr(input, "source") else _ALL_SOURCES


def _account_detail_modal(r: object) -> ui.Tag:
    name = _attr(r, "name", "native_identity") or "Unknown"
    return ui.modal(
        ui.div(
            _detail_row("ID", _attr(r, "id")),
            _detail_row("Native Identity", _attr(r, "native_identity")),
            _detail_row("Source", _attr(r, "source_name")),
            _detail_row("Source ID", _attr(r, "source_id")),
            _detail_row("Correlated", _bool_label(r, "correlated")),
            _detail_row("Disabled", _bool_label(r, "disabled")),
            _detail_row("Locked", _bool_label(r, "locked")),
            _detail_row("Has Entitlements", _bool_label(r, "has_entitlements")),
        ),
        title=ui.tags.span(
            ui.tags.i(class_="fa-solid fa-shield-halved me-2 text-primary"), name
        ),
        easy_close=True,
        footer=ui.modal_button("Close"),
        size="m",
    )


def _make_accounts_frame(rows: list) -> render.DataGrid:
    if not rows:
        return render.DataGrid(
            pd.DataFrame({"id": [], "name": [], "source": [], "native_identity": []}),
            height="400px",
        )
    records = [
        {
            "id": _attr(r, "id"),
            "name": _attr(r, "name", "native_identity"),
            "source": _attr(r, "source_name"),
            "native_identity": _attr(r, "native_identity"),
        }
        for r in rows
    ]
    return render.DataGrid(pd.DataFrame(records), selection_mode="row", height="400px")


def _make_pagination_bar(page: int, has_next: bool) -> ui.Tag:
    prev_cls = "btn btn-sm btn-outline-secondary" + ("" if page > 1 else " disabled")
    next_cls = "btn btn-sm btn-outline-secondary" + ("" if has_next else " disabled")
    return ui.div(
        ui.input_action_button(
            "prev_page", ui.tags.i(class_="fa-solid fa-chevron-left"), class_=prev_cls
        ),
        ui.tags.span(f"Page {page}", class_="mx-2 align-middle text-muted small"),
        ui.input_action_button(
            "next_page", ui.tags.i(class_="fa-solid fa-chevron-right"), class_=next_cls
        ),
        class_="d-flex align-items-center mb-2",
    )


# ---------------------------------------------------------------------------
# Effect-setup helpers
# ---------------------------------------------------------------------------


def _setup_page_reset(input, _page: "reactive.Value[int]") -> None:
    @reactive.effect
    @reactive.event(input.search, input.source, input.page_size)
    def _reset_page() -> None:
        _page.set(1)


def _setup_pagination_effects(
    input, _page: "reactive.Value[int]", rows_fn: Callable
) -> None:
    @reactive.effect
    @reactive.event(input.prev_page)
    def _prev() -> None:
        if _page.get() > 1:
            _page.set(_page.get() - 1)

    @reactive.effect
    @reactive.event(input.next_page)
    def _next() -> None:
        if len(rows_fn()) == int(input.page_size()):
            _page.set(_page.get() + 1)


def _setup_detail_modal(input, rows_fn: Callable) -> None:
    @reactive.effect
    def _show_detail() -> None:
        selected = input.accounts_table_selected_rows()
        if not selected:
            return
        rows = rows_fn()
        idx = list(selected)[0]
        if not rows or idx >= len(rows):
            return
        ui.modal_show(_account_detail_modal(rows[idx]))


# ---------------------------------------------------------------------------
# Shiny module
# ---------------------------------------------------------------------------


@module.ui
def accounts_ui() -> ui.Tag:
    return ui.div(
        ui.h3(
            ui.tags.i(class_="fa-solid fa-shield-halved me-2 text-primary"), "Accounts"
        ),
        ui.row(
            ui.column(
                4, ui.input_text("search", "Search", placeholder="Account name…")
            ),
            ui.column(3, ui.output_ui("source_filter_ui")),
            ui.column(
                2,
                ui.input_select(
                    "page_size",
                    "Per page",
                    choices={str(n): str(n) for n in _PAGE_SIZES},
                    selected="50",
                ),
            ),
            ui.column(
                3,
                ui.div(
                    ui.input_action_button(
                        "refresh",
                        ui.tags.span(
                            ui.tags.i(class_="fa-solid fa-rotate-right me-1"), "Refresh"
                        ),
                        class_="btn btn-outline-secondary w-100",
                    ),
                    class_="mt-4",
                ),
            ),
        ),
        ui.output_ui("pagination_ui"),
        ui.output_data_frame("accounts_table"),
        ui.p(
            ui.tags.i(class_="fa-solid fa-circle-info me-1"),
            "Click a row to view account details.",
            class_="text-muted small mt-1",
        ),
    )


@module.server
def accounts_server(
    input, output, session, *, client: "Callable[[], SailPointClient | None]"
) -> None:
    _page: reactive.Value[int] = reactive.Value(1)

    _setup_page_reset(input, _page)

    @reactive.calc
    def _source_names() -> list[str]:
        input.refresh()
        c = client()
        if c is None:
            return []
        try:
            accounts = c.list_accounts(limit=250)
            return sorted(
                {_attr(a, "source_name") for a in accounts if _attr(a, "source_name")}
            )
        except Exception:
            return []

    @output
    @render.ui
    def source_filter_ui() -> ui.Tag:
        choices = {_ALL_SOURCES: "All sources"}
        choices.update({s: s for s in _source_names()})
        return ui.input_select(
            "source", "Source", choices=choices, selected=_ALL_SOURCES
        )

    @reactive.calc
    def _rows() -> list:
        input.refresh()
        c = client()
        if c is None:
            return []
        page_size = int(input.page_size())
        offset = (_page.get() - 1) * page_size
        filters = _build_filters(input.search().strip(), _get_source(input))
        try:
            return c.list_accounts(limit=page_size, offset=offset, filters=filters)
        except Exception:
            return []

    @output
    @render.ui
    def pagination_ui() -> ui.Tag:
        return _make_pagination_bar(_page.get(), len(_rows()) == int(input.page_size()))

    _setup_pagination_effects(input, _page, _rows)

    @output
    @render.data_frame
    def accounts_table():
        return _make_accounts_frame(_rows())

    _setup_detail_modal(input, _rows)

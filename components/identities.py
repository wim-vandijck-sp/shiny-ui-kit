from typing import TYPE_CHECKING, Callable

import pandas as pd
from shiny import module, reactive, render, ui

if TYPE_CHECKING:
    from isc.client import SailPointClient

_PAGE_SIZES = [25, 50, 100, 250]
_SORT_CHOICES = {
    "name": "Name A→Z",
    "-name": "Name Z→A",
    "email_address": "Email A→Z",
    "-email_address": "Email Z→A",
}


# ---------------------------------------------------------------------------
# Pure helpers
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


def _resolve_manager(r: object) -> str:
    name = _attr(r, "manager_display_name")
    if name:
        return name
    mgr = getattr(r, "manager", None)
    if isinstance(mgr, dict):
        return mgr.get("displayName", "") or mgr.get("name", "")
    if mgr is not None:
        return _attr(mgr, "display_name", "name")
    return ""


def _make_identities_frame(rows: list) -> render.DataGrid:
    if not rows:
        return render.DataGrid(
            pd.DataFrame({"id": [], "name": [], "email": [], "status": []}),
            height="400px",
        )
    records = [
        {
            "id": _attr(r, "id"),
            "name": _attr(r, "name", "display_name"),
            "email": _attr(r, "email_address"),
            "status": _attr(r, "status"),
        }
        for r in rows
    ]
    return render.DataGrid(pd.DataFrame(records), selection_mode="row", height="400px")


def _make_identity_modal(r: object) -> ui.Tag:
    name = _attr(r, "name", "display_name") or "Unknown"
    return ui.modal(
        ui.div(
            _detail_row("ID", _attr(r, "id")),
            _detail_row("Email", _attr(r, "email_address")),
            _detail_row("Status", _attr(r, "status")),
            _detail_row("Alias", _attr(r, "alias")),
            _detail_row("Manager", _resolve_manager(r)),
            _detail_row("Department", _attr(r, "department")),
            _detail_row("Title", _attr(r, "job_title", "title")),
            _detail_row("Phone", _attr(r, "phone")),
        ),
        title=ui.tags.span(ui.tags.i(class_="fa-solid fa-user me-2 text-primary"), name),
        easy_close=True,
        footer=ui.modal_button("Close"),
        size="m",
    )


def _pagination_bar(page: int, has_prev: bool, has_next: bool) -> ui.Tag:
    prev_cls = "btn btn-sm btn-outline-secondary" + ("" if has_prev else " disabled")
    next_cls = "btn btn-sm btn-outline-secondary" + ("" if has_next else " disabled")
    return ui.div(
        ui.input_action_button("prev_page", ui.tags.i(class_="fa-solid fa-chevron-left"), class_=prev_cls),
        ui.tags.span(f"Page {page}", class_="mx-2 align-middle text-muted small"),
        ui.input_action_button("next_page", ui.tags.i(class_="fa-solid fa-chevron-right"), class_=next_cls),
        class_="d-flex align-items-center mb-2",
    )


# ---------------------------------------------------------------------------
# Effect-setup helpers (registered in session context, defined outside server)
# ---------------------------------------------------------------------------


def _setup_pagination(input, _page: "reactive.Value[int]", rows_fn: Callable) -> None:
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
        selected = input.identities_table_selected_rows()
        if not selected:
            return
        rows = rows_fn()
        idx = list(selected)[0]
        if not rows or idx >= len(rows):
            return
        ui.modal_show(_make_identity_modal(rows[idx]))


# ---------------------------------------------------------------------------
# Shiny module
# ---------------------------------------------------------------------------


@module.ui
def identities_ui() -> ui.Tag:
    return ui.div(
        ui.h3(ui.tags.i(class_="fa-solid fa-users me-2 text-primary"), "Identities"),
        ui.row(
            ui.column(5, ui.input_text("search", "Search", placeholder="Name, email, alias…")),
            ui.column(3, ui.input_select("sort", "Sort by", choices=_SORT_CHOICES, selected="name")),
            ui.column(2, ui.input_select("page_size", "Per page", choices={str(n): str(n) for n in _PAGE_SIZES}, selected="50")),
            ui.column(
                2,
                ui.div(
                    ui.input_action_button(
                        "refresh",
                        ui.tags.span(ui.tags.i(class_="fa-solid fa-rotate-right me-1"), "Refresh"),
                        class_="btn btn-outline-secondary w-100",
                    ),
                    class_="mt-4",
                ),
            ),
        ),
        ui.output_ui("pagination_ui"),
        ui.output_data_frame("identities_table"),
        ui.p(
            ui.tags.i(class_="fa-solid fa-circle-info me-1"),
            "Click a row to view identity details.",
            class_="text-muted small mt-1",
        ),
    )


@module.server
def identities_server(
    input, output, session, *, client: "Callable[[], SailPointClient | None]"
) -> None:
    _page: reactive.Value[int] = reactive.Value(1)

    @reactive.effect
    @reactive.event(input.search, input.sort, input.page_size)
    def _reset_page() -> None:
        _page.set(1)

    @reactive.calc
    def _rows() -> list:
        input.refresh()
        c = client()
        if c is None:
            return []
        try:
            page_size = int(input.page_size())
            query = input.search().strip()
            if query:
                return c.search_identities(query, limit=page_size)
            offset = (_page.get() - 1) * page_size
            return c.list_identities(limit=page_size, offset=offset, sorters=input.sort())
        except Exception:
            return []

    @output
    @render.ui
    def pagination_ui() -> ui.Tag:
        page = _page.get()
        return _pagination_bar(page, has_prev=page > 1, has_next=len(_rows()) == int(input.page_size()))

    @output
    @render.data_frame
    def identities_table():
        return _make_identities_frame(_rows())

    _setup_pagination(input, _page, _rows)
    _setup_detail_modal(input, _rows)

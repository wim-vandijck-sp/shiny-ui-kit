---
name: add-component
description: Add a new UI component to the SailPoint Identity Manager. Generates the Shiny module file and patches app.py. Use when the user wants to add a new tab/feature to the app (e.g. "add a certifications component", "create a roles viewer", "add a new component called X").
---

You are adding a new pluggable component to the SailPoint Identity Manager (a Shiny for Python app).

## Step 0 — Gather requirements

If the user has not already provided all of the following, ask for them in a single message (do not ask one at a time):

- **name**: short lowercase Python identifier, e.g. `certifications` (used as module/variable name and registry key)
- **label**: display name shown in the nav bar, e.g. `Certifications`
- **description**: one sentence shown in the Settings toggle, e.g. `Review open certification campaigns.`
- **icon**: Bootstrap Icons name, e.g. `patch-check` (optional, defaults to `grid`)
- **API method**: the `SailPointClient` method that returns a list of items (e.g. `list_certifications()`), or "none" if no API access is needed
- **Columns**: which fields to show in the table (e.g. `id`, `name`, `status`)

Once you have all the information, proceed without asking further clarifying questions.

## Step 1 — Read current state

Before writing anything, read:
1. `components/` directory listing — to confirm the file doesn't already exist
2. `app.py` — to find the exact locations to patch (import block, registry.register calls, `_COMPONENT_UI` dict, and the server wiring section)
3. `isc/client.py` — to verify the API method exists and check its signature

## Step 2 — Create the component file

Write `components/<name>.py` following this exact pattern:

```python
from typing import TYPE_CHECKING, Callable

import pandas as pd
from shiny import module, reactive, render, ui

if TYPE_CHECKING:
    from isc.client import SailPointClient

_PAGE_SIZES = [25, 50, 100, 250]


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


def _make_<name>_frame(rows: list) -> "render.DataGrid":
    import pandas as pd
    if not rows:
        return render.DataGrid(
            pd.DataFrame({col: [] for col in COLUMNS}),
            height="400px",
        )
    records = [
        {col: _attr(r, col) for col in COLUMNS}
        for r in rows
    ]
    return render.DataGrid(pd.DataFrame(records), selection_mode="row", height="400px")


def _<name>_detail_modal(r: object) -> "ui.Tag":
    name = _attr(r, "name", "id") or "Unknown"
    return ui.modal(
        ui.div(*[_detail_row(col.replace("_", " ").title(), _attr(r, col)) for col in COLUMNS]),
        title=name,
        easy_close=True,
        footer=ui.modal_button("Close"),
        size="m",
    )


def _setup_pagination_effects(input, _page, rows_fn):
    @reactive.effect
    @reactive.event(input.search, input.page_size)
    def _reset_page():
        _page.set(1)

    @reactive.effect
    @reactive.event(input.prev_page)
    def _prev():
        if _page.get() > 1:
            _page.set(_page.get() - 1)

    @reactive.effect
    @reactive.event(input.next_page)
    def _next():
        if len(rows_fn()) == int(input.page_size()):
            _page.set(_page.get() + 1)


def _setup_detail_modal(input, rows_fn, table_id):
    @reactive.effect
    def _show_detail():
        selected = input[f"{table_id}_selected_rows"]()
        if not selected:
            return
        rows = rows_fn()
        idx = list(selected)[0]
        if not rows or idx >= len(rows):
            return
        ui.modal_show(_<name>_detail_modal(rows[idx]))


@module.ui
def <name>_ui() -> ui.Tag:
    return ui.div(
        ui.h3(LABEL),
        ui.row(
            ui.column(
                8,
                ui.input_text("search", "Search", placeholder="Search…"),
            ),
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
                2,
                ui.div(
                    ui.input_action_button("refresh", "Refresh", class_="btn btn-outline-secondary w-100"),
                    class_="mt-4",
                ),
            ),
        ),
        ui.output_ui("pagination_ui"),
        ui.output_data_frame("<name>_table"),
        ui.p("Click a row to view details.", class_="text-muted small mt-1"),
    )


@module.server
def <name>_server(
    input, output, session, *, client: "Callable[[], SailPointClient | None]"
) -> None:
    _page = reactive.Value(1)

    @reactive.calc
    def _rows() -> list:
        input.refresh()
        c = client()
        if c is None:
            return []
        try:
            page_size = int(input.page_size())
            offset = (_page.get() - 1) * page_size
            # TODO: replace with the real client method + any search/filter logic
            return c.API_METHOD(limit=page_size, offset=offset)
        except Exception:
            return []

    @output
    @render.ui
    def pagination_ui():
        page = _page.get()
        has_next = len(_rows()) == int(input.page_size())
        prev_cls = "btn btn-sm btn-outline-secondary me-1" + ("" if page > 1 else " disabled")
        next_cls = "btn btn-sm btn-outline-secondary" + ("" if has_next else " disabled")
        return ui.div(
            ui.tags.span(f"Page {page}", class_="me-2 text-muted small"),
            ui.input_action_button("prev_page", "← Prev", class_=prev_cls),
            ui.input_action_button("next_page", "Next →", class_=next_cls),
            class_="d-flex align-items-center mb-2",
        )

    _setup_pagination_effects(input, _page, _rows)

    @output
    @render.data_frame
    def <name>_table():
        return _make_<name>_frame(_rows())

    _setup_detail_modal(input, _rows, "<name>_table")
```

**Fill in the placeholders** from the user's inputs:
- `<name>` → the component name
- `LABEL` → the label string
- `COLUMNS` → list of column names
- `API_METHOD` → the client method name

If the component needs no SailPoint API, remove the `client` parameter and the `_rows` calc; replace the data frame with static or session-derived content.

## Step 3 — Patch app.py

Make **four targeted edits** to `app.py` using the Edit tool. Do them in order so line numbers stay stable:

### 3a. Add import (after the last `from components.` import line)
```python
from components.<name> import <name>_server, <name>_ui
```

### 3b. Add registry entry (after the last `registry.register(...)` block)
```python
registry.register(
    ComponentInfo(
        name="<name>",
        label="<Label>",
        description="<description>",
        icon="<icon>",
    )
)
```

### 3c. Add pre-built UI (inside `_COMPONENT_UI` dict)
```python
    "<name>": <name>_ui("<name>"),
```

### 3d. Add server wiring (after the last `*_server(...)` call in `server()`)
```python
    <name>_server("<name>", client=_isc_client)
```

## Step 4 — Verify edits

After all edits, re-read `app.py` and confirm all four changes are present and syntactically correct.

## Step 5 — Report

Tell the user:
- The new file that was created
- The four lines added to `app.py`
- How to start the app and test the new component
- Any `TODO` left in the generated code (e.g. the real API method to use)

Keep the report concise — one short paragraph or bullet list is enough.

# Adding a New Component

This guide explains how to add a new UI component to the SailPoint Identity Manager. A component is a self-contained Shiny module that appears as a tab in the navigation bar and can be enabled/disabled by users from the Settings page.

---

## What is a Component?

Each component consists of three parts:

1. **A Shiny module file** (`components/<name>.py`) — the UI and server logic.
2. **A registry entry** in `app.py` — registers the component so the app knows it exists.
3. **A server wiring call** in `app.py` — connects the module to the live app session.

---

## Step-by-Step Guide

### Step 1 — Create the module file

Create `components/<name>.py`. Replace `<name>` with a short, lowercase, underscore-separated identifier (e.g. `certifications`, `roles`, `audit_log`).

```python
# components/certifications.py
from typing import TYPE_CHECKING, Callable

import pandas as pd
from shiny import module, reactive, render, ui

if TYPE_CHECKING:
    from isc.client import SailPointClient


@module.ui
def certifications_ui() -> ui.Tag:
    return ui.div(
        ui.h3("Certifications"),
        ui.row(
            ui.column(
                10,
                ui.input_text("search", "Search", placeholder="Campaign name…"),
            ),
            ui.column(
                2,
                ui.div(
                    ui.input_action_button("refresh", "Refresh", class_="btn btn-outline-secondary w-100"),
                    class_="mt-4",
                ),
            ),
        ),
        ui.output_data_frame("certifications_table"),
    )


@module.server
def certifications_server(
    input, output, session, *, client: "Callable[[], SailPointClient | None]"
) -> None:
    @reactive.calc
    def _rows() -> list:
        input.refresh()
        c = client()
        if c is None:
            return []
        try:
            return c.list_certifications()  # replace with the real SDK call
        except Exception:
            return []

    @output
    @render.data_frame
    def certifications_table():
        rows = _rows()
        if not rows:
            return render.DataGrid(
                pd.DataFrame({"id": [], "name": [], "status": []}),
                height="400px",
            )
        records = [
            {
                "id": getattr(r, "id", ""),
                "name": getattr(r, "name", ""),
                "status": getattr(r, "status", ""),
            }
            for r in rows
        ]
        return render.DataGrid(pd.DataFrame(records), selection_mode="row", height="400px")
```

**Rules to follow:**

| Rule | Reason |
|------|--------|
| Name the UI function `<name>_ui` | Convention matched by `app.py` imports |
| Name the server function `<name>_server` | Same |
| Accept `client` as a keyword-only argument | All components that hit the API receive the client this way |
| Return `[]` (not raise) on exceptions | Prevents the whole page from crashing on API errors |
| Use `input.refresh()` at the top of reactive calcs | Lets the user force a fresh fetch |

If your component does **not** need SailPoint API access (e.g. a static help page), omit the `client` parameter and the `isc` imports.

---

### Step 2 — Register the component

Open `app.py` and add three things.

#### 2a. Import the module

```python
from components.certifications import certifications_server, certifications_ui
```

#### 2b. Register with the registry (near the top of `app.py`)

```python
registry.register(
    ComponentInfo(
        name="certifications",          # must match the module file name
        label="Certifications",         # shown in the nav bar and Settings
        description="Review open certification campaigns.",
        icon="patch-check",             # Bootstrap Icons name
    )
)
```

The registry persists enabled/disabled state to `config/config.json`. On first run the component is **enabled by default** (`enabled=True`). To default it to disabled, pass `enabled=False`.

#### 2c. Add the pre-built module UI

```python
_COMPONENT_UI: dict[str, ui.Tag] = {
    "identities": identities_ui("identities"),
    "accounts": accounts_ui("accounts"),
    "search": search_ui("search"),
    "certifications": certifications_ui("certifications"),  # ← add this
}
```

The key must exactly match the `name` you used in `registry.register`.

#### 2d. Wire the server module

Inside the `server(input, output, session)` function, add:

```python
certifications_server("certifications", client=_isc_client)
```

If your component doesn't use the SailPoint client, omit the `client=` keyword argument.

---

### Step 3 — Verify

Start the development server and log in:

```bash
python run.py
```

1. The new tab should appear in the navigation bar (if the component is enabled).
2. Open **Settings** — the toggle for your component should be present.
3. Disable it and confirm it disappears from the nav; enable it and confirm it reappears.

---

## Component Patterns Reference

### Pagination

Use a `reactive.Value[int]` for the current page and wire Prev/Next buttons to it. Reset to page 1 whenever filters change. See [components/identities.py](../components/identities.py) for a complete example.

```python
_page: reactive.Value[int] = reactive.Value(1)

@reactive.effect
@reactive.event(input.search, input.page_size)
def _reset_page() -> None:
    _page.set(1)
```

### Detail modal

Call `ui.modal_show(ui.modal(...))` from inside a `@reactive.effect` that depends on `input.<table_id>_selected_rows()`.

```python
@reactive.effect
def _show_detail() -> None:
    selected = input.my_table_selected_rows()
    if not selected:
        return
    rows = _rows()
    idx = list(selected)[0]
    if not rows or idx >= len(rows):
        return
    ui.modal_show(
        ui.modal(
            ui.div(...),
            title="Detail",
            easy_close=True,
            footer=ui.modal_button("Close"),
        )
    )
```

### Dynamic filter dropdown

Render a `ui.input_select` inside `@output @render.ui` so it populates after data loads. Use `hasattr(input, "my_select")` before reading it in calcs to guard against the first render cycle.

```python
@output
@render.ui
def filter_ui() -> ui.Tag:
    choices = {"__all__": "All"} | {s: s for s in _get_options()}
    return ui.input_select("my_filter", "Filter", choices=choices)
```

### Components without API access

If a component only reads session data (e.g. a profile page), accept `user_session` instead of `client`:

```python
@module.server
def profile_server(input, output, session, *, user_session) -> None:
    ...
```

---

## File Checklist

```
components/
  <name>.py          ← new file (Step 1)

app.py               ← updated in 4 places (Step 2a–d)
  + import <name>_ui, <name>_server
  + registry.register(ComponentInfo(name="<name>", ...))
  + _COMPONENT_UI["<name>"] = <name>_ui("<name>")
  + <name>_server("<name>", client=_isc_client)
```

That's it. The component registry, nav-bar rebuilding, and settings toggle are all handled automatically.

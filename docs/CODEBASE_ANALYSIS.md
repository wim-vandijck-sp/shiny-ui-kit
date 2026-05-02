# SailPoint Identity Manager — Codebase Analysis

## What This App Is

A browser-based management UI built on top of the SailPoint ISC API. It uses **Shiny for Python** as the reactive UI framework and **Starlette** as the web server. Think of it as a configurable admin console: authenticated users see a tabbed interface where each tab is a self-contained "component" that queries ISC and displays results.

---

## Overall Architecture

```
Browser
  └── Starlette (run.py)
        ├── /api/auth/* and /oauth/callback  ← OAuth2 flow (auth/)
        └── /*  ← Shiny app (app.py)
                    ├── Session management (auth/session_manager.py)
                    ├── ISC API client (isc/client.py)
                    ├── Component registry (components/registry.py)
                    └── UI Components (components/*.py)
```

The three layers that matter for anyone adding functionality:

| Layer | Files | Responsibility |
|---|---|---|
| **API Client** | `isc/client.py` | Wraps the SailPoint Python SDK; one method per ISC API call |
| **Component** | `components/<name>.py` | Shiny module: UI layout + reactive server logic |
| **Wiring** | `app.py` | Imports components, registers them, connects everything |

---

## How Authentication Works

The app uses the ISC OAuth2 Authorization Code flow — the same flow you'd configure in the ISC Admin UI under **API Management → OAuth Applications**.

```
User visits /  →  no cookie  →  login page
User clicks "Login with SailPoint"
  →  GET /api/auth/login  →  redirect to login.sailpoint.com/oauth/authorize
  →  user authenticates with SailPoint
  →  callback to /oauth/callback?code=...&state=...
  →  app exchanges code for access token via /oauth/token
  →  session cookie set  →  app renders
```

Configuration in `.env`:
```
SAIL_BASE_URL=https://<tenant>.api.identitynow.com
SAIL_CLIENT_ID=<your-oauth-client-id>
SAIL_CLIENT_SECRET=<your-oauth-client-secret>
```

The app automatically derives the authorization URL from the tenant hostname. Token refresh is handled transparently: before any API call the client layer checks whether the token is within 60 seconds of expiry and refreshes it using the stored refresh token.

---

## The ISC API Client (`isc/client.py`)

`SailPointClient` is a thin wrapper around the official SailPoint Python SDK. Each method maps directly to an ISC API endpoint:

```python
class SailPointClient:
    def list_identities(limit, offset, filters, sorters)  → list[Identity]
    def get_identity(identity_id)                          → Identity
    def search_identities(query, limit)                    → list[Any]
    def list_accounts(limit, offset, filters, sorters)     → list[Account]
    def search_post(indices, query, limit, offset)         → list[Any]
    def get_branding()                                     → dict
```

All SDK exceptions (`ApiException`) are caught and re-raised as `SailPointError`, so components never need to import SDK internals.

**Adding a new ISC API call** means adding one method here:

```python
# isc/client.py
from sailpoint.v2025.api.certifications_api import CertificationsApi

def list_certifications(self, limit=250, offset=0) -> list:
    api = CertificationsApi(self._api_client)
    return self._call(api.list_certifications, limit=limit, offset=offset)
```

That's it — the `_call` wrapper handles logging, timing, and error conversion automatically.

---

## How Components Work

Components are **Shiny modules** — a pattern for encapsulating UI and server logic in a reusable, namespace-isolated unit. Each component lives in its own file and exposes exactly two functions:

```
<name>_ui()     ← returns the HTML layout for the tab
<name>_server() ← runs the reactive logic that populates that layout
```

### Anatomy of a Component (`components/identities.py`)

```python
@module.ui
def identities_ui() -> ui.Tag:
    # Declares the HTML structure: search box, table, pagination
    return ui.div(
        ui.input_text("search", "Search", ...),
        ui.output_data_frame("identities_table"),
        ...
    )

@module.server
def identities_server(input, output, session, *, client) -> None:
    # Reactive data fetch — re-runs when search, sort, or page changes
    @reactive.calc
    def _rows() -> list:
        input.refresh()          # makes refresh button trigger a re-fetch
        c = client()             # get the ISC client (may refresh token)
        if c is None:
            return []
        try:
            return c.list_identities(...)
        except Exception:
            return []

    # Renderer — re-runs when _rows() changes
    @output
    @render.data_frame
    def identities_table():
        return _make_identities_frame(_rows())
```

The `client` parameter is a **callable** (a reactive calc), not a client instance directly. Calling `client()` inside a reactive context means the component automatically re-renders if the user's session or token changes.

### The Registry (`components/registry.py`)

The registry is the single source of truth for which components exist and whether each is enabled. It reads/writes `config/config.json` so toggle state survives app restarts.

```python
# config/config.json (auto-managed)
{
  "components": {
    "identities": { "enabled": true },
    "accounts":   { "enabled": true },
    "search":     { "enabled": true }
  }
}
```

Components registered here automatically get a toggle in the **Settings** tab — no extra code needed.

### How Wiring Works (`app.py`)

`app.py` is where everything connects. It has four spots that matter per component:

```python
# 1. Import
from components.identities import identities_ui, identities_server

# 2. Register (near top, after creating registry)
registry.register(ComponentInfo(
    name="identities",
    label="Identities",
    description="Browse and search identities.",
    icon="people",
))

# 3. Pre-build the UI tag (once, at module load time)
_COMPONENT_UI = {
    "identities": identities_ui("identities"),
    ...
}

# 4. Wire the server (inside the server() function)
identities_server("identities", client=_isc_client)
```

The nav bar is rebuilt dynamically from `registry.get_enabled()` — enabling or disabling a component in Settings immediately adds or removes its tab.

---

## How to Add a New Component

The pattern is identical every time. Here's a concrete example: adding an **Access Profiles** browser.

### Step 1 — Add the API method to the client

```python
# isc/client.py
from sailpoint.v2025.api.access_profiles_api import AccessProfilesApi
from sailpoint.v2025.models.access_profile import AccessProfile

def list_access_profiles(self, limit=250, offset=0, filters=None) -> list[AccessProfile]:
    api = AccessProfilesApi(self._api_client)
    return self._call(api.list_access_profiles, limit=limit, offset=offset, filters=filters)
```

### Step 2 — Create the component file

```python
# components/access_profiles.py
from typing import TYPE_CHECKING, Callable
import pandas as pd
from shiny import module, reactive, render, ui

if TYPE_CHECKING:
    from isc.client import SailPointClient


@module.ui
def access_profiles_ui() -> ui.Tag:
    return ui.div(
        ui.h3(ui.tags.i(class_="fa-solid fa-key me-2 text-primary"), "Access Profiles"),
        ui.row(
            ui.column(10, ui.input_text("search", "Search", placeholder="Profile name…")),
            ui.column(2, ui.div(
                ui.input_action_button("refresh", "Refresh", class_="btn btn-outline-secondary w-100"),
                class_="mt-4",
            )),
        ),
        ui.output_data_frame("ap_table"),
    )


@module.server
def access_profiles_server(
    input, output, session, *, client: "Callable[[], SailPointClient | None]"
) -> None:
    @reactive.calc
    def _rows() -> list:
        input.refresh()
        c = client()
        if c is None:
            return []
        try:
            query = input.search().strip()
            filters = f'name co "{query}"' if query else None
            return c.list_access_profiles(filters=filters)
        except Exception:
            return []

    @output
    @render.data_frame
    def ap_table():
        rows = _rows()
        if not rows:
            return render.DataGrid(
                pd.DataFrame({"id": [], "name": [], "enabled": [], "owner": []}),
                height="400px",
            )
        records = [
            {
                "id":      getattr(r, "id", ""),
                "name":    getattr(r, "name", ""),
                "enabled": getattr(r, "enabled", ""),
                "owner":   getattr(r.owner, "name", "") if getattr(r, "owner", None) else "",
            }
            for r in rows
        ]
        return render.DataGrid(pd.DataFrame(records), selection_mode="row", height="400px")
```

### Step 3 — Wire it into `app.py` (4 lines)

```python
# Top of file — import
from components.access_profiles import access_profiles_ui, access_profiles_server

# After registry is created — register
registry.register(ComponentInfo(
    name="access_profiles",
    label="Access Profiles",
    description="Browse access profiles and their owners.",
    icon="key",
))

# In _COMPONENT_UI dict — add UI tag
_COMPONENT_UI = {
    ...
    "access_profiles": access_profiles_ui("access_profiles"),
}

# Inside server() function — wire server
access_profiles_server("access_profiles", client=_isc_client)
```

Also add the FontAwesome icon to `_ICON_MAP` at the top of `app.py`:

```python
_ICON_MAP = {
    ...
    "access_profiles": "fa-key",
}
```

### Complete Checklist

```
File                           Change
─────────────────────────────────────────────────────────────
isc/client.py                  Add API method(s)
components/<name>.py           New file: @module.ui + @module.server
app.py line ~10                Import <name>_ui, <name>_server
app.py line ~85                registry.register(ComponentInfo(...))
app.py line ~90                _COMPONENT_UI["<name>"] = <name>_ui("<name>")
app.py line ~75                _ICON_MAP["<name>"] = "fa-<icon>"
app.py line ~307               <name>_server("<name>", client=_isc_client)
```

The Settings toggle, nav bar inclusion, and enable/disable persistence are all automatic.

---

## Key Patterns to Know

| Pattern | Where | What it does |
|---|---|---|
| `@reactive.calc` | component server | Caches result; re-runs only when dependencies change |
| `@reactive.event(input.x)` | component server | Limits re-runs to specific input changes only |
| `input.refresh()` at top of calc | `_rows()` | Makes the Refresh button invalidate the cache |
| `client()` is callable | component server | Ensures token refresh is transparent |
| `try / except → return []` | `_rows()` | Component fails silently; never crashes the whole app |
| Module namespace (`"identities"`) | `app.py` wiring | All input/output IDs inside a module are prefixed automatically |
| `config/config.json` | registry | Persists which components are enabled across restarts |

---

## ISC API Coverage (What's Already There)

| ISC Object | Client Methods | Component |
|---|---|---|
| Identities | `list_identities`, `get_identity`, `search_identities` | Identities tab |
| Accounts | `list_accounts` | Accounts tab |
| Search | `search_post` (all indices) | Search tab |
| Branding | `get_branding` | Applied to nav/colors |

Any ISC v2025 API that has a Python SDK class can be added to `isc/client.py` in 5 lines and immediately consumed by a new component. The SDK is already installed and authenticated.

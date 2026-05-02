# Architecture

See `SHINY_PYTHON_PROJECT_PLAN.md` in the project root for the full architecture diagram and design decisions.

## Key Components

- **`app.py`** — Shiny UI definition and server function
- **`run.py`** — Combines Shiny app with Starlette for OAuth routing
- **`auth/`** — OAuth flow, session management, and API routes
- **`components/`** — Shiny modules for each feature area
- **`sailpoint/`** — SailPoint API client wrapper
- **`ui/`** — Shared UI helpers and styles
- **`config/`** — Settings and component configuration persistence

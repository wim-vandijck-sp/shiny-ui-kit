# Setup Guide

## Prerequisites

-   Python 3.11+
-   A SailPoint Identity Security Cloud tenant
-   An OAuth client configured in SailPoint ISC

## SailPoint OAuth Client Setup

1.  Log into SailPoint ISC as an administrator
1.  Navigate to: Admin → Security Settings → API Management
1.  Create a new OAuth client:
   -   **Name:** "Identity Manager - Development"
   -   **Grant Types:** Authorization Code
   -   **Redirect URI (dev):** `http://localhost:8000/oauth/callback`
   -   **Scopes:** `sp:scopes:all`
   -   **Refresh Token:** Enabled
1.  Record the Client ID and Client Secret

## Local Development

```bash
# Clone and enter the project
cd shiny-ui-kit

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your SailPoint credentials

# Run the development server
python run.py
```

Open `http://localhost:8000` in your browser.

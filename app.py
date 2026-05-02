import logging
from pathlib import Path

from shiny import App, reactive, render, ui

from auth.starlette_routes import _get_oauth_handler, get_session_manager
from components.accounts import accounts_server, accounts_ui
from components.component_selector import (
    component_selector_server,
    component_selector_ui,
)
from components.home import home_server, home_ui
from components.identities import identities_server, identities_ui
from components.login import login_server, login_ui
from components.registry import ComponentInfo, ComponentRegistry
from components.search import search_server, search_ui
from isc.oauth_client import get_client_for_session
from ui.theme import APP_TITLE, SP_NAV_BG

logger = logging.getLogger(__name__)


_CSS_PATH = Path(__file__).parent / "ui" / "styles.css"
_LOGOUT_JS = "fetch('/api/auth/logout',{method:'POST'}).then(()=>location.assign('/'))"
_FA_CDN = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css"

# IIFE applies saved theme before first render to prevent flash.
_DARK_MODE_JS = """
(function(){
  var t=localStorage.getItem('sp-theme')||'light';
  document.documentElement.setAttribute('data-bs-theme',t);
})();
function spToggleTheme(){
  var h=document.documentElement;
  var n=h.getAttribute('data-bs-theme')==='dark'?'light':'dark';
  h.setAttribute('data-bs-theme',n);
  localStorage.setItem('sp-theme',n);
}
function spGetInput(name){
  /* Shiny wraps <input> in a container <div> with the same id.
     getElementById returns the div first; unwrap it to reach the actual input. */
  var el=document.getElementById(name);
  if(!el)return null;
  return el.tagName==='INPUT'?el:el.querySelector('input');
}
function spSaveColors(){
  function v(n){var e=spGetInput(n);return e?e.value.trim().replace(/^#/,''):''}
  localStorage.setItem('sp-custom-colors',JSON.stringify({
    nav:v('settings-nav_color'),
    action:v('settings-action_color'),
    link:v('settings-link_color')
  }));
}
function spResetColors(){
  localStorage.removeItem('sp-custom-colors');
  ['settings-nav_color','settings-action_color','settings-link_color'].forEach(function(name){
    var el=spGetInput(name);
    if(el){el.value='';el.dispatchEvent(new Event('change',{bubbles:true}));}
  });
}
function spRestoreColors(attempt){
  attempt=attempt||0;
  var c=JSON.parse(localStorage.getItem('sp-custom-colors')||'{}');
  if(!c.nav&&!c.action&&!c.link)return;
  /* main() renders server-side after Shiny connects — poll until inputs exist */
  if(!spGetInput('settings-nav_color')&&attempt<40){
    setTimeout(function(){spRestoreColors(attempt+1);},250);
    return;
  }
  [['settings-nav_color','nav'],['settings-action_color','action'],['settings-link_color','link']].forEach(function(f){
    var val=c[f[1]]||'';
    var inp=spGetInput(f[0]);
    if(inp&&val){inp.value=val;inp.dispatchEvent(new Event('change',{bubbles:true}));}
  });
}
window.addEventListener('load',function(){spRestoreColors();});
"""

_ICON_MAP: dict[str, str] = {
    "identities": "fa-users",
    "accounts": "fa-shield-halved",
    "search": "fa-magnifying-glass",
}

# ---------------------------------------------------------------------------
# Singleton registry
# ---------------------------------------------------------------------------
registry = ComponentRegistry()
registry.register(
    ComponentInfo(
        name="identities",
        label="Identities",
        description="Browse and search identities.",
        icon="people",
    )
)
registry.register(
    ComponentInfo(
        name="accounts",
        label="Accounts",
        description="View accounts across sources.",
        icon="shield",
    )
)
registry.register(
    ComponentInfo(
        name="search",
        label="Search",
        description="Run global full-text searches.",
        icon="search",
    )
)

_HOME_UI: ui.Tag = home_ui("home")
_COMPONENT_UI: dict[str, ui.Tag] = {
    "identities": identities_ui("identities"),
    "accounts": accounts_ui("accounts"),
    "search": search_ui("search"),
}


# ---------------------------------------------------------------------------
# Pure UI-building helpers (no reactive context required)
# ---------------------------------------------------------------------------


def _nav_label(icon_cls: str, label: str) -> ui.Tag:
    return ui.tags.span(ui.tags.i(class_=f"fa-solid {icon_cls} me-1"), label)


def _build_nav_panels() -> list[ui.Tag]:
    panels: list[ui.Tag] = [
        ui.nav_panel(_nav_label("fa-house", "Home"), _HOME_UI, value="Home")
    ]
    for comp in registry.get_enabled():
        panel_ui = _COMPONENT_UI.get(comp.name)
        if panel_ui is not None:
            icon = _ICON_MAP.get(comp.name, "fa-grid")
            panels.append(
                ui.nav_panel(_nav_label(icon, comp.label), panel_ui, value=comp.label)
            )
    panels.append(
        ui.nav_panel(
            _nav_label("fa-sliders", "Settings"),
            component_selector_ui("settings"),
            value="Settings",
        )
    )
    return panels


def _build_navbar_title(logo_url: str | None) -> ui.Tag:
    if logo_url:
        return ui.tags.span(
            ui.tags.img(src=logo_url, alt="", class_="me-2"),
            APP_TITLE,
            class_="d-flex align-items-center",
        )
    return ui.tags.span(
        ui.tags.i(class_="fa-solid fa-shield-halved me-2"),
        APP_TITLE,
    )


def _build_theme_btn() -> ui.Tag:
    return ui.nav_control(
        ui.tags.button(
            ui.tags.i(class_="fa-solid fa-moon sp-theme-moon"),
            ui.tags.i(class_="fa-solid fa-sun sp-theme-sun"),
            id="sp-theme-btn",
            onclick="spToggleTheme()",
            class_="btn btn-sm btn-outline-light ms-1",
            title="Toggle dark mode",
        )
    )


def _build_user_menu(user_name: str) -> ui.Tag:
    return ui.nav_menu(
        ui.tags.span(ui.tags.i(class_="fa-solid fa-circle-user me-1"), user_name),
        ui.nav_control(
            ui.tags.a(
                ui.tags.i(class_="fa-solid fa-right-from-bracket me-2"),
                "Logout",
                href="#",
                onclick=_LOGOUT_JS,
            )
        ),
        align="right",
    )


def _build_custom_css(colors: dict) -> str:
    _HEX = set("0123456789abcdefABCDEF")

    def clean(key: str) -> str:
        return (colors.get(key) or "").strip().lstrip("#").lower()

    def valid(h: str) -> bool:
        return len(h) == 6 and all(c in _HEX for c in h)

    parts: list[str] = []
    nav = clean("navigation_color")
    action = clean("action_button_color")
    link = clean("active_link_color")
    if valid(nav):
        parts.append(f".navbar {{ background-color: #{nav} !important; }}")
    if valid(action):
        r, g, b = int(action[0:2], 16), int(action[2:4], 16), int(action[4:6], 16)
        parts.append(
            f":root {{ --bs-primary: #{action}; --bs-primary-rgb: {r},{g},{b}; }}"
        )
        parts.append(
            f".btn-primary {{ background-color: #{action}; border-color: #{action}; }}"
        )
    if valid(link):
        parts.append(f":root {{ --bs-link-color: #{link}; }}")
    return "\n".join(parts)


def _get_client_safe(user_sess, oauth_handler):
    try:
        return get_client_for_session(user_sess, oauth_handler=oauth_handler)
    except Exception:
        return None


def _build_authenticated_shell(branding: "dict | None", user_sess) -> ui.Tag:
    user_name = (
        user_sess.user_info.get("name") or user_sess.user_info.get("sub") or "User"
    )
    logo_url = branding.get("logo_data_url") if branding else None
    return ui.navset_bar(
        *_build_nav_panels(),
        ui.nav_spacer(),
        _build_theme_btn(),
        _build_user_menu(user_name),
        title=_build_navbar_title(logo_url),
        id="navbar",
        bg=SP_NAV_BG,
        inverse=True,
    )


# ---------------------------------------------------------------------------
# App UI (static shell)
# ---------------------------------------------------------------------------

app_ui = ui.page_fluid(
    ui.head_content(
        ui.tags.link(rel="stylesheet", href=_FA_CDN),
        ui.tags.script(_DARK_MODE_JS),
    ),
    ui.include_css(_CSS_PATH),
    ui.output_ui("branding_style"),
    ui.output_ui("main"),
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


def server(input, output, session):
    _error_param: str = session.http_conn.query_params.get("error", "")

    # None = not yet fetched; {} = fetched, no branding; {...} = branding available.
    _branding: reactive.Value[dict | None] = reactive.Value(None)
    _custom_colors: reactive.Value[dict] = reactive.Value({})

    @reactive.calc
    def _user_session():
        session_id = session.http_conn.cookies.get("session_id")
        if not session_id:
            logger.debug("No session cookie present")
            return None
        sess = get_session_manager().get_session(session_id)
        if sess:
            logger.debug("Active session for user=%s", sess.user_info.get("sub", "?"))
        return sess

    @reactive.calc
    def _isc_client():
        user_sess = _user_session()
        if user_sess is None:
            return None
        logger.debug(
            "Creating ISC client for user=%s", user_sess.user_info.get("sub", "?")
        )
        return _get_client_safe(user_sess, _get_oauth_handler())

    @reactive.effect
    def _fetch_branding():
        c = _isc_client()
        if c is None:
            return
        logger.debug("Fetching tenant branding")
        try:
            result = c.get_branding()
            _branding.set(result)
            logger.debug(
                "Branding fetched: keys=%s", list(result.keys()) if result else []
            )
        except Exception:
            logger.debug("Branding fetch failed")
            _branding.set({})

    nav_trigger = component_selector_server(
        "settings",
        registry=registry,
        branding=_branding,
        custom_colors=_custom_colors,
    )

    @output
    @render.ui
    def branding_style():
        css = _build_custom_css(_custom_colors.get())
        return ui.tags.style(css) if css else ui.div()

    _active_tab: reactive.Value[str] = reactive.Value("Home")

    @reactive.effect
    def _track_active_tab():
        tab = input.navbar()
        if tab:
            _active_tab.set(tab)

    @output
    @render.ui
    def main():
        nav_trigger()
        user_sess = _user_session()
        if user_sess is None:
            return login_ui("login")
        return _build_authenticated_shell(_branding.get(), user_sess)

    @reactive.effect
    @reactive.event(nav_trigger)
    def _restore_active_tab():
        with reactive.isolate():
            tab = _active_tab.get()
        ui.update_navset("navbar", selected=tab, session=session)

    login_server("login", error_param=_error_param)
    home_server(
        "home", user_session=_user_session, client=_isc_client, registry=registry
    )
    identities_server("identities", client=_isc_client)
    accounts_server("accounts", client=_isc_client)
    search_server("search", client=_isc_client)


app = App(app_ui, server)

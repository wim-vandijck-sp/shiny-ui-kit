from shiny import module, render, ui

from ui.theme import APP_TITLE

ERROR_MESSAGES: dict[str, str] = {
    "oauth_failed": "Authentication failed. Please try again.",
    "invalid_state": "Security validation failed. Please try again.",
    "token_exchange_failed": "Could not complete login. Please try again.",
}


@module.ui
def login_ui() -> ui.Tag:
    return ui.div(
        ui.div(
            ui.div(
                ui.div(
                    ui.tags.i(class_="fa-solid fa-shield-halved fa-2x text-primary mb-3"),
                    class_="text-center",
                ),
                ui.h2(APP_TITLE, class_="mb-1"),
                ui.p(
                    "Sign in with your SailPoint Identity Security Cloud credentials.",
                    class_="text-muted mb-4",
                ),
                ui.output_ui("error_banner"),
                ui.tags.a(
                    ui.tags.i(class_="fa-solid fa-right-to-bracket me-2"),
                    "Login with SailPoint",
                    href="/api/auth/login",
                    class_="btn btn-primary btn-lg w-100",
                ),
                class_="card-body p-4 text-center",
            ),
            class_="card shadow",
        ),
        class_="login-page",
    )


@module.server
def login_server(input, output, session, *, error_param: str = "") -> None:
    @output
    @render.ui
    def error_banner() -> ui.Tag:
        if not error_param:
            return ui.div()
        msg = ERROR_MESSAGES.get(error_param, "An unexpected error occurred. Please try again.")
        return ui.div(
            ui.tags.i(class_="fa-solid fa-circle-exclamation me-2"),
            msg,
            class_="alert alert-danger d-flex align-items-center mb-3",
            role="alert",
        )

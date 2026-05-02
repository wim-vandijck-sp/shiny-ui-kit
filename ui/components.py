from shiny import ui


def spinner_tag() -> ui.Tag:
    return ui.div(class_="sp-spinner")


def loading_spinner(output_id: str) -> ui.Tag:
    return ui.div(
        ui.output_ui(output_id),
        class_="loading-container",
    )


def error_alert(message: str) -> ui.Tag:
    return ui.div(
        ui.tags.i(class_="fa-solid fa-circle-exclamation me-2"),
        message,
        class_="alert alert-danger d-flex align-items-center",
    )


def empty_state(message: str = "No data available", icon: str = "fa-inbox") -> ui.Tag:
    return ui.div(
        ui.tags.i(class_=f"fa-solid {icon} empty-icon"),
        ui.p(message, class_="text-muted mb-0 small"),
        class_="empty-state py-5",
    )

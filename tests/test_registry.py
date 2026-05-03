import json
from pathlib import Path

import pytest

from components.registry import ComponentInfo, ComponentRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    """Return a config path inside tmp_path — no file created yet."""
    return tmp_path / "config" / "config.json"


@pytest.fixture
def registry(cfg: Path) -> ComponentRegistry:
    r = ComponentRegistry(config_path=cfg)
    r.register(
        ComponentInfo(
            name="identities", label="Identities", description="View identities"
        )
    )
    r.register(
        ComponentInfo(name="accounts", label="Accounts", description="View accounts")
    )
    return r


# ---------------------------------------------------------------------------
# Basic registration
# ---------------------------------------------------------------------------


def test_register_and_get_all(registry: ComponentRegistry) -> None:
    assert len(registry.get_all()) == 2


def test_get_returns_component(registry: ComponentRegistry) -> None:
    comp = registry.get("identities")
    assert comp is not None
    assert comp.name == "identities"


def test_get_unknown_returns_none(registry: ComponentRegistry) -> None:
    assert registry.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------


def test_get_enabled_all_by_default(registry: ComponentRegistry) -> None:
    assert len(registry.get_enabled()) == 2


def test_disable_removes_from_enabled(registry: ComponentRegistry) -> None:
    registry.disable("identities")
    enabled_names = [c.name for c in registry.get_enabled()]
    assert "identities" not in enabled_names
    assert "accounts" in enabled_names


def test_enable_restores_component(registry: ComponentRegistry) -> None:
    registry.disable("identities")
    registry.enable("identities")
    enabled_names = [c.name for c in registry.get_enabled()]
    assert "identities" in enabled_names


def test_disable_nonexistent_is_silent(registry: ComponentRegistry) -> None:
    registry.disable("nonexistent")  # must not raise


def test_enable_nonexistent_is_silent(registry: ComponentRegistry) -> None:
    registry.enable("nonexistent")  # must not raise


# ---------------------------------------------------------------------------
# Toggle
# ---------------------------------------------------------------------------


def test_toggle_disables_enabled_component(registry: ComponentRegistry) -> None:
    registry.toggle("identities")
    assert registry.get("identities").enabled is False


def test_toggle_enables_disabled_component(registry: ComponentRegistry) -> None:
    registry.disable("identities")
    registry.toggle("identities")
    assert registry.get("identities").enabled is True


def test_toggle_nonexistent_is_silent(registry: ComponentRegistry) -> None:
    registry.toggle("nonexistent")  # must not raise


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------


def test_disable_writes_config(registry: ComponentRegistry, cfg: Path) -> None:
    registry.disable("identities")
    assert cfg.exists()
    data = json.loads(cfg.read_text())
    assert data["components"]["identities"]["enabled"] is False
    assert data["components"]["accounts"]["enabled"] is True


def test_toggle_writes_config(registry: ComponentRegistry, cfg: Path) -> None:
    registry.toggle("identities")
    assert cfg.exists()
    data = json.loads(cfg.read_text())
    assert data["components"]["identities"]["enabled"] is False


def test_enable_updates_config(registry: ComponentRegistry, cfg: Path) -> None:
    registry.disable("identities")
    registry.enable("identities")
    data = json.loads(cfg.read_text())
    assert data["components"]["identities"]["enabled"] is True


def test_persisted_state_restored_on_new_instance(
    registry: ComponentRegistry, cfg: Path
) -> None:
    """Persisted disabled state must be applied when register() is called."""
    registry.disable("identities")

    r2 = ComponentRegistry(config_path=cfg)
    r2.register(
        ComponentInfo(
            name="identities", label="Identities", description="View identities"
        )
    )
    r2.register(
        ComponentInfo(name="accounts", label="Accounts", description="View accounts")
    )

    assert r2.get("identities").enabled is False
    assert r2.get("accounts").enabled is True


def test_config_directory_auto_created(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "config.json"
    r = ComponentRegistry(config_path=nested)
    r.register(ComponentInfo(name="x", label="X", description="desc"))
    r.disable("x")
    assert nested.exists()


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_missing_config_file_handled_gracefully(tmp_path: Path) -> None:
    r = ComponentRegistry(config_path=tmp_path / "missing.json")
    r.register(ComponentInfo(name="x", label="X", description="desc"))
    assert r.get("x").enabled is True  # defaults to enabled


def test_malformed_json_handled_gracefully(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("not valid json{{{")
    r = ComponentRegistry(config_path=cfg)
    r.register(ComponentInfo(name="x", label="X", description="desc"))
    assert r.get("x").enabled is True  # defaults to enabled, no crash


@pytest.mark.parametrize("name", ["identities", "accounts"])
def test_toggle_is_idempotent_after_two_calls(
    registry: ComponentRegistry, name: str
) -> None:
    original = registry.get(name).enabled
    registry.toggle(name)
    registry.toggle(name)
    assert registry.get(name).enabled == original

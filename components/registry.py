import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.json"


@dataclass
class ComponentInfo:
    name: str
    label: str
    description: str
    icon: str = "grid"
    enabled: bool = True


class ComponentRegistry:
    """Registry of pluggable UI components with JSON-backed persistence.

    Config is loaded eagerly so persisted enable/disable state is applied
    automatically when each component is registered via :meth:`register`.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._components: dict[str, ComponentInfo] = {}
        self._persisted: dict[str, bool] = {}
        self._load_config()

    def register(self, info: ComponentInfo) -> None:
        """Register a component, restoring its persisted enabled state if present."""
        if info.name in self._persisted:
            info.enabled = self._persisted[info.name]
        self._components[info.name] = info

    def get(self, name: str) -> ComponentInfo | None:
        """Return the component with *name*, or ``None`` if not registered."""
        return self._components.get(name)

    def enable(self, name: str) -> None:
        if name in self._components:
            self._components[name].enabled = True
            self._save_config()

    def disable(self, name: str) -> None:
        if name in self._components:
            self._components[name].enabled = False
            self._save_config()

    def toggle(self, name: str) -> None:
        """Flip the enabled state of the named component."""
        comp = self._components.get(name)
        if comp:
            if comp.enabled:
                self.disable(name)
            else:
                self.enable(name)

    def get_enabled(self) -> list[ComponentInfo]:
        return [c for c in self._components.values() if c.enabled]

    def get_all(self) -> list[ComponentInfo]:
        return list(self._components.values())

    # ------------------------------------------------------------------
    # Internal persistence helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        if not self._config_path.exists():
            return
        try:
            data: dict[str, Any] = json.loads(self._config_path.read_text())
            self._persisted = {
                name: cfg.get("enabled", True)
                for name, cfg in data.get("components", {}).items()
            }
        except (json.JSONDecodeError, OSError):
            pass

    def _save_config(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "components": {
                name: {"enabled": info.enabled}
                for name, info in self._components.items()
            }
        }
        try:
            self._config_path.write_text(json.dumps(data, indent=2))
        except OSError:
            pass

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from .config import WinRMConfig

INVENTORY_VERSION = 1
SCOPES = {"project", "user"}


def inventory_path(scope: str | None = None) -> tuple[Path, str]:
    if scope is None and os.getenv("WINRM_MCP_INVENTORY_FILE"):
        return Path(os.environ["WINRM_MCP_INVENTORY_FILE"]).expanduser().resolve(), "custom"

    selected = (scope or os.getenv("WINRM_MCP_INVENTORY_SCOPE", "user")).strip().lower()
    if selected not in SCOPES:
        raise ValueError("inventory scope must be project or user")
    if selected == "project":
        project_dir = _project_directory()
        return project_dir / ".winrm-mcp" / "inventory.json", selected

    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "winrm-mcp" / "inventory.json", selected


def _project_directory() -> Path:
    configured = os.getenv("WINRM_MCP_PROJECT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    # MCP launchers commonly start their own server process in a temporary
    # runtime directory while preserving the user's logical PWD. Prefer that
    # inherited project context over the subprocess cwd.
    logical_pwd = os.getenv("PWD")
    if logical_pwd:
        candidate = Path(logical_pwd).expanduser().resolve()
        if candidate.is_dir() and not _is_ephemeral_launcher_path(candidate):
            return candidate

    current = Path.cwd().resolve()
    if _is_ephemeral_launcher_path(current):
        raise ValueError(
            "project inventory cannot use an ephemeral DeepAgents runtime directory; "
            "set WINRM_MCP_PROJECT_DIR to the actual project root"
        )
    return current


def _is_ephemeral_launcher_path(path: Path) -> bool:
    return any(part.startswith("deepagents_server_") for part in path.parts)


class InventoryStore:
    """Atomic JSON inventory for reusable WinRM hosts."""

    def __init__(self, scope: str | None = None, path: str | Path | None = None) -> None:
        if path is None:
            self.path, self.scope = inventory_path(scope)
        else:
            self.path = Path(path).expanduser().resolve()
            self.scope = scope or "custom"
        self._lock = RLock()

    def status(self) -> dict[str, Any]:
        with self._lock:
            error: str | None = None
            try:
                count: int | None = len(self._load())
            except Exception as exc:  # noqa: BLE001 - status must describe damaged inventories.
                count = None
                error = f"{type(exc).__name__}: {exc}"
            return {
                "path": str(self.path),
                "scope": self.scope,
                "exists": self.path.exists(),
                "host_count": count,
                "version": INVENTORY_VERSION,
                "load_error": error,
            }

    def initialize(self, *, overwrite: bool = False) -> dict[str, Any]:
        with self._lock:
            if self.path.exists() and not overwrite:
                return {"ok": True, "created": False, **self.status()}
            self._write({})
            return {"ok": True, "created": True, **self.status()}

    def validate(self) -> dict[str, Any]:
        with self._lock:
            try:
                hosts = self._load()
            except Exception as exc:  # noqa: BLE001 - return repairable validation details.
                return {"ok": False, **self.status(), "invalid_hosts": {}, "inventory_error": str(exc)}
            invalid: dict[str, str] = {}
            for name, settings in hosts.items():
                try:
                    WinRMConfig.from_mapping(settings, include_environment=False)
                except Exception as exc:  # noqa: BLE001 - report every malformed host.
                    invalid[name] = f"{type(exc).__name__}: {exc}"
            return {
                "ok": not invalid,
                **self.status(),
                "valid_hosts": sorted(set(hosts) - set(invalid)),
                "invalid_hosts": invalid,
                "inventory_error": None,
            }

    def list_safe(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                name: WinRMConfig.from_mapping(settings, include_environment=False).to_dict(redact=True)
                for name, settings in sorted(self._load().items())
            }

    def get_raw(self, name: str) -> dict[str, Any]:
        clean = _name(name)
        with self._lock:
            hosts = self._load()
            if clean not in hosts:
                raise KeyError(f"host {clean!r} does not exist in the {self.scope} inventory")
            return dict(hosts[clean])

    def get_safe(self, name: str) -> dict[str, Any]:
        return WinRMConfig.from_mapping(self.get_raw(name), include_environment=False).to_dict(redact=True)

    def save(self, name: str, settings: dict[str, Any], *, overwrite: bool = False) -> WinRMConfig:
        clean = _name(name)
        config = WinRMConfig.from_mapping(settings, include_environment=False)
        with self._lock:
            hosts = self._load()
            if clean in hosts and not overwrite:
                raise ValueError(f"host {clean!r} already exists")
            hosts[clean] = config.to_dict()
            self._write(hosts)
        return config

    def update(
        self,
        name: str,
        changes: dict[str, Any],
        *,
        remove_fields: list[str] | None = None,
    ) -> WinRMConfig:
        clean = _name(name)
        with self._lock:
            hosts = self._load()
            if clean not in hosts:
                raise KeyError(f"host {clean!r} does not exist in the {self.scope} inventory")
            updated = {**hosts[clean], **changes}
            for field in remove_fields or []:
                updated.pop(str(field), None)
            config = WinRMConfig.from_mapping(updated, include_environment=False)
            hosts[clean] = config.to_dict()
            self._write(hosts)
            return config

    def delete(self, name: str) -> bool:
        clean = _name(name)
        with self._lock:
            hosts = self._load()
            if clean not in hosts:
                return False
            del hosts[clean]
            self._write(hosts)
            return True

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON inventory {self.path}: {exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("hosts", {}), dict):
            raise TypeError(f"invalid inventory file: {self.path}")
        hosts: dict[str, dict[str, Any]] = {}
        for name, settings in raw.get("hosts", {}).items():
            if not isinstance(name, str) or not isinstance(settings, dict):
                raise TypeError(f"invalid host entry: {name!r}")
            hosts[name] = dict(settings)
        return hosts

    def _write(self, hosts: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="inventory-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": INVENTORY_VERSION, "hosts": hosts}, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _name(name: str) -> str:
    clean = name.strip()
    if not clean:
        raise ValueError("host name is required")
    return clean

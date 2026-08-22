import json
import stat

import pytest

from winrm_mcp.inventory import InventoryStore, inventory_path


def settings(host: str = "win01.example") -> dict[str, object]:
    return {"host": host, "username": "Administrator", "password_env": "WIN01_PASSWORD"}


def test_project_and_user_paths(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("WINRM_MCP_PROJECT_DIR", str(tmp_path / "project"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert inventory_path("project")[0] == tmp_path / "project" / ".winrm-mcp" / "inventory.json"
    assert inventory_path("user")[0] == tmp_path / "config" / "winrm-mcp" / "inventory.json"


def test_project_path_uses_logical_pwd_outside_launcher_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    launcher = tmp_path / "deepagents_server_123"
    launcher.mkdir()
    monkeypatch.delenv("WINRM_MCP_PROJECT_DIR", raising=False)
    monkeypatch.setenv("PWD", str(project))
    monkeypatch.chdir(launcher)
    assert inventory_path("project")[0] == project / ".winrm-mcp" / "inventory.json"


def test_project_path_rejects_ephemeral_launcher_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    launcher = tmp_path / "deepagents_server_123"
    launcher.mkdir()
    monkeypatch.delenv("WINRM_MCP_PROJECT_DIR", raising=False)
    monkeypatch.setenv("PWD", str(launcher))
    monkeypatch.chdir(launcher)
    with pytest.raises(ValueError, match="ephemeral DeepAgents runtime"):
        inventory_path("project")


def test_inventory_crud_redacts_and_writes_atomically(tmp_path) -> None:
    path = tmp_path / "inventory.json"
    store = InventoryStore(path=path)
    assert store.initialize()["created"] is True
    store.save("win01", {**settings(), "password": "secret", "password_env": None})
    assert store.get_safe("win01")["password"] == "***REDACTED***"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    store.update("win01", {"host": "win02.example"}, remove_fields=["password"])
    assert store.get_safe("win01")["host"] == "win02.example"
    assert "password" not in store.get_safe("win01")
    assert store.delete("win01") is True
    assert store.delete("win01") is False


def test_inventory_multiple_hosts_and_validation(tmp_path) -> None:
    store = InventoryStore(path=tmp_path / "inventory.json")
    store.save("win01", settings("win01.example"))
    store.save("win02", settings("win02.example"))
    assert list(store.list_safe()) == ["win01", "win02"]
    assert store.validate()["ok"] is True


def test_inventory_reports_invalid_host(tmp_path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"version": 1, "hosts": {"broken": {"username": "admin"}}}))
    result = InventoryStore(path=path).validate()
    assert result["ok"] is False
    assert "broken" in result["invalid_hosts"]

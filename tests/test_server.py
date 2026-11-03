from typing import Any

import pytest

from winrm_mcp import server
from winrm_mcp.client import CommandResult
from winrm_mcp.server import mcp


def test_server_registers_winrm_and_inventory_tools() -> None:
    tool_manager = mcp._tool_manager
    assert set(tool_manager._tools) == {
        "winrm_policy",
        "winrm_execute_many",
        "winrm_upload",
        "winrm_download",
        "winrm_test",
        "winrm_execute_powershell",
        "winrm_execute_cmd",
        "winrm_inventory_status",
        "winrm_inventory_init",
        "winrm_inventory_validate",
        "winrm_host_list",
        "winrm_host_get",
        "winrm_host_save",
        "winrm_host_update",
        "winrm_host_delete",
    }


@pytest.mark.parametrize("sentinel", ["None", "none", "null", " NULL ", ""])
async def test_connection_string_sentinels_are_normalized_before_tool_call(
    monkeypatch: pytest.MonkeyPatch,
    sentinel: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_resolve(saved_host: str | None, connection: object, inventory_scope: str | None) -> object:
        captured.update(
            saved_host=saved_host,
            connection=connection,
            inventory_scope=inventory_scope,
        )
        return object()

    async def fake_execute(*args: Any, **kwargs: Any) -> CommandResult:
        return CommandResult("host", "powershell", "test", "WINRM_MCP_CONNECTION_OK", "", 0, 0.1, True)

    monkeypatch.setattr(server, "_resolve", fake_resolve)
    monkeypatch.setattr(server, "execute", fake_execute)

    await mcp._tool_manager.call_tool(
        "winrm_test",
        {
            "saved_host": "saved",
            "connection": sentinel,
            "inventory_scope": "project",
            "timeout": 30,
        },
        convert_result=True,
    )

    assert captured == {"saved_host": "saved", "connection": None, "inventory_scope": "project"}


async def test_connection_rejects_other_strings() -> None:
    with pytest.raises(Exception, match="valid dictionary"):
        await mcp._tool_manager.call_tool(
            "winrm_test",
            {"saved_host": "saved", "connection": "not-a-connection", "inventory_scope": "project"},
        )


def test_every_tool_is_annotated() -> None:
    for name, tool in mcp._tool_manager._tools.items():
        assert tool.annotations is not None and tool.annotations.readOnlyHint is not None, name
    tools = mcp._tool_manager._tools
    assert tools["winrm_execute_powershell"].annotations.destructiveHint is True
    assert tools["winrm_host_list"].annotations.readOnlyHint is True


async def test_execute_many_reports_each_host(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from winrm_mcp.inventory import InventoryStore

    store = InventoryStore(path=tmp_path / "inventory.json")
    for name in ("web1", "web2", "db1"):
        store.save(
            name,
            {
                "host": f"{name}.example",
                "username": "u",
                "password_env": "X_PASSWORD",
                "tags": ["web"] if name.startswith("web") else ["db"],
            },
        )
    monkeypatch.setattr(server, "_store", lambda scope: store)
    monkeypatch.setenv("X_PASSWORD", "secret")

    async def fake_execute(config: Any, command: str, **kwargs: Any) -> CommandResult:
        if config.host == "web2.example":
            raise ConnectionError("unreachable")
        return CommandResult(config.host, "powershell", command, "ok", "", 0, 0.1, True)

    monkeypatch.setattr(server, "execute", fake_execute)
    result = await server.winrm_execute_many("hostname", tag="web")
    assert (result["hosts"], result["succeeded"], result["failed"]) == (2, 1, 1)
    assert {r["saved_host"]: r["ok"] for r in result["results"]} == {"web1": True, "web2": False}
    assert "unreachable" in next(r for r in result["results"] if not r["ok"])["error"]

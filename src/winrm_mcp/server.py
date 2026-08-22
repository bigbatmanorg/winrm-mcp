from __future__ import annotations

import os
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import BeforeValidator

from .client import execute
from .config import WinRMConfig
from .inventory import InventoryStore


def _normalize_optional_connection(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
        return None
    return value


ConnectionInput = Annotated[
    dict[str, Any] | None,
    BeforeValidator(_normalize_optional_connection),
]

mcp = FastMCP(
    "WinRM",
    instructions=(
        "Execute PowerShell or CMD commands on Windows hosts over WinRM. "
        "Use a saved host from a project/user inventory, pass an ad-hoc connection object, "
        "or configure WINRM_MCP_* environment defaults."
    ),
    host=os.getenv("WINRM_MCP_SERVER_HOST", "127.0.0.1"),
    port=int(os.getenv("WINRM_MCP_SERVER_PORT", "8765")),
    json_response=True,
)


def _store(scope: str | None) -> InventoryStore:
    return InventoryStore(scope=scope)


def _resolve(
    saved_host: str | None,
    connection: dict[str, Any] | None,
    inventory_scope: str | None,
) -> WinRMConfig:
    stored = _store(inventory_scope).get_raw(saved_host) if saved_host else None
    return WinRMConfig.from_sources(
        stored,
        connection,
        include_environment=stored is None,
    )


@mcp.tool()
def winrm_inventory_status(scope: str | None = None) -> dict[str, Any]:
    """Show the project or user inventory path, existence, and saved host count."""
    return _store(scope).status()


@mcp.tool()
def winrm_inventory_init(scope: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Create an empty project or user inventory without replacing existing data by default."""
    return _store(scope).initialize(overwrite=overwrite)


@mcp.tool()
def winrm_inventory_validate(scope: str | None = None) -> dict[str, Any]:
    """Validate an inventory file and every saved WinRM host."""
    return _store(scope).validate()


@mcp.tool()
def winrm_host_list(scope: str | None = None) -> dict[str, Any]:
    """List saved WinRM hosts with passwords redacted."""
    store = _store(scope)
    return {"path": str(store.path), "scope": store.scope, "hosts": store.list_safe()}


@mcp.tool()
def winrm_host_get(name: str, scope: str | None = None) -> dict[str, Any]:
    """Get one saved WinRM host with its password redacted."""
    store = _store(scope)
    return {"name": name, "scope": store.scope, "settings": store.get_safe(name)}


@mcp.tool()
def winrm_host_save(
    name: str,
    settings: dict[str, Any],
    scope: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Save a WinRM host in the project or user inventory. Prefer password_env over password."""
    store = _store(scope)
    config = store.save(name, settings, overwrite=overwrite)
    return {
        "ok": True,
        "name": name,
        "scope": store.scope,
        "path": str(store.path),
        "settings": config.to_dict(redact=True),
        "warning": "an inline password was stored in the protected inventory file"
        if settings.get("password") is not None
        else None,
    }


@mcp.tool()
def winrm_host_update(
    name: str,
    changes: dict[str, Any],
    scope: str | None = None,
    remove_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Update selected settings on a saved host; remove optional values with remove_fields."""
    store = _store(scope)
    config = store.update(name, changes, remove_fields=remove_fields)
    return {"ok": True, "name": name, "scope": store.scope, "settings": config.to_dict(redact=True)}


@mcp.tool()
def winrm_host_delete(name: str, scope: str | None = None) -> dict[str, Any]:
    """Delete a saved WinRM host."""
    store = _store(scope)
    return {"ok": store.delete(name), "name": name, "scope": store.scope}


@mcp.tool()
async def winrm_test(
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    """Test a WinRM connection with a harmless PowerShell marker command."""
    config = _resolve(saved_host, connection, inventory_scope)
    result = await execute(config, "Write-Output 'WINRM_MCP_CONNECTION_OK'", shell="powershell", timeout=timeout)
    payload = result.to_dict()
    payload["connection_ok"] = result.ok and "WINRM_MCP_CONNECTION_OK" in result.stdout
    return payload


@mcp.tool()
async def winrm_execute_powershell(
    command: str,
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
    timeout: float = 300,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    output_limit: int = 200_000,
) -> dict[str, Any]:
    """Execute a PowerShell command over WinRM and return stdout, stderr, and exit code."""
    config = _resolve(saved_host, connection, inventory_scope)
    result = await execute(config, command, shell="powershell", timeout=timeout, cwd=cwd, env=env)
    return result.to_dict(output_limit=output_limit)


@mcp.tool()
async def winrm_execute_cmd(
    command: str,
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
    timeout: float = 300,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    output_limit: int = 200_000,
) -> dict[str, Any]:
    """Execute a CMD command over WinRM and return stdout, stderr, and exit code."""
    config = _resolve(saved_host, connection, inventory_scope)
    result = await execute(config, command, shell="cmd", timeout=timeout, cwd=cwd, env=env)
    return result.to_dict(output_limit=output_limit)


def main() -> None:
    transport = os.getenv("WINRM_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise SystemExit("WINRM_MCP_TRANSPORT must be stdio, streamable-http, or sse")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()

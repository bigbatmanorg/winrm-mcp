from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BeforeValidator

from . import __version__
from .client import copy_to_remote, execute, fetch_from_remote
from .config import WinRMConfig
from .inventory import InventoryStore
from .policy import Policy


def _normalize_optional_connection(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
        return None
    return value


ConnectionInput = Annotated[
    dict[str, Any] | None,
    BeforeValidator(_normalize_optional_connection),
]

# MCP annotations let clients decide which calls need user confirmation.
LOCAL_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
LOCAL_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
LOCAL_DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)
REMOTE_PROBE = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
# Remote commands can do anything the account may do, so they are treated as destructive.
REMOTE_EXEC = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
)

mcp = FastMCP(
    "WinRM",
    instructions=(
        "Execute PowerShell or CMD commands on Windows hosts over WinRM. "
        "Use a saved host from a project/user inventory, pass an ad-hoc connection object, "
        "or configure WINRM_MCP_* environment defaults. Commands run with the remote account's "
        "full rights; confirm destructive actions with the user first. Use output_format='json' "
        "for structured PowerShell results and winrm_execute_many for several saved hosts. "
        "Call winrm_policy to see which hosts, secrets and file transfers the operator allows."
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
    policy = Policy.from_environment()
    policy.check_overrides(connection, saved_host=bool(saved_host))
    stored = _store(inventory_scope).get_raw(saved_host) if saved_host else None
    config = WinRMConfig.from_sources(
        stored,
        connection,
        include_environment=stored is None,
    )
    return policy.check(config)


@mcp.tool(annotations=LOCAL_READ)
def winrm_policy() -> dict[str, Any]:
    """Show the server version and the operator's security policy: allowed hosts, whether ad-hoc connections are allowed, which environment variables password_env may read, and whether file transfer is enabled."""
    return {"version": __version__, **Policy.from_environment().summary()}


@mcp.tool(annotations=LOCAL_READ)
def winrm_inventory_status(scope: str | None = None) -> dict[str, Any]:
    """Show the project or user inventory path, existence, and saved host count."""
    return _store(scope).status()


@mcp.tool(annotations=LOCAL_WRITE)
def winrm_inventory_init(scope: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Create an empty project or user inventory without replacing existing data by default."""
    return _store(scope).initialize(overwrite=overwrite)


@mcp.tool(annotations=LOCAL_READ)
def winrm_inventory_validate(scope: str | None = None) -> dict[str, Any]:
    """Validate an inventory file and every saved WinRM host."""
    return _store(scope).validate()


@mcp.tool(annotations=LOCAL_READ)
def winrm_host_list(scope: str | None = None, tag: str | None = None) -> dict[str, Any]:
    """List saved WinRM hosts with passwords redacted; optionally only hosts carrying a tag."""
    store = _store(scope)
    hosts = store.list_safe()
    if tag:
        hosts = {name: settings for name, settings in hosts.items() if tag in (settings.get("tags") or [])}
    return {"path": str(store.path), "scope": store.scope, "hosts": hosts}


@mcp.tool(annotations=LOCAL_READ)
def winrm_host_get(name: str, scope: str | None = None) -> dict[str, Any]:
    """Get one saved WinRM host with its password redacted."""
    store = _store(scope)
    return {"name": name, "scope": store.scope, "settings": store.get_safe(name)}


@mcp.tool(annotations=LOCAL_WRITE)
def winrm_host_save(
    name: str,
    settings: dict[str, Any],
    scope: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Save a WinRM host in the project or user inventory. Prefer password_env over password; tags (a list of strings) group hosts for winrm_execute_many."""
    store = _store(scope)
    Policy.from_environment().check(WinRMConfig.from_mapping(settings, include_environment=False))
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


@mcp.tool(annotations=LOCAL_WRITE)
def winrm_host_update(
    name: str,
    changes: dict[str, Any],
    scope: str | None = None,
    remove_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Update selected settings on a saved host; remove optional values with remove_fields."""
    store = _store(scope)
    config = store.update(name, changes, remove_fields=remove_fields)
    Policy.from_environment().check(config)
    return {"ok": True, "name": name, "scope": store.scope, "settings": config.to_dict(redact=True)}


@mcp.tool(annotations=LOCAL_DELETE)
def winrm_host_delete(name: str, scope: str | None = None) -> dict[str, Any]:
    """Delete a saved WinRM host."""
    store = _store(scope)
    return {"ok": store.delete(name), "name": name, "scope": store.scope}


@mcp.tool(annotations=REMOTE_PROBE)
async def winrm_test(
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    """Test a WinRM connection with a harmless PowerShell marker command; reports whether the account is a local administrator."""
    config = _resolve(saved_host, connection, inventory_scope)
    probe = (
        "Write-Output 'WINRM_MCP_CONNECTION_OK'; "
        "Write-Output ('ADMIN=' + ([Security.Principal.WindowsPrincipal]"
        "[Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators'))"
    )
    result = await execute(config, probe, shell="powershell", timeout=timeout)
    payload = result.to_dict()
    payload["connection_ok"] = result.ok and "WINRM_MCP_CONNECTION_OK" in result.stdout
    payload["is_admin"] = "ADMIN=True" in result.stdout
    return payload


@mcp.tool(annotations=REMOTE_EXEC)
async def winrm_execute_powershell(
    command: str,
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
    timeout: float = 300,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    output_limit: int = 200_000,
    output_format: str = "text",
) -> dict[str, Any]:
    """Execute PowerShell over WinRM and return stdout, stderr (error/warning/verbose streams) and the exit code, including `exit N`. On timeout the remote command is stopped. output_format='json' converts the output objects with ConvertTo-Json and returns them parsed in `data`."""
    config = _resolve(saved_host, connection, inventory_scope)
    result = await execute(
        config, command, shell="powershell", timeout=timeout, cwd=cwd, env=env, output_format=output_format
    )
    return result.to_dict(output_limit=output_limit)


@mcp.tool(annotations=REMOTE_EXEC)
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
    """Execute a CMD command over WinRM and return stdout, stderr, and exit code. env sets real process environment variables (usable as %NAME%). On timeout the remote process is terminated."""
    config = _resolve(saved_host, connection, inventory_scope)
    result = await execute(config, command, shell="cmd", timeout=timeout, cwd=cwd, env=env)
    return result.to_dict(output_limit=output_limit)


@mcp.tool(annotations=REMOTE_EXEC)
async def winrm_execute_many(
    command: str,
    saved_hosts: list[str] | None = None,
    tag: str | None = None,
    shell: str = "powershell",
    inventory_scope: str | None = None,
    timeout: float = 300,
    max_parallel: int = 5,
    output_limit: int = 20_000,
    output_format: str = "text",
) -> dict[str, Any]:
    """Run one command on several saved hosts (listed by name and/or selected by tag) in parallel. Returns one result or error per host, so one unreachable host does not hide the others."""
    if shell not in {"powershell", "cmd"}:
        raise ValueError("shell must be powershell or cmd")
    names = list(dict.fromkeys(saved_hosts or []))
    if tag:
        tagged = _store(inventory_scope).list_safe()
        names += [
            name
            for name, settings in tagged.items()
            if tag in (settings.get("tags") or []) and name not in names
        ]
    if not names:
        raise ValueError("no hosts selected; pass saved_hosts and/or a tag that matches saved hosts")
    limit = asyncio.Semaphore(max(1, min(int(max_parallel), 20)))

    async def run(name: str) -> dict[str, Any]:
        async with limit:
            try:
                config = _resolve(name, None, inventory_scope)
                result = await execute(
                    config, command, shell=shell, timeout=timeout, output_format=output_format
                )
                return {"saved_host": name, **result.to_dict(output_limit=output_limit)}
            except Exception as exc:  # noqa: BLE001 - one host's failure is reported, not raised.
                return {"saved_host": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    results = await asyncio.gather(*(run(name) for name in names))
    return {
        "hosts": len(results),
        "succeeded": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }


@mcp.tool(annotations=REMOTE_EXEC)
async def winrm_upload(
    local_path: str,
    remote_path: str,
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
) -> dict[str, Any]:
    """Copy a local file to the Windows host. local_path is relative to WINRM_MCP_LOCAL_ROOT (file transfer is disabled unless the operator sets it); remote_path is a full Windows path."""
    policy = Policy.from_environment()
    source = Path(policy.local_path(local_path, must_exist=True))
    config = _resolve(saved_host, connection, inventory_scope)
    written = await asyncio.to_thread(copy_to_remote, config, source, remote_path)
    return {"ok": True, "local_path": str(source), "remote_path": written, "bytes": source.stat().st_size}


@mcp.tool(annotations=REMOTE_EXEC)
async def winrm_download(
    remote_path: str,
    local_path: str,
    saved_host: str | None = None,
    connection: ConnectionInput = None,
    inventory_scope: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy a file from the Windows host to WINRM_MCP_LOCAL_ROOT/local_path (file transfer is disabled unless the operator sets it). Existing local files are kept unless overwrite=true."""
    policy = Policy.from_environment()
    destination = Path(policy.local_path(local_path, must_exist=False))
    if destination.exists() and not overwrite:
        raise FileExistsError(f"{local_path!r} already exists; pass overwrite=true to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    config = _resolve(saved_host, connection, inventory_scope)
    await asyncio.to_thread(fetch_from_remote, config, remote_path, destination)
    return {
        "ok": True,
        "remote_path": remote_path,
        "local_path": str(destination),
        "bytes": destination.stat().st_size,
    }


def main() -> None:
    transport = os.getenv("WINRM_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise SystemExit("WINRM_MCP_TRANSPORT must be stdio, streamable-http, or sse")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()

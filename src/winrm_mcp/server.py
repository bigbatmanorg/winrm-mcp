from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import execute
from .config import WinRMConfig

mcp = FastMCP(
    "WinRM",
    instructions=(
        "Execute PowerShell or CMD commands on Windows hosts over WinRM. "
        "Pass a connection object per call or configure WINRM_MCP_* environment defaults."
    ),
    host=os.getenv("WINRM_MCP_SERVER_HOST", "127.0.0.1"),
    port=int(os.getenv("WINRM_MCP_SERVER_PORT", "8765")),
    json_response=True,
)


@mcp.tool()
async def winrm_test(connection: dict[str, Any] | None = None, timeout: float = 30) -> dict[str, Any]:
    """Test a WinRM connection with a harmless PowerShell marker command."""
    config = WinRMConfig.from_mapping(connection)
    result = await execute(config, "Write-Output 'WINRM_MCP_CONNECTION_OK'", shell="powershell", timeout=timeout)
    payload = result.to_dict()
    payload["connection_ok"] = result.ok and "WINRM_MCP_CONNECTION_OK" in result.stdout
    return payload


@mcp.tool()
async def winrm_execute_powershell(
    command: str,
    connection: dict[str, Any] | None = None,
    timeout: float = 300,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    output_limit: int = 200_000,
) -> dict[str, Any]:
    """Execute a PowerShell command over WinRM and return stdout, stderr, and exit code."""
    config = WinRMConfig.from_mapping(connection)
    result = await execute(config, command, shell="powershell", timeout=timeout, cwd=cwd, env=env)
    return result.to_dict(output_limit=output_limit)


@mcp.tool()
async def winrm_execute_cmd(
    command: str,
    connection: dict[str, Any] | None = None,
    timeout: float = 300,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    output_limit: int = 200_000,
) -> dict[str, Any]:
    """Execute a CMD command over WinRM and return stdout, stderr, and exit code."""
    config = WinRMConfig.from_mapping(connection)
    result = await execute(config, command, shell="cmd", timeout=timeout, cwd=cwd, env=env)
    return result.to_dict(output_limit=output_limit)


def main() -> None:
    transport = os.getenv("WINRM_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise SystemExit("WINRM_MCP_TRANSPORT must be stdio, streamable-http, or sse")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()


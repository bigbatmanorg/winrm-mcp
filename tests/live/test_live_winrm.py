"""Live end-to-end tests through the real MCP stdio server against a Windows host.

Opt-in: set WINRM_LIVE=1 and WINRM_TEST_HOST, WINRM_TEST_ADMIN_USER, WINRM_TEST_ADMIN_PASSWORD,
WINRM_TEST_USER, WINRM_TEST_USER_PASSWORD (for example from a gitignored .env). The admin and
non-admin accounts must be allowed to use WinRM; HTTPS may use a self-signed certificate.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.skipif(
    os.getenv("WINRM_LIVE") != "1", reason="set WINRM_LIVE=1 for live WinRM tests"
)

HOST = os.getenv("WINRM_TEST_HOST", "")


def admin(**extra):
    return {
        "host": HOST,
        "username": os.getenv("WINRM_TEST_ADMIN_USER"),
        "password_env": "WINRM_TEST_ADMIN_PASSWORD",
        "auth": "ntlm",
        "ssl": True,
        "cert_validation": False,
        **extra,
    }


def user(**extra):
    return admin(username=os.getenv("WINRM_TEST_USER"), password_env="WINRM_TEST_USER_PASSWORD", **extra)


@asynccontextmanager
async def server(tmp_path: Path, **env: str):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "winrm_mcp"],
        env={
            **os.environ,
            "WINRM_MCP_PROJECT_DIR": str(tmp_path),
            "WINRM_MCP_INVENTORY_SCOPE": "project",
            **env,
        },
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        yield session


async def call(session: ClientSession, tool: str, **arguments):
    result = await session.call_tool(tool, arguments)
    text = result.content[0].text if result.content else ""
    if result.isError:
        return {"__error__": text}
    return json.loads(text)


async def test_connectivity_admin_rights_and_transports(tmp_path):
    async with server(tmp_path) as s:
        https_admin = await call(s, "winrm_test", connection=admin())
        assert https_admin["connection_ok"] and https_admin["is_admin"] is True
        https_user = await call(s, "winrm_test", connection=user())
        assert https_user["connection_ok"] and https_user["is_admin"] is False
        http_ntlm = await call(s, "winrm_test", connection=admin(ssl=False))
        assert http_ntlm["connection_ok"], "NTLM over HTTP uses message encryption"
        basic_https = await call(s, "winrm_test", connection=admin(auth="basic"))
        assert basic_https["connection_ok"]
        basic_http = await call(s, "winrm_test", connection=admin(auth="basic", ssl=False))
        assert "unencrypted" in basic_http["__error__"]


async def test_exit_codes_json_and_cmd_env(tmp_path):
    async with server(tmp_path) as s:
        exited = await call(
            s, "winrm_execute_powershell", connection=admin(), command="Write-Output before; exit 3"
        )
        assert (exited["exit_code"], exited["ok"], exited["stdout"]) == (3, False, "before")
        native = await call(s, "winrm_execute_powershell", connection=admin(), command="cmd /c exit 7")
        assert native["exit_code"] == 7
        failing = await call(
            s, "winrm_execute_powershell", connection=admin(), command="Get-Item C:\\does-not-exist-mcp"
        )
        assert failing["ok"] is False and "[error]" in failing["stderr"]
        services = await call(
            s,
            "winrm_execute_powershell",
            connection=admin(),
            output_format="json",
            command="Get-Service -Name WinRM, W32Time | Select-Object Name, Status",
        )
        assert {svc["Name"] for svc in services["data"]} == {"WinRM", "W32Time"}
        cmd = await call(
            s,
            "winrm_execute_cmd",
            connection=admin(),
            command="echo %MCP_MODE% & exit /b 4",
            env={"MCP_MODE": "live-ok"},
        )
        assert cmd["stdout"].strip() == "live-ok" and cmd["exit_code"] == 4
        cwd = await call(s, "winrm_execute_cmd", connection=admin(), command="cd", cwd="C:\\Windows\\Temp")
        assert cwd["stdout"].strip().lower() == "c:\\windows\\temp"


@pytest.mark.parametrize("shell", ["powershell", "cmd"])
async def test_timeout_stops_the_remote_command(tmp_path, shell):
    proof = f"C:\\Windows\\Temp\\mcp-timeout-{uuid.uuid4().hex}.txt"
    slow = (
        f"Start-Sleep 8; Set-Content {proof} late"
        if shell == "powershell"
        else f"ping -n 9 127.0.0.1 >nul & echo late> {proof}"
    )
    async with server(tmp_path) as s:
        started = time.monotonic()
        timed_out = await call(s, f"winrm_execute_{shell}", connection=admin(), command=slow, timeout=3)
        assert "timeout" in timed_out["__error__"].lower() and time.monotonic() - started < 20
        time.sleep(9)
        check = await call(
            s,
            "winrm_execute_powershell",
            connection=admin(),
            command=f"Test-Path {proof}; Remove-Item -Force -ErrorAction SilentlyContinue {proof}",
        )
        assert check["stdout"].strip() == "False", "the remote command kept running after the timeout"


async def test_file_transfer_round_trip_and_confinement(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    payload = ("mcp transfer test " * 4000).encode()
    (root / "up.txt").write_bytes(payload)
    remote = f"C:\\Windows\\Temp\\mcp-transfer-{uuid.uuid4().hex}.txt"
    async with server(tmp_path, WINRM_MCP_LOCAL_ROOT=str(root)) as s:
        up = await call(s, "winrm_upload", connection=admin(), local_path="up.txt", remote_path=remote)
        assert up["ok"] and up["bytes"] == len(payload)
        down = await call(
            s, "winrm_download", connection=admin(), remote_path=remote, local_path="back/down.txt"
        )
        assert (root / "back" / "down.txt").read_bytes() == payload and down["bytes"] == len(payload)
        again = await call(
            s, "winrm_download", connection=admin(), remote_path=remote, local_path="back/down.txt"
        )
        assert "already exists" in again["__error__"]
        escape = await call(
            s, "winrm_upload", connection=admin(), local_path="../../etc/passwd", remote_path=remote
        )
        assert "outside" in escape["__error__"]
        await call(s, "winrm_execute_powershell", connection=admin(), command=f"Remove-Item -Force {remote}")
    async with server(tmp_path) as s:
        disabled = await call(s, "winrm_upload", connection=admin(), local_path="up.txt", remote_path=remote)
        assert "file transfer is disabled" in disabled["__error__"]


async def test_inventory_tags_execute_many_and_policy(tmp_path):
    async with server(tmp_path) as s:
        await call(s, "winrm_inventory_init")
        await call(s, "winrm_host_save", name="lab-admin", settings=admin(tags=["lab"]))
        await call(s, "winrm_host_save", name="lab-user", settings=user(tags=["lab"]))
        await call(
            s,
            "winrm_host_save",
            name="lab-broken",
            settings=admin(tags=["lab"], host="no-such-host.invalid", connect_timeout=5),
        )
        tagged = await call(s, "winrm_host_list", tag="lab")
        assert set(tagged["hosts"]) == {"lab-admin", "lab-user", "lab-broken"}
        many = await call(s, "winrm_execute_many", tag="lab", command="$env:USERNAME", timeout=60)
        by_host = {r["saved_host"]: r for r in many["results"]}
        assert (
            by_host["lab-admin"]["stdout"].strip().lower() == os.getenv("WINRM_TEST_ADMIN_USER", "").lower()
        )
        assert by_host["lab-user"]["stdout"].strip().lower() == os.getenv("WINRM_TEST_USER", "").lower()
        assert by_host["lab-broken"]["ok"] is False and many["succeeded"] == 2
    async with server(
        tmp_path, WINRM_MCP_ALLOWED_HOSTS="allowed-only.example", WINRM_MCP_ALLOW_ADHOC="false"
    ) as s:
        policy = await call(s, "winrm_policy")
        assert policy["allow_adhoc"] is False and policy["allowed_hosts"] == ["allowed-only.example"]
        blocked = await call(s, "winrm_test", saved_host="lab-admin")
        assert "not allowed" in blocked["__error__"]
        adhoc = await call(s, "winrm_test", connection=admin())
        assert "ad-hoc connections are disabled" in adhoc["__error__"]
        exfil = await call(s, "winrm_host_save", name="x", settings=admin(password_env="HOME"))
        assert "SECRET_ENV_PATTERNS" in exfil["__error__"] or "not allowed" in exfil["__error__"]

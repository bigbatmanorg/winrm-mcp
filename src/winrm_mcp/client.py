from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pypsrp.client import Client
from pypsrp.host import PSHost
from pypsrp.powershell import PowerShell, PSInvocationState, RunspacePool
from pypsrp.shell import CommandState, Process, SignalCode, WinRS
from pypsrp.wsman import WSMan

from .config import WinRMConfig

EXIT_MARKER = "__WINRM_MCP_EXIT_CODE__="
# Seconds per WSMan receive call. Short polls let a deadline stop the remote command promptly.
POLL_SECONDS = 2
# Extra seconds the worker thread gets after the deadline to stop the remote command cleanly.
STOP_GRACE_SECONDS = 30


@dataclass(slots=True)
class CommandResult:
    host: str
    shell: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    ok: bool
    data: Any = field(default=None)

    def to_dict(self, output_limit: int = 200_000) -> dict[str, Any]:
        data = asdict(self)
        data["stdout"], stdout_truncated = _truncate(self.stdout, output_limit)
        data["stderr"], stderr_truncated = _truncate(self.stderr, output_limit)
        data["output_truncated"] = stdout_truncated or stderr_truncated
        if self.data is None:
            data.pop("data")
        return data


async def execute(
    config: WinRMConfig,
    command: str,
    *,
    shell: str,
    timeout: float,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    output_format: str = "text",
) -> CommandResult:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be text or json")
    if output_format == "json" and shell != "powershell":
        raise ValueError("output_format=json is only supported for PowerShell")
    deadline = time.monotonic() + timeout
    worker = asyncio.to_thread(_execute_sync, config, command, shell, cwd, env, deadline, output_format)
    # The worker stops the remote command itself at the deadline; the outer bound only guards
    # against a WSMan call that never returns.
    try:
        return await asyncio.wait_for(worker, timeout=timeout + STOP_GRACE_SECONDS)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"WinRM command exceeded {timeout} seconds") from exc


def _execute_sync(
    config: WinRMConfig,
    command: str,
    shell: str,
    cwd: str | None,
    env: dict[str, str] | None,
    deadline: float,
    output_format: str,
) -> CommandResult:
    started = time.monotonic()
    for key in env or {}:
        _validate_env_name(key)
    with WSMan(config.host, **config.client_kwargs()) as wsman:
        if shell == "cmd":
            stdout, stderr, code = _run_cmd(wsman, _prepare_cmd(command, cwd), env, deadline)
            return CommandResult(
                host=config.host,
                shell="cmd",
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=code,
                duration_seconds=round(time.monotonic() - started, 3),
                ok=code == 0,
            )

        script = _prepare_powershell(command, cwd, env, json_output=output_format == "json")
        output, streams, had_errors, host_code = _run_powershell(wsman, script, deadline)
        stdout, marker_code = _parse_ps_output(output)
        # `exit N` ends the pipeline before the marker line runs; the host records N instead.
        code = host_code if host_code is not None else marker_code
        if code is None:
            code = 1 if had_errors else 0
        result = CommandResult(
            host=config.host,
            shell="powershell",
            command=command,
            stdout=stdout,
            stderr=_format_streams(streams),
            exit_code=code,
            duration_seconds=round(time.monotonic() - started, 3),
            ok=code == 0 and not had_errors,
        )
        if output_format == "json":
            result.data = _parse_json_output(stdout)
        return result


def _run_powershell(wsman: WSMan, script: str, deadline: float) -> tuple[list[Any], Any, bool, int | None]:
    host = PSHost(None, None, False, "winrm-mcp", None, None, "1.0")
    with RunspacePool(wsman, host=host) as pool:
        ps = PowerShell(pool)
        ps.add_script(script)
        ps.begin_invoke()
        while ps.state == PSInvocationState.RUNNING:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with contextlib.suppress(Exception):
                    ps.stop()
                raise TimeoutError("WinRM command exceeded its timeout and was stopped on the remote host")
            ps.poll_invoke(timeout=max(1, min(POLL_SECONDS, int(remaining))))
        return ps.output, ps.streams, ps.had_errors, host.rc


def _run_cmd(wsman: WSMan, command: str, env: dict[str, str] | None, deadline: float) -> tuple[str, str, int]:
    # WinRS sets real process environment variables; `set` inside the command line would be
    # too late because cmd expands %VAR% when it parses the line.
    with WinRS(wsman, environment={k: str(v) for k, v in (env or {}).items()} or None) as shell:
        process = Process(shell, command)
        process.begin_invoke()
        while process.state != CommandState.DONE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with contextlib.suppress(Exception):
                    process.signal(SignalCode.TERMINATE)
                raise TimeoutError("WinRM command exceeded its timeout and was terminated on the remote host")
            process.poll_invoke(timeout=max(1, min(POLL_SECONDS, int(remaining))))
        with contextlib.suppress(Exception):
            process.signal(SignalCode.CTRL_C)
    code = process.rc if process.rc is not None else -1
    return _decode(process.stdout), _decode(process.stderr), code


def copy_to_remote(config: WinRMConfig, source: Path, remote_path: str) -> str:
    with Client(config.host, **config.client_kwargs()) as client:
        return client.copy(str(source), remote_path)


def fetch_from_remote(config: WinRMConfig, remote_path: str, destination: Path) -> None:
    with Client(config.host, **config.client_kwargs()) as client:
        client.fetch(remote_path, str(destination))


def _prepare_powershell(
    command: str, cwd: str | None, env: dict[str, str] | None, *, json_output: bool = False
) -> str:
    lines = ["$global:LASTEXITCODE = $null"]
    if cwd:
        lines.append(f"Set-Location -LiteralPath {_ps_quote(cwd)}")
    for key, value in (env or {}).items():
        _validate_env_name(key)
        lines.append(f"$env:{key} = {_ps_quote(str(value))}")
    if json_output:
        # One JSON document for the whole output, so agents get structured data instead of
        # PowerShell's formatted tables.
        lines.append(f"@(& {{\n{command}\n}}) | ConvertTo-Json -Depth 6 -Compress")
    else:
        lines.append(command)
    lines.extend(
        [
            (
                "$__winrm_mcp_code = if ($null -ne $LASTEXITCODE) "
                "{ [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }"
            ),
            f'Write-Output "{EXIT_MARKER}$__winrm_mcp_code"',
        ]
    )
    return "\n".join(lines)


def _prepare_cmd(command: str, cwd: str | None) -> str:
    if cwd:
        return f'cd /d "{cwd.replace(chr(34), "")}" && {command}'
    return command


def _parse_ps_output(output: Any) -> tuple[str, int | None]:
    code: int | None = None
    retained: list[str] = []
    for line in _text(output).splitlines():
        if line.startswith(EXIT_MARKER):
            with contextlib.suppress(ValueError):
                code = int(line.split("=", 1)[1].strip())
        else:
            retained.append(line)
    return "\n".join(retained), code


def _parse_json_output(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _format_streams(streams: Any) -> str:
    chunks: list[str] = []
    for name in ("error", "warning", "verbose", "debug", "information"):
        for value in getattr(streams, name, None) or []:
            chunks.append(f"[{name}] {value}")
    return "\n".join(chunks)


def _decode(value: bytes) -> str:
    # WinRS returns console code-page bytes; UTF-8 first, then the classic OEM code page.
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.decode("cp437", errors="replace")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item) for item in value)
    return str(value)


def _truncate(value: str, limit: int) -> tuple[str, bool]:
    if limit <= 0 or len(value) <= limit:
        return value, False
    half = max(1, limit // 2)
    removed = len(value) - (half * 2)
    return value[:half] + f"\n\n... [truncated {removed} characters] ...\n\n" + value[-half:], True


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _validate_env_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"invalid environment variable name: {name!r}")

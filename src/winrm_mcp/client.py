from __future__ import annotations

import asyncio
import contextlib
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

from pypsrp.client import Client

from .config import WinRMConfig

EXIT_MARKER = "__WINRM_MCP_EXIT_CODE__="


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

    def to_dict(self, output_limit: int = 200_000) -> dict[str, Any]:
        data = asdict(self)
        data["stdout"], stdout_truncated = _truncate(self.stdout, output_limit)
        data["stderr"], stderr_truncated = _truncate(self.stderr, output_limit)
        data["output_truncated"] = stdout_truncated or stderr_truncated
        return data


async def execute(
    config: WinRMConfig,
    command: str,
    *,
    shell: str,
    timeout: float,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_execute_sync, config, command, shell, cwd, env),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"WinRM command exceeded {timeout} seconds") from exc


def _execute_sync(
    config: WinRMConfig,
    command: str,
    shell: str,
    cwd: str | None,
    env: dict[str, str] | None,
) -> CommandResult:
    started = time.monotonic()
    with Client(config.host, **config.client_kwargs()) as client:
        if shell == "cmd":
            stdout, stderr, exit_code = client.execute_cmd(_prepare_cmd(command, cwd, env))
            code = int(exit_code)
            return CommandResult(
                host=config.host,
                shell="cmd",
                command=command,
                stdout=_text(stdout),
                stderr=_text(stderr),
                exit_code=code,
                duration_seconds=round(time.monotonic() - started, 3),
                ok=code == 0,
            )

        output, streams, had_errors = client.execute_ps(_prepare_powershell(command, cwd, env))
        stdout, marker_code = _parse_ps_output(output)
        code = marker_code if marker_code is not None else (1 if had_errors else 0)
        return CommandResult(
            host=config.host,
            shell="powershell",
            command=command,
            stdout=stdout,
            stderr=_format_streams(streams),
            exit_code=code,
            duration_seconds=round(time.monotonic() - started, 3),
            ok=code == 0 and not had_errors,
        )


def _prepare_powershell(command: str, cwd: str | None, env: dict[str, str] | None) -> str:
    lines = ["$global:LASTEXITCODE = $null"]
    if cwd:
        lines.append(f"Set-Location -LiteralPath {_ps_quote(cwd)}")
    for key, value in (env or {}).items():
        _validate_env_name(key)
        lines.append(f"$env:{key} = {_ps_quote(str(value))}")
    lines.extend(
        [
            command,
            (
                "$__winrm_mcp_code = if ($null -ne $LASTEXITCODE) "
                "{ [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }"
            ),
            f'Write-Output "{EXIT_MARKER}$__winrm_mcp_code"',
        ]
    )
    return "\n".join(lines)


def _prepare_cmd(command: str, cwd: str | None, env: dict[str, str] | None) -> str:
    parts: list[str] = []
    if cwd:
        parts.append(f'cd /d "{cwd.replace(chr(34), chr(34) * 2)}"')
    for key, value in (env or {}).items():
        _validate_env_name(key)
        parts.append(f'set "{key}={str(value).replace(chr(34), chr(34) * 2)}"')
    parts.append(command)
    return " && ".join(parts)


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


def _format_streams(streams: Any) -> str:
    chunks: list[str] = []
    for name in ("error", "warning", "verbose", "debug", "information"):
        for value in getattr(streams, name, None) or []:
            chunks.append(f"[{name}] {value}")
    return "\n".join(chunks)


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

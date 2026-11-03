"""Operator-controlled limits on where the server connects and which secrets it may read.

Tool arguments come from an AI agent, which may be steered by untrusted content (prompt
injection). Without limits, an agent could point a connection at a host it controls and use
`password_env` to make the server send any of its environment variables there as a password.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any

from .config import ConfigurationError, WinRMConfig, _bool

DEFAULT_SECRET_ENV_PATTERNS = ("*PASSWORD*", "*PASSWD*", "*_PASS")
# Fields an agent may still override per call when ad-hoc connections are disabled.
TUNING_FIELDS = {"connect_timeout", "read_timeout", "operation_timeout"}


def _patterns(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return tuple(p.strip() for p in raw.split(",") if p.strip())


@dataclass(frozen=True, slots=True)
class Policy:
    allowed_hosts: tuple[str, ...] = ()
    allow_adhoc: bool = True
    secret_env_patterns: tuple[str, ...] = DEFAULT_SECRET_ENV_PATTERNS
    allow_insecure_basic: bool = False
    local_root: str | None = None

    @classmethod
    def from_environment(cls) -> Policy:
        root = os.getenv("WINRM_MCP_LOCAL_ROOT")
        return cls(
            allowed_hosts=tuple(p.lower() for p in _patterns("WINRM_MCP_ALLOWED_HOSTS")),
            allow_adhoc=_bool(os.getenv("WINRM_MCP_ALLOW_ADHOC", "true"), "WINRM_MCP_ALLOW_ADHOC"),
            secret_env_patterns=_patterns("WINRM_MCP_SECRET_ENV_PATTERNS", DEFAULT_SECRET_ENV_PATTERNS),
            allow_insecure_basic=_bool(
                os.getenv("WINRM_MCP_ALLOW_INSECURE_BASIC", "false"), "WINRM_MCP_ALLOW_INSECURE_BASIC"
            ),
            local_root=os.path.realpath(os.path.expanduser(root)) if root else None,
        )

    def check_overrides(self, connection: dict[str, Any] | None, *, saved_host: bool) -> None:
        if self.allow_adhoc or not connection:
            return
        forbidden = sorted(set(connection) - TUNING_FIELDS)
        if forbidden or not saved_host:
            raise ConfigurationError(
                "ad-hoc connections are disabled (WINRM_MCP_ALLOW_ADHOC=false); use a saved host "
                f"and override only {', '.join(sorted(TUNING_FIELDS))}"
                + (f" (got {', '.join(forbidden)})" if forbidden else "")
            )

    def check(self, config: WinRMConfig) -> WinRMConfig:
        host = config.host.lower()
        if self.allowed_hosts and not any(fnmatchcase(host, pattern) for pattern in self.allowed_hosts):
            raise ConfigurationError(f"host {config.host!r} is not allowed by WINRM_MCP_ALLOWED_HOSTS")
        reads_env = config.password_env and config.password is None
        if reads_env and not any(
            fnmatchcase(config.password_env.upper(), p.upper()) for p in self.secret_env_patterns
        ):
            raise ConfigurationError(
                f"password_env {config.password_env!r} does not match WINRM_MCP_SECRET_ENV_PATTERNS "
                f"({', '.join(self.secret_env_patterns)})"
            )
        if config.auth == "basic" and not config.ssl and not self.allow_insecure_basic:
            raise ConfigurationError(
                "basic auth over plain HTTP sends the password unencrypted; use ssl=true, ntlm/kerberos, "
                "or set WINRM_MCP_ALLOW_INSECURE_BASIC=true"
            )
        return config

    def summary(self) -> dict[str, Any]:
        return {
            "allowed_hosts": list(self.allowed_hosts) or "any",
            "allow_adhoc": self.allow_adhoc,
            "secret_env_patterns": list(self.secret_env_patterns),
            "allow_insecure_basic": self.allow_insecure_basic,
            "file_transfer": "enabled" if self.local_root else "disabled (set WINRM_MCP_LOCAL_ROOT)",
            "local_root": self.local_root,
        }

    def local_path(self, path: str, *, must_exist: bool) -> str:
        """Resolve a local path for file transfer, confined to WINRM_MCP_LOCAL_ROOT."""
        if not self.local_root:
            raise ConfigurationError("file transfer is disabled; set WINRM_MCP_LOCAL_ROOT to a directory")
        candidate = os.path.realpath(os.path.join(self.local_root, os.path.expanduser(path)))
        if os.path.commonpath([candidate, self.local_root]) != self.local_root:
            raise ConfigurationError(f"local path {path!r} is outside WINRM_MCP_LOCAL_ROOT")
        if must_exist and not os.path.isfile(candidate):
            raise ConfigurationError(f"local file {path!r} does not exist under WINRM_MCP_LOCAL_ROOT")
        return candidate

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class ConfigurationError(ValueError):
    """Raised when WinRM connection settings are invalid."""


@dataclass(slots=True)
class WinRMConfig:
    host: str
    username: str | None = None
    password: str | None = None
    password_env: str | None = None
    port: int | None = None
    ssl: bool = True
    auth: str = "ntlm"
    cert_validation: bool = True
    encryption: str = "auto"
    path: str = "wsman"
    connect_timeout: int = 30
    read_timeout: int = 60
    operation_timeout: int = 30

    @classmethod
    def from_mapping(cls, connection: dict[str, Any] | None = None) -> WinRMConfig:
        data = _environment_defaults()
        if connection is not None:
            if not isinstance(connection, dict):
                raise ConfigurationError("connection must be an object")
            unknown = set(connection) - set(cls.__dataclass_fields__)
            if unknown:
                raise ConfigurationError(f"unknown connection fields: {', '.join(sorted(unknown))}")
            data.update({key: value for key, value in connection.items() if value is not None})

        host = str(data.get("host", "")).strip()
        if not host:
            raise ConfigurationError("host is required (connection.host or WINRM_MCP_HOST)")
        data["host"] = host

        for key in ("ssl", "cert_validation"):
            if key in data:
                data[key] = _bool(data[key], key)
        for key in ("port", "connect_timeout", "read_timeout", "operation_timeout"):
            if key in data:
                try:
                    data[key] = int(data[key])
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError(f"{key} must be an integer") from exc

        config = cls(**data)
        config.validate()
        return config

    def validate(self) -> None:
        if self.port is not None and not 1 <= self.port <= 65535:
            raise ConfigurationError("port must be between 1 and 65535")
        if self.auth != "certificate" and not self.username:
            raise ConfigurationError("username is required for this authentication method")
        if self.encryption not in {"auto", "always", "never"}:
            raise ConfigurationError("encryption must be auto, always, or never")
        if min(self.connect_timeout, self.read_timeout, self.operation_timeout) <= 0:
            raise ConfigurationError("timeouts must be positive")
        if self.operation_timeout >= self.read_timeout:
            self.read_timeout = self.operation_timeout + 10

    @property
    def effective_port(self) -> int:
        return self.port or (5986 if self.ssl else 5985)

    def resolved_password(self) -> str | None:
        if self.password is not None:
            return self.password
        if not self.password_env:
            return None
        value = os.getenv(self.password_env)
        if value is None:
            raise ConfigurationError(f"environment variable {self.password_env!r} is not set")
        return value

    def client_kwargs(self) -> dict[str, Any]:
        return {
            "port": self.effective_port,
            "username": self.username,
            "password": self.resolved_password(),
            "ssl": self.ssl,
            "path": self.path,
            "auth": self.auth,
            "cert_validation": self.cert_validation,
            "connection_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "operation_timeout": self.operation_timeout,
            "encryption": self.encryption,
        }


def _environment_defaults() -> dict[str, Any]:
    names = {
        "host": "WINRM_MCP_HOST",
        "username": "WINRM_MCP_USERNAME",
        "password": "WINRM_MCP_PASSWORD",
        "password_env": "WINRM_MCP_PASSWORD_ENV",
        "port": "WINRM_MCP_PORT",
        "ssl": "WINRM_MCP_SSL",
        "auth": "WINRM_MCP_AUTH",
        "cert_validation": "WINRM_MCP_CERT_VALIDATION",
        "encryption": "WINRM_MCP_ENCRYPTION",
        "path": "WINRM_MCP_PATH",
        "connect_timeout": "WINRM_MCP_CONNECT_TIMEOUT",
        "read_timeout": "WINRM_MCP_READ_TIMEOUT",
        "operation_timeout": "WINRM_MCP_OPERATION_TIMEOUT",
    }
    return {field: os.environ[name] for field, name in names.items() if name in os.environ}


def _bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigurationError(f"{name} must be a boolean")

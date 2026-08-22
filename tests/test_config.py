import pytest

from winrm_mcp.config import ConfigurationError, WinRMConfig


def test_defaults_and_http_port() -> None:
    config = WinRMConfig.from_mapping(
        {"host": "windows.example", "username": "Administrator", "password": "secret", "ssl": False}
    )
    assert config.effective_port == 5985
    assert config.auth == "ntlm"


def test_environment_defaults_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WINRM_MCP_HOST", "old.example")
    monkeypatch.setenv("WINRM_MCP_USERNAME", "admin")
    config = WinRMConfig.from_mapping({"host": "new.example"})
    assert config.host == "new.example"
    assert config.username == "admin"


def test_password_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_WINRM_PASSWORD", "secret")
    config = WinRMConfig.from_mapping(
        {"host": "windows.example", "username": "admin", "password_env": "TEST_WINRM_PASSWORD"}
    )
    assert config.resolved_password() == "secret"


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ConfigurationError, match="unknown connection fields"):
        WinRMConfig.from_mapping({"host": "windows.example", "username": "admin", "protocol": "winrm"})


def test_read_timeout_is_adjusted_for_pypsrp() -> None:
    config = WinRMConfig.from_mapping(
        {
            "host": "windows.example",
            "username": "admin",
            "operation_timeout": 60,
            "read_timeout": 30,
        }
    )
    assert config.read_timeout == 70


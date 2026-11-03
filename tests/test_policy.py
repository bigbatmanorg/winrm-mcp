import pytest

from winrm_mcp import server
from winrm_mcp.config import ConfigurationError, WinRMConfig
from winrm_mcp.policy import Policy


def config(**extra):
    return WinRMConfig.from_mapping(
        {"host": "win01.lab.example", "username": "admin", **extra}, include_environment=False
    )


def test_allowed_hosts_glob(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WINRM_MCP_ALLOWED_HOSTS", "*.lab.example, 10.0.110.*")
    policy = Policy.from_environment()
    policy.check(config())
    policy.check(config(host="10.0.110.66"))
    with pytest.raises(ConfigurationError, match="not allowed"):
        policy.check(config(host="attacker.example"))


def test_password_env_must_look_like_a_password(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = Policy.from_environment()
    policy.check(config(password_env="WIN01_PASSWORD"))
    with pytest.raises(ConfigurationError, match="SECRET_ENV_PATTERNS"):
        policy.check(config(password_env="AWS_SECRET_ACCESS_KEY"))
    monkeypatch.setenv("WINRM_MCP_SECRET_ENV_PATTERNS", "LAB_*")
    Policy.from_environment().check(config(password_env="LAB_TOKEN"))


def test_basic_over_http_is_refused_unless_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfigurationError, match="unencrypted"):
        Policy.from_environment().check(config(auth="basic", ssl=False))
    Policy.from_environment().check(config(auth="basic", ssl=True))
    monkeypatch.setenv("WINRM_MCP_ALLOW_INSECURE_BASIC", "true")
    Policy.from_environment().check(config(auth="basic", ssl=False))


def test_adhoc_disabled_allows_only_saved_hosts_with_timeout_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WINRM_MCP_ALLOW_ADHOC", "false")
    policy = Policy.from_environment()
    policy.check_overrides({"read_timeout": 90}, saved_host=True)
    with pytest.raises(ConfigurationError, match="ad-hoc connections are disabled"):
        policy.check_overrides({"host": "other.example"}, saved_host=True)
    with pytest.raises(ConfigurationError, match="ad-hoc connections are disabled"):
        policy.check_overrides({"host": "other.example", "username": "x"}, saved_host=False)


def test_resolve_applies_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WINRM_MCP_ALLOWED_HOSTS", "*.lab.example")
    with pytest.raises(ConfigurationError, match="not allowed"):
        server._resolve(None, {"host": "evil.example", "username": "x", "password": "y"}, None)


def test_local_path_confinement(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="file transfer is disabled"):
        Policy.from_environment().local_path("a.txt", must_exist=False)
    monkeypatch.setenv("WINRM_MCP_LOCAL_ROOT", str(tmp_path))
    policy = Policy.from_environment()
    assert policy.local_path("sub/a.txt", must_exist=False) == str(tmp_path / "sub" / "a.txt")
    for escape in ("../outside.txt", "/etc/passwd", "sub/../../x"):
        with pytest.raises(ConfigurationError, match="outside"):
            policy.local_path(escape, must_exist=False)
    with pytest.raises(ConfigurationError, match="does not exist"):
        policy.local_path("missing.txt", must_exist=True)


def test_auth_validation_certificate_and_tags() -> None:
    with pytest.raises(ConfigurationError, match="auth must be one of"):
        config(auth="digest")
    with pytest.raises(ConfigurationError, match="certificate_pem"):
        WinRMConfig.from_mapping({"host": "h", "auth": "certificate"}, include_environment=False)
    cert = WinRMConfig.from_mapping(
        {"host": "h", "auth": "certificate", "certificate_pem": "~/c.pem", "certificate_key_pem": "~/k.pem"},
        include_environment=False,
    )
    assert cert.client_kwargs()["certificate_pem"].endswith("/c.pem")
    assert config(tags=["web", "web", " prod "]).tags == ["prod", "web"]
    with pytest.raises(ConfigurationError, match="tags"):
        config(tags="web")

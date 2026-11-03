import pytest

from winrm_mcp.client import (
    EXIT_MARKER,
    CommandResult,
    _parse_json_output,
    _parse_ps_output,
    _prepare_cmd,
    _prepare_powershell,
)


def test_powershell_wrapper_and_marker_parsing() -> None:
    rendered = _prepare_powershell("Write-Output hello", "C:\\Temp", {"MODE": "test"})
    assert "Set-Location -LiteralPath 'C:\\Temp'" in rendered
    assert "$env:MODE = 'test'" in rendered
    stdout, code = _parse_ps_output(["hello", f"{EXIT_MARKER}0"])
    assert stdout == "hello"
    assert code == 0


def test_cmd_wrapper_changes_directory_and_leaves_env_to_winrs() -> None:
    assert _prepare_cmd("whoami", "C:\\Temp") == 'cd /d "C:\\Temp" && whoami'
    assert _prepare_cmd("whoami", None) == "whoami"


def test_json_output_wraps_command_and_parses() -> None:
    rendered = _prepare_powershell("Get-Service w32time", None, None, json_output=True)
    assert "@(& {\nGet-Service w32time\n}) | ConvertTo-Json -Depth 6 -Compress" in rendered
    assert _parse_json_output('[{"Name":"w32time"}]') == [{"Name": "w32time"}]
    assert _parse_json_output("") == []
    assert _parse_json_output("not json") is None


def test_invalid_environment_name() -> None:
    with pytest.raises(ValueError, match="invalid environment"):
        _prepare_powershell("hostname", None, {"BAD-NAME": "value"})


def test_output_truncation() -> None:
    result = CommandResult("host", "cmd", "x", "abcdefghij", "", 0, 0.1, True)
    payload = result.to_dict(output_limit=6)
    assert payload["output_truncated"] is True
    assert "truncated" in payload["stdout"]

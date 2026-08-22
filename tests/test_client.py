import pytest

from winrm_mcp.client import (
    EXIT_MARKER,
    CommandResult,
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


def test_cmd_wrapper() -> None:
    rendered = _prepare_cmd("whoami", "C:\\Temp", {"MODE": "test"})
    assert rendered == 'cd /d "C:\\Temp" && set "MODE=test" && whoami'


def test_invalid_environment_name() -> None:
    with pytest.raises(ValueError, match="invalid environment"):
        _prepare_powershell("hostname", None, {"BAD-NAME": "value"})


def test_output_truncation() -> None:
    result = CommandResult("host", "cmd", "x", "abcdefghij", "", 0, 0.1, True)
    payload = result.to_dict(output_limit=6)
    assert payload["output_truncated"] is True
    assert "truncated" in payload["stdout"]


from winrm_mcp.server import mcp


def test_server_registers_only_small_winrm_surface() -> None:
    tool_manager = mcp._tool_manager
    assert set(tool_manager._tools) == {
        "winrm_test",
        "winrm_execute_powershell",
        "winrm_execute_cmd",
    }


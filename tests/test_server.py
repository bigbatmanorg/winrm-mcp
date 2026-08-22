from winrm_mcp.server import mcp


def test_server_registers_winrm_and_inventory_tools() -> None:
    tool_manager = mcp._tool_manager
    assert set(tool_manager._tools) == {
        "winrm_test",
        "winrm_execute_powershell",
        "winrm_execute_cmd",
        "winrm_inventory_status",
        "winrm_inventory_init",
        "winrm_inventory_validate",
        "winrm_host_list",
        "winrm_host_get",
        "winrm_host_save",
        "winrm_host_update",
        "winrm_host_delete",
    }

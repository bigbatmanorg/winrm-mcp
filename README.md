# winrm-mcp

A deliberately small MCP server for running PowerShell and CMD commands on Windows hosts over WinRM. It takes
the WinRM execution ideas from `ssh-winrm-mcp` and leaves out SSH, inventories, sessions, jobs, command groups,
and file transfer.

## Tools

- `winrm_test` — verify authentication and connectivity.
- `winrm_execute_powershell` — execute PowerShell.
- `winrm_execute_cmd` — execute CMD.

Each tool accepts an optional `connection` object. Values in it override the process environment:

```json
{
  "host": "192.168.1.50",
  "username": "Administrator",
  "password_env": "MY_WINRM_PASSWORD",
  "auth": "ntlm",
  "ssl": true,
  "cert_validation": false
}
```

`ssl` chooses HTTPS (normally port 5986) versus HTTP (normally port 5985). `cert_validation=false` is needed for
self-signed HTTPS listeners, but should only be used for trusted hosts.

Supported connection fields are `host`, `username`, `password`, `password_env`, `port`, `ssl`, `auth`,
`cert_validation`, `encryption`, `path`, `connect_timeout`, `read_timeout`, and `operation_timeout`.

## Install and run

```bash
uv sync --extra dev
uv run pytest
uv run winrm-mcp
```

The default transport is stdio. A client configuration can supply stable connection defaults without putting
credentials in every tool call:

```json
{
  "servers": {
    "winrm": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/home/toor/projects/winrm-mcp", "run", "winrm-mcp"],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD_ENV": "MY_WINRM_PASSWORD",
        "MY_WINRM_PASSWORD": "replace-me",
        "WINRM_MCP_AUTH": "ntlm",
        "WINRM_MCP_SSL": "true",
        "WINRM_MCP_CERT_VALIDATION": "false"
      }
    }
  }
}
```

Available environment defaults correspond to the connection fields and use the `WINRM_MCP_` prefix. Server
settings are `WINRM_MCP_TRANSPORT`, `WINRM_MCP_SERVER_HOST`, and `WINRM_MCP_SERVER_PORT`.

For Kerberos or CredSSP support, install the matching optional extra:

```bash
uv sync --extra kerberos
uv sync --extra credssp
```


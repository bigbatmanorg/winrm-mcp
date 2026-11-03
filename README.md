# winrm-mcp

A focused MCP server for running PowerShell and CMD commands on Windows hosts over WinRM, with a multi-host
inventory, parallel execution across tagged hosts, sandboxed file transfer and an operator-controlled security
policy. It leaves out SSH, persistent sessions, jobs and command groups (see `ssh-winrm-mcp` for those).

- Accurate exit codes, including PowerShell `exit N`; timed-out commands are stopped on the remote host.
- `output_format="json"` returns PowerShell objects as parsed JSON instead of formatted text.
- Every tool declares MCP annotations so clients can ask before running remote commands.

## Tools

- `winrm_test` — verify authentication and connectivity; reports whether the account is a local administrator.
- `winrm_execute_powershell` — execute PowerShell (`output_format="json"` for structured results).
- `winrm_execute_cmd` — execute CMD; `env` sets real process environment variables.
- `winrm_execute_many` — run one command on several saved hosts (by name or tag) in parallel, one result per host.
- `winrm_upload`, `winrm_download` — copy files, confined to `WINRM_MCP_LOCAL_ROOT` (disabled unless set).
- `winrm_policy` — show the version and the active security policy.
- `winrm_inventory_status`, `winrm_inventory_init`, `winrm_inventory_validate` — manage inventory files.
- `winrm_host_list`, `winrm_host_get`, `winrm_host_save`, `winrm_host_update`, `winrm_host_delete` — manage
  reusable hosts.

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

Supported connection fields are `host`, `username`, `password`, `password_env`, `port`, `ssl`, `auth`
(`ntlm`, `negotiate`, `kerberos`, `basic`, `credssp`, `certificate`), `cert_validation`, `encryption`, `path`,
`connect_timeout`, `read_timeout`, `operation_timeout`, `certificate_pem` and `certificate_key_pem` (file paths for
certificate auth over HTTPS), and `tags` (a list of labels for `winrm_host_list(tag=...)` and
`winrm_execute_many(tag=...)`).

## Security model

Commands run with the remote account's full rights, and tool arguments come from an AI agent that untrusted
content (web pages, files, command output) can steer. The operator limits what the agent can reach:

| Setting | Default | Effect |
|---|---|---|
| `WINRM_MCP_ALLOWED_HOSTS` | any | Comma-separated glob patterns (`*.lab.example,10.0.110.*`); other hosts are refused, saved or not. |
| `WINRM_MCP_ALLOW_ADHOC` | `true` | `false` allows only saved hosts; per-call `connection` may then only change timeouts. |
| `WINRM_MCP_SECRET_ENV_PATTERNS` | `*PASSWORD*,*PASSWD*,*_PASS` | `password_env` may only read matching variables, so an agent cannot send e.g. `AWS_SECRET_ACCESS_KEY` to a host it controls. |
| `WINRM_MCP_ALLOW_INSECURE_BASIC` | `false` | Basic auth over plain HTTP sends the password in cleartext and is refused unless enabled. NTLM/Kerberos over HTTP use message encryption and are allowed. |
| `WINRM_MCP_LOCAL_ROOT` | unset | Enables `winrm_upload`/`winrm_download`, confined to this directory. |

## Multi-host inventory

Hosts can be stored in either inventory scope:

- `user` (default): `${XDG_CONFIG_HOME:-~/.config}/winrm-mcp/inventory.json` on Linux/macOS, or the matching
  `%APPDATA%` location on Windows.
- `project`: `.winrm-mcp/inventory.json` under the current working directory.

Choose the process default with `WINRM_MCP_INVENTORY_SCOPE=user` or `WINRM_MCP_INVENTORY_SCOPE=project`.
Every inventory and host tool also accepts an explicit `scope`, and execution tools accept `inventory_scope`.
Project scope uses `WINRM_MCP_PROJECT_DIR`, then the launcher's logical `PWD`, then the process working directory.
It refuses temporary `deepagents_server_*` paths instead of silently saving disposable inventory data. Set
`WINRM_MCP_PROJECT_DIR` when the launcher working directory is not the desired project root. A fully custom file is
supported through `WINRM_MCP_INVENTORY_FILE`; it is used when a call does not explicitly select a scope.

Create a project inventory and save two hosts:

```text
winrm_inventory_init(scope="project")

winrm_host_save(
  name="epv1",
  scope="project",
  settings={
    "host": "10.0.110.50",
    "username": "Administrator",
    "password_env": "EPV1_WINRM_PASSWORD",
    "auth": "ntlm",
    "ssl": true,
    "cert_validation": false
  }
)

winrm_host_save(
  name="epv2",
  scope="project",
  settings={
    "host": "10.0.110.51",
    "username": "Administrator",
    "password_env": "EPV2_WINRM_PASSWORD",
    "auth": "ntlm",
    "ssl": true,
    "cert_validation": false
  }
)
```

Use a saved host by name:

```text
winrm_test(saved_host="epv1", inventory_scope="project")
winrm_execute_powershell(saved_host="epv1", inventory_scope="project", command="hostname")
winrm_execute_cmd(saved_host="epv2", inventory_scope="project", command="whoami")
```

The optional `connection` object overrides fields from the saved host for that call. Inventory writes are atomic,
and the inventory file is restricted to the current user (`0600`) on Unix-like systems. Inline passwords are
supported but stored as plaintext in that protected JSON file; prefer `password_env`.

Omit `connection` when no overrides are needed. For compatibility with agents that serialize an optional value as
text, `connection="None"`, `connection="null"`, and an empty connection string are treated as JSON `null`.

## DeepAgents

DeepAgents can run the server directly from GitHub, so a local checkout is not required. Add the following
entry to your DeepAgents `.deepagents/.mcp.json` file:

```json
{
  "winrm": {
    "type": "stdio",
    "command": "uv",
    "args": [
      "tool",
      "run",
      "--with",
      "mcp>=1.28,<2",
      "--from",
      "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
      "winrm-mcp"
    ],
    "env": {
      "WINRM_MCP_HOST": "192.168.1.50",
      "WINRM_MCP_USERNAME": "Administrator",
      "WINRM_MCP_PASSWORD": "YOUR_SECRET",
      "WINRM_MCP_PORT": "5986",
      "WINRM_MCP_AUTH": "ntlm",
      "WINRM_MCP_SSL": "true",
      "WINRM_MCP_CERT_VALIDATION": "false",
      "WINRM_MCP_INVENTORY_SCOPE": "project",
      "WINRM_MCP_PROJECT_DIR": "${PWD}",
      "WINRM_MCP_CONNECT_TIMEOUT": "30",
      "WINRM_MCP_READ_TIMEOUT": "60",
      "WINRM_MCP_OPERATION_TIMEOUT": "30"
    }
  }
}
```

For reproducible installations, pin the repository to a release tag or commit:

```json
"git+https://github.com/bigbatmanorg/winrm-mcp.git@YOUR_TAG_OR_COMMIT"
```

The example uses HTTPS with certificate verification disabled for a trusted development host with a self-signed
certificate. Keep `WINRM_MCP_CERT_VALIDATION=true` when the listener certificate is trusted. Do not commit a real
password to source control; use your normal DeepAgents secret-injection workflow for `WINRM_MCP_PASSWORD`.
DeepAgents expands `${PWD}` before launching the MCP server. Replace it with an absolute path if DeepAgents itself
is launched from somewhere other than the project root.

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
      "args": ["--directory", "/absolute/path/to/winrm-mcp", "run", "winrm-mcp"],
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
settings are `WINRM_MCP_TRANSPORT`, `WINRM_MCP_SERVER_HOST`, and `WINRM_MCP_SERVER_PORT`. Inventory settings are
`WINRM_MCP_INVENTORY_SCOPE`, `WINRM_MCP_PROJECT_DIR`, and `WINRM_MCP_INVENTORY_FILE`.

## Testing

```bash
uv sync --extra dev
uv run pytest                                  # offline unit tests
WINRM_LIVE=1 uv run pytest tests/live -v       # live tests over MCP stdio against a Windows host
```

Live tests read `WINRM_TEST_HOST`, `WINRM_TEST_ADMIN_USER`/`WINRM_TEST_ADMIN_PASSWORD` (a local administrator)
and `WINRM_TEST_USER`/`WINRM_TEST_USER_PASSWORD` (a member of *Remote Management Users*), for example from a
gitignored `.env`.

For Kerberos or CredSSP support, install the matching optional extra:

```bash
uv sync --extra kerberos
uv sync --extra credssp
```

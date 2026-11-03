# winrm-mcp

A focused MCP server for running PowerShell and CMD commands on Windows hosts over WinRM, with a multi-host
inventory, parallel execution across tagged hosts, sandboxed file transfer and an operator-controlled security
policy. It leaves out SSH, persistent sessions, jobs and command groups (see `ssh-winrm-mcp` for those).

- Accurate exit codes, including PowerShell `exit N`; timed-out commands are stopped on the remote host.
- `output_format="json"` returns PowerShell objects as parsed JSON instead of formatted text.
- Every tool declares MCP annotations so clients can ask before running remote commands.

<!-- install:start -->
## Install in your agent

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_winrm-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=winrm&inputs=%5B%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22winrm_mcp_host%22%2C%22description%22%3A%22Default%20Windows%20host%22%2C%22password%22%3Afalse%7D%2C%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22winrm_mcp_username%22%2C%22description%22%3A%22Default%20user%22%2C%22password%22%3Afalse%7D%2C%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22winrm_mcp_password%22%2C%22description%22%3A%22Default%20password%22%2C%22password%22%3Atrue%7D%5D&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/bigbatmanorg/winrm-mcp.git%40v0.3.0%22%2C%22winrm-mcp%22%5D%2C%22env%22%3A%7B%22WINRM_MCP_HOST%22%3A%22%24%7Binput%3Awinrm_mcp_host%7D%22%2C%22WINRM_MCP_USERNAME%22%3A%22%24%7Binput%3Awinrm_mcp_username%7D%22%2C%22WINRM_MCP_PASSWORD%22%3A%22%24%7Binput%3Awinrm_mcp_password%7D%22%7D%7D)
[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install_winrm-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=winrm&inputs=%5B%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22winrm_mcp_host%22%2C%22description%22%3A%22Default%20Windows%20host%22%2C%22password%22%3Afalse%7D%2C%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22winrm_mcp_username%22%2C%22description%22%3A%22Default%20user%22%2C%22password%22%3Afalse%7D%2C%7B%22type%22%3A%22promptString%22%2C%22id%22%3A%22winrm_mcp_password%22%2C%22description%22%3A%22Default%20password%22%2C%22password%22%3Atrue%7D%5D&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22git%2Bhttps%3A//github.com/bigbatmanorg/winrm-mcp.git%40v0.3.0%22%2C%22winrm-mcp%22%5D%2C%22env%22%3A%7B%22WINRM_MCP_HOST%22%3A%22%24%7Binput%3Awinrm_mcp_host%7D%22%2C%22WINRM_MCP_USERNAME%22%3A%22%24%7Binput%3Awinrm_mcp_username%7D%22%2C%22WINRM_MCP_PASSWORD%22%3A%22%24%7Binput%3Awinrm_mcp_password%7D%22%7D%7D&quality=insiders)
[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=winrm&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLWZyb20iLCJnaXQraHR0cHM6Ly9naXRodWIuY29tL2JpZ2JhdG1hbm9yZy93aW5ybS1tY3AuZ2l0QHYwLjMuMCIsIndpbnJtLW1jcCJdLCJlbnYiOnsiV0lOUk1fTUNQX0hPU1QiOiIxOTIuMTY4LjEuNTAiLCJXSU5STV9NQ1BfVVNFUk5BTUUiOiJBZG1pbmlzdHJhdG9yIiwiV0lOUk1fTUNQX1BBU1NXT1JEIjoieW91ci1wYXNzd29yZCJ9fQ%3D%3D)

It works with any MCP client that can start a stdio command. It needs [uv](https://docs.astral.sh/uv/). `uvx` fetches the pinned release, so no clone or virtualenv is needed. Pick your agent below.

| Variable | Meaning | Example |
|---|---|---|
| `WINRM_MCP_HOST` | Default Windows host | `192.168.1.50` |
| `WINRM_MCP_USERNAME` | Default user | `Administrator` |
| `WINRM_MCP_PASSWORD` | Default password | `your-password` |

All three are optional defaults. Without them, pass the connection in each tool call or use the [multi-host inventory](#multi-host-inventory). Other defaults use the same `WINRM_MCP_` prefix: `WINRM_MCP_AUTH` (`ntlm`), `WINRM_MCP_SSL`, `WINRM_MCP_PORT`, `WINRM_MCP_CERT_VALIDATION`. See [Install and run](#install-and-run).

The VS Code buttons ask for each value, keeping secrets out of files. The Cursor button writes placeholders: edit them in `~/.cursor/mcp.json` afterwards. Elsewhere, replace the example values.

<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add winrm -s user -e WINRM_MCP_HOST=192.168.1.50 -e WINRM_MCP_USERNAME=Administrator -e WINRM_MCP_PASSWORD=your-password -- uvx --from git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0 winrm-mcp
```

</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      }
    }
  }
}
```

</details>

<details>
<summary><b>VS Code / GitHub Copilot</b></summary>

Use the button above, or add this to `.vscode/mcp.json` (workspace) or to the user `mcp.json` (command
*MCP: Open User Configuration*):

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "winrm_mcp_host",
      "description": "Default Windows host",
      "password": false
    },
    {
      "type": "promptString",
      "id": "winrm_mcp_username",
      "description": "Default user",
      "password": false
    },
    {
      "type": "promptString",
      "id": "winrm_mcp_password",
      "description": "Default password",
      "password": true
    }
  ],
  "servers": {
    "winrm": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "${input:winrm_mcp_host}",
        "WINRM_MCP_USERNAME": "${input:winrm_mcp_username}",
        "WINRM_MCP_PASSWORD": "${input:winrm_mcp_password}"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Cursor</b></summary>

Use the button above, or add this to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project):

```json
{
  "mcpServers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Windsurf</b></summary>

Add this to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      }
    }
  }
}
```

</details>

<details>
<summary><b>OpenAI Codex CLI</b></summary>

```bash
codex mcp add winrm --env WINRM_MCP_HOST=192.168.1.50 --env WINRM_MCP_USERNAME=Administrator --env WINRM_MCP_PASSWORD=your-password -- uvx --from git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0 winrm-mcp
```

Or add this to `~/.codex/config.toml`:

```toml
[mcp_servers.winrm]
command = "uvx"
args = ["--from", "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0", "winrm-mcp"]
env = { WINRM_MCP_HOST = "192.168.1.50", WINRM_MCP_USERNAME = "Administrator", WINRM_MCP_PASSWORD = "your-password" }
```

</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add this to `~/.gemini/settings.json` (or to `.gemini/settings.json` in a project):

```json
{
  "mcpServers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      }
    }
  }
}
```

</details>

<details>
<summary><b>DeepAgents</b></summary>

**Deep Agents CLI:** add this to `~/.deepagents/.mcp.json` (all projects) or to `.mcp.json` in a project. `${VAR}` values are read from your shell or `~/.deepagents/.env`, so secrets stay out of the file.

```json
{
  "mcpServers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "${WINRM_MCP_HOST}",
        "WINRM_MCP_USERNAME": "${WINRM_MCP_USERNAME}",
        "WINRM_MCP_PASSWORD": "${WINRM_MCP_PASSWORD}"
      }
    }
  }
}
```

**Python library** (`pip install deepagents langchain-mcp-adapters`):

```python
import asyncio
import os

from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "winrm": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["--from", "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0", "winrm-mcp"],
        "env": {
            "WINRM_MCP_HOST": os.environ["WINRM_MCP_HOST"],
            "WINRM_MCP_USERNAME": os.environ["WINRM_MCP_USERNAME"],
            "WINRM_MCP_PASSWORD": os.environ["WINRM_MCP_PASSWORD"],
        },
    }
})


async def main():
    tools = await client.get_tools()
    agent = create_deep_agent(model="anthropic:claude-sonnet-5-5", tools=tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "What can you do?"}]})
    print(result["messages"][-1].content)


asyncio.run(main())
```

</details>

<details>
<summary><b>Docker Agent</b></summary>

Save this as `agent.yaml`, then run `docker agent run agent.yaml`:

```yaml
agents:
  root:
    model: anthropic/claude-sonnet-5-5
    description: Assistant with the winrm MCP tools
    instruction: Use the winrm tools to answer the user's requests.
    toolsets:
      - type: mcp
        command: uvx
        args:
          - "--from"
          - "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0"
          - "winrm-mcp"
        env:
          WINRM_MCP_HOST: "192.168.1.50"
          WINRM_MCP_USERNAME: "Administrator"
          WINRM_MCP_PASSWORD: "your-password"
```

</details>

<details>
<summary><b>Hermes Agent</b></summary>

Add this to `~/.hermes/config.yaml`, then run `/reload-mcp` in a chat:

```yaml
mcp_servers:
  winrm:
    command: uvx
    args: ["--from", "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0", "winrm-mcp"]
    env:
      WINRM_MCP_HOST: "192.168.1.50"
      WINRM_MCP_USERNAME: "Administrator"
      WINRM_MCP_PASSWORD: "your-password"
```

</details>

<details>
<summary><b>Cline / Roo Code / Kilo Code</b></summary>

MCP Servers → Configure (`cline_mcp_settings.json` / `mcp_settings.json`):

```json
{
  "mcpServers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Zed</b></summary>

Add this to `settings.json`:

```json
{
  "context_servers": {
    "winrm": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "env": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      }
    }
  }
}
```

</details>

<details>
<summary><b>opencode</b></summary>

Add this to `opencode.json` (project) or `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "winrm": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0",
        "winrm-mcp"
      ],
      "environment": {
        "WINRM_MCP_HOST": "192.168.1.50",
        "WINRM_MCP_USERNAME": "Administrator",
        "WINRM_MCP_PASSWORD": "your-password"
      },
      "enabled": true
    }
  }
}
```

</details>

<details>
<summary><b>Goose</b></summary>

Run `goose configure` → Add Extension → Command-line Extension, with the command `uvx --from git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0 winrm-mcp`. Or add this to
`~/.config/goose/config.yaml`:

```yaml
extensions:
  winrm:
    type: stdio
    enabled: true
    cmd: uvx
    args: ["--from", "git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0", "winrm-mcp"]
    envs:
      WINRM_MCP_HOST: "192.168.1.50"
      WINRM_MCP_USERNAME: "Administrator"
      WINRM_MCP_PASSWORD: "your-password"
```

</details>

<details>
<summary><b>Other clients, a permanent install, a local checkout</b></summary>

Most clients take the standard `mcpServers` JSON shown for Claude Desktop. Some use `servers` instead.

To install once instead of fetching on each start:

```bash
uv tool install git+https://github.com/bigbatmanorg/winrm-mcp.git@v0.3.0
```

then use `"command": "winrm-mcp"`, `"args": []`.

From a checkout: `"command": "uv"`, `"args": ["run", "--directory", "/abs/path/winrm-mcp", "winrm-mcp"]`.

</details>

<!-- install:end -->

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

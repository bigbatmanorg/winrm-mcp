# Changelog

## 0.3.0 — 2026-11-03

### Fixed
- **Exit codes:** PowerShell `exit N` now reports N. It used to be reported as exit 0 / `ok: true`.
- **Timeouts:** a timed-out command is now stopped (PowerShell) or terminated (CMD) on the remote host. Previously the caller got an error but the command kept running.
- **CMD `env`:** values are now set through WinRS as real process variables, so `%NAME%` works. Before, `set` ran after cmd had already expanded the line.
- **`auth`** is validated. `certificate` auth now works, using `certificate_pem` / `certificate_key_pem`.

### Added
- **`winrm_execute_many`:** runs a command on several saved hosts, by name or tag, in parallel, with one result or error per host.
- **`winrm_upload` / `winrm_download`:** file transfer confined to `WINRM_MCP_LOCAL_ROOT`, and disabled unless it is set.
- **`output_format="json"`** for PowerShell, returning parsed objects in `data`.
- **`winrm_test`** now reports `is_admin`.
- **Security policy:**
  - `WINRM_MCP_ALLOWED_HOSTS` restricts which hosts can be reached.
  - `WINRM_MCP_ALLOW_ADHOC` can disable ad-hoc connections.
  - `WINRM_MCP_SECRET_ENV_PATTERNS` limits which variables `password_env` may read.
  - Basic auth over plain HTTP is refused unless `WINRM_MCP_ALLOW_INSECURE_BASIC=true`.
  - `winrm_policy` shows the active policy.
- **Inventory `tags`**, with filtering in `winrm_host_list`.
- **MCP annotations** on every tool.
- **Testing:** CI runs on Python 3.10, 3.12 and 3.13, and an opt-in live suite (`WINRM_LIVE=1`) runs through the real MCP stdio server.

### Changed
- `.env` is now gitignored.
- The README no longer contains a local path, and it has new security and testing sections.

## 0.2.2 — 2026-08-22

Accept string `null` sentinels for the optional connection argument.

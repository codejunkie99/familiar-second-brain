# Installation

The installer copies the MCP server and Kimi skill into the local app paths, then updates MCP configs for apps that support a JSON or TOML MCP registration.

## Dry Run

```bash
cd /Users/<your-username>/Downloads/familiar-second-brain
/usr/bin/python3 scripts/install.py --dry-run
```

## Install

```bash
/usr/bin/python3 scripts/install.py
```

## Custom Vault

```bash
/usr/bin/python3 scripts/install.py \
  --vault "$HOME/Documents/kimi/workspace/familiar-vault"
```

## Configs Updated

The installer updates these files when present:

```text
~/.codex/config.toml
~/.claude/mcp_servers.json
~/.cursor/mcp.json
~/Library/Application Support/Claude/claude_desktop_config.json
~/Library/Application Support/Claude-3p/claude_desktop_config.json
~/Library/Application Support/kimi-desktop/daimon-share/daimon/config.json
~/Library/Application Support/kimi-desktop/daimon-share/daimon/runtime/kimi-code/home/mcp.json
```

Backups are written beside each changed config as `*.bak.YYYYMMDD-HHMMSS`.

## Kimi Reload

Kimi Work may need a new work session or an app restart before it loads a newly added MCP server. Existing sessions can keep the tool list they started with.

## Manual MCP Entry

For JSON MCP configs:

```json
{
  "mcpServers": {
    "familiar": {
      "command": "/usr/bin/python3",
      "args": [
        "/Users/<your-username>/Documents/kimi/workspace/familiar-vault/.familiar/mcp/familiar_mcp_server.py"
      ]
    }
  }
}
```

For Codex TOML:

```toml
[mcp_servers.familiar]
command = "/usr/bin/python3"
args = ["/Users/<your-username>/Documents/kimi/workspace/familiar-vault/.familiar/mcp/familiar_mcp_server.py"]
startup_timeout_sec = 30
```

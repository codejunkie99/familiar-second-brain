# Security

Familiar Second Brain is a local integration. It should not require uploading the vault or app databases anywhere.

## What The Repo Excludes

This repo does not include:

- Personal Familiar notes.
- Kimi session transcripts.
- Kimi API keys.
- App databases.
- Generated state files.

## Path Safety

The MCP server resolves every requested note path against the configured vault. It rejects paths outside the vault and hides `.familiar` internals from MCP note tools.

## Config Backups

The installer creates timestamped backups before modifying app configs:

```text
config.json.bak.YYYYMMDD-HHMMSS
mcp.json.bak.YYYYMMDD-HHMMSS
config.toml.bak.YYYYMMDD-HHMMSS
```

## Model Calls

`summarize_sessions.py` can call Kimi's local model endpoint when `--no-model` is not used. It adds the Kimi desktop user agent required by the local Kimi endpoint.

Use this when you want better summaries:

```bash
/usr/bin/python3 kimi_skill/scripts/summarize_sessions.py
```

Use this when you want deterministic local extraction only:

```bash
/usr/bin/python3 kimi_skill/scripts/summarize_sessions.py --no-model
```

## Operational Rule

Do not commit live vault contents, app support directories, credentials, or generated session transcripts into this repo.

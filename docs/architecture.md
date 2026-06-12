# Architecture

Familiar Second Brain is intentionally local-first. The vault is just Markdown, the MCP server is a stdio process, and Kimi Work capture reads local Kimi session logs.

![Animated Familiar data flow](assets/familiar-flow.svg)

## Components

| Component | Responsibility |
| --- | --- |
| Familiar vault | Durable Markdown storage for notes, sessions, transcripts, research, and project context |
| Kimi skill | Teaches Kimi Work when to read from or save to the vault |
| Session summarizer | Converts Kimi session records into summary and transcript notes |
| MCP server | Gives MCP clients a tool interface over the vault |
| App configs | Register the same MCP server with Kimi Work, Codex, Claude, and Cursor |

## Data Flow

1. Kimi Work creates session records in its local Daimon runtime.
2. `summarize_sessions.py` reads hosted session metadata and `wire.jsonl` records.
3. Session summaries are written to `Daily/Kimi Sessions/`.
4. Full transcripts are written to `Daily/Kimi Transcripts/`.
5. MCP clients use `familiar_mcp_server.py` to search, read, and write Markdown notes.

## Vault Contract

The MCP server only works inside the configured vault. It rejects:

- Path traversal such as `../outside.md`.
- Hidden `.familiar` internals.
- Non-Markdown writes through note tools.

This keeps MCP clients focused on user-facing notes instead of internal state.

## State Tracking

The Kimi session capture job stores fingerprints in:

```text
.familiar/kimi-session-summarizer-state.json
```

Each session entry tracks:

- `fingerprint`
- `note`
- `transcript`
- `updatedAt`
- `summarizedAt`

If the Kimi session files have not changed, the capture job skips rewriting notes.

## Maintenance Filtering

Scheduled Kimi jobs can create their own maintenance sessions. The summarizer ignores sessions whose prompt starts with the Familiar maintenance marker and references `summarize_sessions.py`, so the brain does not fill with self-generated cron chatter.

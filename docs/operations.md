# Operations

## Capture Kimi Sessions

Run deterministic capture without calling the Kimi model:

```bash
/usr/bin/python3 kimi_skill/scripts/summarize_sessions.py --no-model
```

Run model-backed summaries using Kimi's local model config:

```bash
/usr/bin/python3 kimi_skill/scripts/summarize_sessions.py
```

Outputs:

```text
Daily/Kimi Sessions/
Daily/Kimi Transcripts/
```

## Generate A Daily Brain Brief

Create a deterministic daily brief without calling a model:

```bash
/usr/bin/python3 kimi_skill/scripts/brain_brief.py \
  --vault "$HOME/Documents/kimi/workspace/familiar-vault" \
  --date "$(date +%F)" \
  --no-model
```

Output:

```text
Daily/YYYY-MM-DD Brain Brief.md
```

The brief includes changed session notes, inbox notes, decisions, open loops, reserved resurfacing space, and source paths.

## Save A Note From Kimi Work

```bash
/usr/bin/python3 kimi_skill/scripts/save_to_familiar.py \
  --vault "$HOME/Documents/kimi/workspace/familiar-vault" \
  --title "Project decision" \
  --content "The durable thing to remember." \
  --links "Kimi Work,Second Brain" \
  --kind "memory"
```

## MCP Smoke Test

```bash
/usr/bin/python3 scripts/smoke_mcp.py \
  --vault "$HOME/Documents/kimi/workspace/familiar-vault"
```

Expected output includes:

- Tool names such as `save_memory`, `search_memory`, and `vault_status`.
- Vault paths for `_Inbox`, `Daily/Kimi Sessions`, and `Daily/Kimi Transcripts`.

## Retrieval Behavior

The `search_memory` MCP tool ranks notes using:

- note title
- frontmatter tags
- Markdown headings
- `[[wikilinks]]`
- note body

Each match keeps the original `excerpt` field for compatibility and also returns:

```json
{
  "matched_fields": ["title", "headings", "body"],
  "contexts": [
    {
      "heading": "Summary",
      "text": "Compact context window..."
    }
  ]
}
```

## Test Suite

```bash
make test
```

The tests cover:

- MCP stdio framing.
- Vault path safety.
- Save/search/read behavior.
- Kimi session summary capture.
- Kimi transcript capture.
- Daily brain brief generation.
- Maintenance-session filtering.

## Updating The Live Install

After editing source files:

```bash
/usr/bin/python3 scripts/install.py
```

Then restart or reopen any MCP client that caches tool definitions.

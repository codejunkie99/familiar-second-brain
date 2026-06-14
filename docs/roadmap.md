# Feature Roadmap

This roadmap keeps visual wow features and daily-use automation separated so branches can merge with minimal conflicts.

## Phase 1: Daily-Use Engine

Build the data layer first. The UI should read these outputs instead of inventing its own state.

| Feature | Output | Main files |
| --- | --- | --- |
| Automatic daily brief note | `Daily/YYYY-MM-DD Brain Brief.md` | `kimi_skill/scripts/brain_brief.py`, tests |
| Project-specific memory briefs | `Projects/<project>/Brief.md` | `kimi_skill/scripts/project_briefs.py`, tests |
| Smart inbox triage | suggested moves, links, tags, merges | `kimi_skill/scripts/inbox_triage.py`, tests |
| Higher-quality retrieval | ranked note results with context windows | `src/familiar_mcp_server.py`, tests |

## Phase 2: Trust And Recall

Add quality controls after the brain can already summarize and triage.

| Feature | Output | Main files |
| --- | --- | --- |
| Duplicate detection | candidate duplicate note list | `kimi_skill/scripts/vault_audit.py`, tests |
| Contradiction detection | conflict report with source paths | `kimi_skill/scripts/vault_audit.py`, tests |
| Recurring resurfacing | `Daily/Resurfaced/` notes or daily brief section | `kimi_skill/scripts/resurface.py`, tests |

## Phase 3: Visual Dashboard

Only build the dashboard once Phase 1 has real files to display.

| Feature | Output | Main files |
| --- | --- | --- |
| Dashboard shell | local web app | `dashboard/` |
| Memory graph UI | graph from wikilinks and references | `dashboard/src/graph/*` |
| Kimi timeline playback | session replay from transcript notes | `dashboard/src/timeline/*` |
| Visual inbox | triage queue UI | `dashboard/src/inbox/*` |
| Live capture status | capture state and last run health | `dashboard/src/status/*` |

## Branch Strategy

Use one branch per workstream:

```text
feature/daily-brief-engine
feature/project-briefs
feature/smart-inbox-triage
feature/retrieval-upgrade
feature/vault-audit
feature/resurfacing
feature/dashboard-shell
```

Merge order:

1. Daily brief engine
2. Retrieval upgrade
3. Smart inbox triage
4. Project briefs
5. Vault audit
6. Resurfacing
7. Dashboard shell

## Conflict Rules

- Scripts under `kimi_skill/scripts/` should each own one workflow.
- Shared vault parsing helpers should be extracted only when two scripts need the same behavior.
- MCP protocol changes should stay in `src/familiar_mcp_server.py` and its tests.
- Dashboard work should not modify capture scripts unless the data contract changes first.
- Each branch must run `make test` before merge.

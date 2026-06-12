---
name: familiar-second-brain
description: Always use when working in Kimi Work desktop sessions that should read from or save to the user's Familiar second brain. Trigger for memory, notes, projects, prior work, research, summaries, durable outputs, "save this", "remember this", "from my brain", "what do I know", or any request that should use the local Markdown vault.
dependencies: []
---

# Familiar Second Brain

The user's second brain is the current Kimi Work workspace. It is a Familiar Markdown vault: plain `.md` files, folders, YAML frontmatter, and `[[wikilinks]]`.

## Core Rule

For desktop work, treat the workspace as the durable brain. Do not save final work to Desktop unless the user explicitly asks. Save durable notes, summaries, project plans, research, decisions, and reusable context into this vault.

## Read From The Brain

Before answering questions about the user's memory, prior work, projects, notes, plans, research, or "what do I know about X":

1. Search Markdown files in the workspace with `rg -n "query|keywords" . --glob "*.md"`.
2. Read the most relevant notes.
3. Answer from those notes first.
4. Mention the note paths used when useful.
5. If the vault has no relevant notes, say that directly and answer from general reasoning only if appropriate.

## Save To The Brain

Use `scripts/save_to_familiar.py` for quick captures and durable notes:

```bash
python3 "$KIMI_SKILL_DIR/scripts/save_to_familiar.py" \
  --vault "$PWD" \
  --title "Short title" \
  --content "Markdown content to preserve" \
  --links "Kimi Work,Second Brain" \
  --kind "memory"
```

If `KIMI_SKILL_DIR` is not set, use the absolute skill directory:

```bash
python3 "$HOME/Library/Application Support/kimi-desktop/daimon-share/daimon/skills/familiar-second-brain/scripts/save_to_familiar.py" ...
```

## Organization

- `_Inbox/`: unsorted captures, quick memories, raw session takeaways.
- `Projects/`: project-specific work, plans, implementation notes.
- `Research/`: research notes and synthesized findings.
- `People/`: people, orgs, relationship notes.
- `Ideas/`: concepts, product ideas, strategy thoughts.
- `Daily/`: daily logs and rolling context.
- `_Attachments/`: PDFs, CSVs, images, exports, generated assets.

Use `_Inbox` when unsure. Prefer plain Markdown. Add frontmatter with `source: kimi-work`. Add `[[wikilinks]]` for important people, projects, concepts, and decisions.

## Automatic Session Summaries

The local helper `scripts/summarize_sessions.py` summarizes Kimi Work sessions into:

```text
Daily/Kimi Sessions/
```

It tracks fingerprints in `.familiar/kimi-session-summarizer-state.json`, so it only rewrites notes for sessions that changed. These summaries are normal Familiar notes with `source: kimi-work` and `kind: session-summary`.

If the user asks whether Kimi sessions are saved to the second brain, check `Daily/Kimi Sessions/` and `_Inbox/` before answering.

## Daily Brain Brief

Use `scripts/brain_brief.py` when the user asks what the brain learned today, wants a daily summary, or asks for current open loops:

```bash
python3 "$KIMI_SKILL_DIR/scripts/brain_brief.py" \
  --vault "$PWD" \
  --date "$(date +%F)" \
  --no-model
```

It writes a deterministic note to:

```text
Daily/YYYY-MM-DD Brain Brief.md
```

The note includes changed session context, inbox captures, decisions, open loops, and source paths.

## Inbox Triage

Use `scripts/inbox_triage.py` when the user asks to clean up, organize, or file unsorted memories:

```bash
python3 "$KIMI_SKILL_DIR/scripts/inbox_triage.py" \
  --vault "$PWD"
```

This previews suggested destinations, tags, links, and merge candidates. Only use `--apply` after the user wants the suggested moves applied:

```bash
python3 "$KIMI_SKILL_DIR/scripts/inbox_triage.py" \
  --vault "$PWD" \
  --apply
```

The apply mode only moves files. It does not rewrite note content.

## Project Briefs

Use `scripts/project_briefs.py` when the user asks for project state, project memory, or a current project summary:

```bash
python3 "$KIMI_SKILL_DIR/scripts/project_briefs.py" \
  --vault "$PWD" \
  --no-model
```

It writes or refreshes:

```text
Projects/<project>/Brief.md
```

Project briefs include project notes, related sessions, related inbox notes, decisions, open loops, and source paths.

## Default Behaviors

- "Remember this" or "save this" means create a Markdown note.
- "Summarize this session" means save a concise session summary.
- "What did the brain learn today?" means generate or read the daily brain brief.
- "Clean up my inbox" means run inbox triage in preview mode first.
- "What is the state of this project?" means generate or read project briefs.
- "From my brain" means search the vault before answering.
- Project deliverables should be saved under `Projects/` when the project name is clear.
- Never expose or edit Kimi Work private tokens, credentials, or internal app databases for second-brain behavior.

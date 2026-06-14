#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"
MAINTENANCE_PROMPT_PREFIX = "Run the Familiar second brain session summarizer now."
MAINTENANCE_COMMAND_MARKER = "summarize_sessions.py"
MAX_ITEMS_PER_SECTION = 8
SECTION_LABELS = {
    "summary",
    "decisions",
    "outputs",
    "follow-ups",
    "followups",
    "follow ups",
    "links",
    "messages",
    "last prompt",
}
INTERNAL_NOISE_MARKERS = (
    "TodoList tool",
    "NEVER mention",
    "gentle reminder",
    "Current todo list",
    "skill",
)


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def parse_frontmatter(body: str) -> dict:
    if not body.startswith("---\n"):
        return {}
    end = body.find("\n---", 4)
    if end < 0:
        return {}
    data = {}
    for line in body[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def strip_frontmatter(body: str) -> str:
    if not body.startswith("---\n"):
        return body
    end = body.find("\n---", 4)
    if end < 0:
        return body
    return body[end + 4 :].lstrip()


def title_from_body(path: Path, body: str) -> str:
    for line in strip_frontmatter(body).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def source_date(path: Path, frontmatter: dict) -> str:
    created = frontmatter.get("created", "")
    if created:
        return created[:10]
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else ""


def is_maintenance_note(body: str) -> bool:
    return MAINTENANCE_PROMPT_PREFIX in body and MAINTENANCE_COMMAND_MARKER in body


def is_generated_brief(path: Path) -> bool:
    return path.name.endswith(" Brain Brief.md")


def clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-*]\s+", "", line)
    line = re.sub(r"^\d+\.\s+", "", line)
    return line.strip()


def notable_lines(body: str) -> list[str]:
    lines = []
    in_links = False
    for raw in strip_frontmatter(body).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            in_links = line.lower().strip("# ").strip() == "links"
            continue
        if in_links:
            continue
        item = clean_line(line)
        label = item.strip("*").strip().lower()
        if label in SECTION_LABELS:
            continue
        if any(marker in item for marker in INTERNAL_NOISE_MARKERS):
            continue
        if item and not item.startswith("[") and len(item) > 12:
            lines.append(item)
    return dedupe(lines)


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        key = re.sub(r"\s+", " ", item.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract_matching(lines: list[str], patterns: tuple[str, ...]) -> list[str]:
    out = []
    for line in lines:
        lowered = line.lower()
        if any(pattern in lowered for pattern in patterns):
            out.append(line)
    return dedupe(out)


def collect_sources(vault: Path, day: str) -> list[dict]:
    candidates = []
    groups = [
        ("session", vault / "Daily" / "Kimi Sessions"),
        ("transcript", vault / "Daily" / "Kimi Transcripts"),
        ("inbox", vault / "_Inbox"),
    ]
    for kind, directory in groups:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if is_generated_brief(path):
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            if is_maintenance_note(body):
                continue
            frontmatter = parse_frontmatter(body)
            if source_date(path, frontmatter) != day:
                continue
            candidates.append(
                {
                    "kind": kind,
                    "path": path,
                    "rel": str(path.relative_to(vault)),
                    "title": title_from_body(path, body),
                    "body": body,
                    "lines": notable_lines(body),
                }
            )
    return candidates


def bullet_list(items: list[str], empty: str) -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items[:MAX_ITEMS_PER_SECTION]]


def build_brief(vault: Path, day: str, sources: list[dict]) -> str:
    session_lines = []
    inbox_lines = []
    decisions = []
    open_loops = []
    for source in sources:
        if source["kind"] == "transcript":
            continue
        lines = source["lines"]
        decisions.extend(extract_matching(lines, ("decision:", "decided", "choose ", "chosen ", "use ")))
        open_loops.extend(extract_matching(lines, ("follow up", "follow-up", "next", "todo", "open loop", "action:")))
        if source["kind"] == "session":
            session_lines.extend(lines)
        elif source["kind"] == "inbox":
            inbox_lines.extend(lines)

    what_changed = dedupe(session_lines + inbox_lines)
    source_lines = [f"- `{source['rel']}` - {source['title']}" for source in sources]
    sections = [
        "---",
        f"created: {day}T00:00:00Z",
        "source: familiar-second-brain",
        "kind: brain-brief",
        f"date: {day}",
        "---",
        "",
        f"# {day} Brain Brief",
        "",
        "## What Changed",
        "",
        *bullet_list(what_changed, "No new Familiar notes were found for this date."),
        "",
        "## Decisions",
        "",
        *bullet_list(dedupe(decisions), "No explicit decisions were detected."),
        "",
        "## Open Loops",
        "",
        *bullet_list(dedupe(open_loops), "No open loops were detected."),
        "",
        "## Inbox",
        "",
        *bullet_list(dedupe(inbox_lines), "No inbox notes were captured for this date."),
        "",
        "## Resurfaced Context",
        "",
        "- Resurfacing is not enabled yet. This section is reserved for the recurring resurfacing workflow.",
        "",
        "## Sources",
        "",
        *(source_lines or ["- No source notes found."]),
        "",
    ]
    return "\n".join(sections)


def write_if_changed(path: Path, body: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == body:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return True


def process(args) -> dict:
    vault = Path(args.vault).expanduser().resolve()
    day = args.date or today()
    sources = collect_sources(vault, day)
    target = vault / "Daily" / f"{day} Brain Brief.md"
    body = build_brief(vault, day, sources)
    written = write_if_changed(target, body)
    return {
        "ok": True,
        "date": day,
        "path": str(target),
        "written": written,
        "sources_count": len(sources),
        "sources": [source["rel"] for source in sources],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a daily Familiar brain brief.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--date", default="")
    parser.add_argument("--no-model", action="store_true", help="Accepted for deterministic local extraction")
    args = parser.parse_args()
    try:
        print(json.dumps(process(args), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

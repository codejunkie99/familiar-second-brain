#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"
DEFAULT_STATE = ".familiar/resurface-state.json"
STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "brief",
    "briefs",
    "daily",
    "from",
    "have",
    "note",
    "notes",
    "project",
    "should",
    "that",
    "the",
    "this",
    "today",
    "with",
    "work",
    "worked",
}


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def tokens(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"\W+", text.lower())
        if len(token) >= 4 and token not in STOPWORDS and not token.isdigit()
    }


def excerpt(body: str, max_chars: int = 180) -> str:
    lines = []
    in_links = False
    for raw in strip_frontmatter(body).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            in_links = line.strip("# ").lower() == "links"
            continue
        if in_links:
            continue
        lines.append(re.sub(r"^[-*]\s+", "", line))
    return re.sub(r"\s+", " ", " ".join(lines)).strip()[:max_chars]


def iter_notes(vault: Path):
    for path in sorted(vault.rglob("*.md")):
        rel_parts = path.relative_to(vault).parts
        if ".familiar" in rel_parts or any(part.startswith(".") for part in rel_parts):
            continue
        if len(rel_parts) >= 2 and rel_parts[0] == "Daily" and rel_parts[1] in {"Kimi Sessions", "Kimi Transcripts"}:
            continue
        if rel_parts and rel_parts[0] == "_Inbox":
            continue
        if "Resurfaced" in rel_parts or path.name.endswith("Brain Brief.md") or path.name == "Brief.md":
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        yield {
            "path": path,
            "rel": str(path.relative_to(vault)),
            "title": title_from_body(path, body),
            "body": body,
            "tokens": tokens(f"{path.stem}\n{body}"),
            "excerpt": excerpt(body),
        }


def recent_context(vault: Path, day: str) -> set[str]:
    roots = [vault / "Daily" / "Kimi Sessions", vault / "_Inbox", vault / "Projects"]
    chunks = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if path.name == "Brief.md":
                continue
            rel = str(path.relative_to(vault))
            if day in path.name or "_Inbox" in rel or "Projects" in rel:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return tokens("\n".join(chunks))


def select_items(vault: Path, day: str, limit: int, state: dict) -> list[dict]:
    context = recent_context(vault, day)
    already = set((state.get("resurfaced") or {}).keys())
    candidates = []
    for note in iter_notes(vault):
        if note["rel"] in already:
            continue
        score = len(context & note["tokens"])
        if score < 2 or not note["excerpt"]:
            continue
        candidates.append((score, note["rel"], note))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "source_path": note["rel"],
            "title": note["title"],
            "score": score,
            "excerpt": note["excerpt"],
        }
        for score, _, note in candidates[:limit]
    ]


def build_note(day: str, items: list[dict]) -> str:
    lines = [
        "---",
        f"created: {day}T00:00:00Z",
        "source: familiar-second-brain",
        "kind: resurfaced-notes",
        f"date: {day}",
        "---",
        "",
        f"# {day} Resurfaced Notes",
        "",
    ]
    if not items:
        lines.extend(["- No resurfaced notes for this run.", ""])
        return "\n".join(lines)
    for item in items:
        lines.extend(
            [
                f"## {item['title']}",
                "",
                f"- Source: `{item['source_path']}`",
                f"- Score: {item['score']}",
                f"- Context: {item['excerpt']}",
                "",
            ]
        )
    return "\n".join(lines)


def process(args) -> dict:
    vault = Path(args.vault).expanduser().resolve()
    day = args.date or today()
    state_path = Path(args.state).expanduser() if args.state else vault / DEFAULT_STATE
    state = load_json(state_path, {"resurfaced": {}})
    state.setdefault("resurfaced", {})
    items = select_items(vault, day, max(1, args.limit), state)
    written = 0
    if items:
        target = vault / "Daily" / "Resurfaced" / f"{day} Resurfaced Notes.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_note(day, items), encoding="utf-8")
        for item in items:
            state["resurfaced"][item["source_path"]] = day
        write_json(state_path, state)
        written = len(items)
    return {
        "ok": True,
        "date": day,
        "written_count": written,
        "items": items,
        "state": str(state_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resurface older useful Familiar notes.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--date", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--state", default="")
    args = parser.parse_args()
    try:
        print(json.dumps(process(args), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

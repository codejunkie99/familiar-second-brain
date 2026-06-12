#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def slugify(value: str, fallback: str = "note") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#`\\[\\]()\\n\\r]+", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned[:72].strip() or fallback)


def unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        next_candidate = directory / f"{stem} {index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def parse_links(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def build_note(title: str, content: str, kind: str, links: list[str]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    link_block = "\n".join(f"- [[{link}]]" for link in links)
    sections = [
        "---",
        f"created: {now}",
        "source: kimi-work",
        f"kind: {kind}",
        "---",
        "",
        f"# {title}",
        "",
        content.strip(),
    ]
    if link_block:
        sections.extend(["", "## Links", link_block])
    sections.append("")
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a Kimi Work output into a Familiar Markdown vault.")
    parser.add_argument("--vault", required=True, help="Path to the Familiar vault")
    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--links", default="")
    parser.add_argument("--kind", default="note")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    inbox = vault / "_Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    title = slugify(args.title, "Kimi Work note")
    stamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    note_path = unique_path(inbox, f"{stamp} {title}.md")
    note_path.write_text(build_note(title, args.content, args.kind, parse_links(args.links)), encoding="utf-8")

    print(json.dumps({"ok": True, "path": str(note_path), "rel": str(note_path.relative_to(vault))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

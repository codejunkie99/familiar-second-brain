#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import sys
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"


def title_from_body(path: Path, body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def content_without_links(body: str) -> str:
    lines = []
    in_links = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            in_links = stripped.strip("# ").lower() == "links"
            if in_links:
                continue
        if in_links:
            continue
        lines.append(line)
    return "\n".join(lines)


def slug_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#`\[\]()\n\r]+", " ", name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "Inbox note") + ".md"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = path.with_name(f"{stem} {index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def classify_note(title: str, body: str) -> dict:
    text = f"{title}\n{content_without_links(body)}".lower()
    if any(term in text for term in ("stock", "equity", "valuation", "research", "analysis", "ipo", "spacex", "nvidia")):
        return {
            "folder": "Research",
            "tags": ["research"],
            "links": ["Research"],
            "reason": "Looks like research or market analysis.",
        }
    if any(term in text for term in ("familiar", "kimi", "mcp", "dashboard", "memory graph", "second brain")):
        return {
            "folder": "Projects/Familiar Second Brain",
            "tags": ["familiar", "second-brain", "dashboard"] if "dashboard" in text else ["familiar", "second-brain"],
            "links": ["Familiar", "Kimi Work", "Second Brain"],
            "reason": "Matches Familiar/Kimi second-brain project terms.",
        }
    if any(term in text for term in ("person", "met ", "call with", "email from")):
        return {
            "folder": "People",
            "tags": ["people"],
            "links": ["People"],
            "reason": "Looks like a people or relationship note.",
        }
    if any(term in text for term in ("idea", "concept", "brainstorm")):
        return {
            "folder": "Ideas",
            "tags": ["idea"],
            "links": ["Ideas"],
            "reason": "Looks like an idea or concept note.",
        }
    return {
        "folder": "_Inbox",
        "tags": [],
        "links": [],
        "reason": "No confident destination detected.",
    }


def collect_suggestions(vault: Path) -> list[dict]:
    inbox = vault / "_Inbox"
    suggestions = []
    if not inbox.exists():
        return suggestions
    for path in sorted(inbox.glob("*.md")):
        body = path.read_text(encoding="utf-8", errors="replace")
        title = title_from_body(path, body)
        classification = classify_note(title, body)
        target_rel = str(Path(classification["folder"]) / slug_filename(title))
        action = "keep" if classification["folder"] == "_Inbox" else "move"
        suggestions.append(
            {
                "source_path": str(path.relative_to(vault)),
                "title": title,
                "action": action,
                "target_path": target_rel,
                "tags": classification["tags"],
                "links": classification["links"],
                "reason": classification["reason"],
                "merge_candidates": [],
            }
        )
    return suggestions


def safe_target(vault: Path, rel_path: str) -> Path:
    target = (vault / rel_path).resolve()
    if target != vault and vault not in target.parents:
        raise ValueError("target path escaped vault")
    if ".familiar" in target.relative_to(vault).parts:
        raise ValueError("target path points at Familiar internals")
    return target


def apply_suggestions(vault: Path, suggestions: list[dict]) -> int:
    moved = 0
    for suggestion in suggestions:
        if suggestion["action"] != "move":
            continue
        source = safe_target(vault, suggestion["source_path"])
        target = unique_path(safe_target(vault, suggestion["target_path"]))
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        suggestion["applied_path"] = str(target.relative_to(vault))
        moved += 1
    return moved


def process(args) -> dict:
    vault = Path(args.vault).expanduser().resolve()
    suggestions = collect_suggestions(vault)
    moved = apply_suggestions(vault, suggestions) if args.apply else 0
    return {
        "ok": True,
        "applied": bool(args.apply),
        "suggestions_count": len(suggestions),
        "moved_count": moved,
        "suggestions": suggestions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest or apply Familiar inbox triage moves.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--apply", action="store_true", help="Move notes to suggested destinations")
    args = parser.parse_args()
    try:
        print(json.dumps(process(args), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

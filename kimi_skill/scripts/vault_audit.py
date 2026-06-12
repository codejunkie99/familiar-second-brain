#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
from itertools import combinations
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"


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


def normalized_text(body: str) -> str:
    text = strip_frontmatter(body)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text.lower()).strip()
    return text


def tokens(text: str) -> set[str]:
    return {token for token in re.split(r"\W+", text.lower()) if len(token) >= 4}


def iter_notes(vault: Path) -> list[dict]:
    notes = []
    for path in sorted(vault.rglob("*.md")):
        rel_parts = path.relative_to(vault).parts
        if ".familiar" in rel_parts or any(part.startswith(".") for part in rel_parts):
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        text = normalized_text(body)
        notes.append(
            {
                "path": path,
                "rel": str(path.relative_to(vault)),
                "title": title_from_body(path, body),
                "body": body,
                "text": text,
                "tokens": tokens(text),
                "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return notes


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def detect_duplicates(notes: list[dict]) -> list[dict]:
    duplicates = []
    used = set()
    for left, right in combinations(notes, 2):
        if left["rel"] in used or right["rel"] in used:
            continue
        exact = left["hash"] == right["hash"]
        similar = jaccard(left["tokens"], right["tokens"]) >= 0.82
        same_title = left["title"].lower() == right["title"].lower()
        if exact or (same_title and similar):
            duplicates.append(
                {
                    "paths": [left["rel"], right["rel"]],
                    "reason": "exact text match" if exact else "same title with similar text",
                    "similarity": 1.0 if exact else round(jaccard(left["tokens"], right["tokens"]), 3),
                }
            )
            used.add(left["rel"])
            used.add(right["rel"])
    return duplicates


def contradiction_claims(note: dict) -> list[dict]:
    claims = []
    text = note["text"]
    patterns = [
        (r"\b([a-z][a-z0-9 -]{2,40}?)\s+enabled\b", "enabled"),
        (r"\b([a-z][a-z0-9 -]{2,40}?)\s+disabled\b", "disabled"),
        (r"\buse\s+([a-z][a-z0-9 -]{2,40}?)\b", "use"),
        (r"\bdo not use\s+([a-z][a-z0-9 -]{2,40}?)\b", "do-not-use"),
    ]
    for pattern, stance in patterns:
        for match in re.finditer(pattern, text):
            topic = re.sub(r"\s+", " ", match.group(1)).strip(" -")
            if topic:
                claims.append({"topic": topic, "stance": stance, "path": note["rel"]})
    return claims


def detect_contradictions(notes: list[dict]) -> list[dict]:
    by_topic = {}
    opposites = {("enabled", "disabled"), ("disabled", "enabled"), ("use", "do-not-use"), ("do-not-use", "use")}
    for note in notes:
        for claim in contradiction_claims(note):
            by_topic.setdefault(claim["topic"], []).append(claim)

    findings = []
    seen = set()
    for topic, claims in by_topic.items():
        for left, right in combinations(claims, 2):
            if left["path"] == right["path"]:
                continue
            if (left["stance"], right["stance"]) not in opposites:
                continue
            key = tuple(sorted([topic, left["path"], right["path"]]))
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "topic": topic,
                    "stances": [left["stance"], right["stance"]],
                    "paths": [left["path"], right["path"]],
                    "reason": "opposing claims detected",
                }
            )
    return findings


def process(args) -> dict:
    vault = Path(args.vault).expanduser().resolve()
    notes = iter_notes(vault)
    duplicates = detect_duplicates(notes)
    contradictions = detect_contradictions(notes)
    return {
        "ok": True,
        "notes_count": len(notes),
        "duplicates_count": len(duplicates),
        "contradictions_count": len(contradictions),
        "duplicates": duplicates,
        "contradictions": contradictions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a Familiar vault for duplicates and contradictions.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    args = parser.parse_args()
    try:
        print(json.dumps(process(args), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

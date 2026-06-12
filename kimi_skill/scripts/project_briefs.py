#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"
MAX_ITEMS = 10


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


def clean_line(line: str) -> str:
    line = re.sub(r"^[-*]\s+", "", line.strip())
    return line.strip()


def notable_lines(body: str) -> list[str]:
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
        item = clean_line(line)
        if len(item) > 12:
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


def project_keywords(name: str) -> list[str]:
    words = [word.lower() for word in re.split(r"\W+", name) if len(word) >= 4]
    if name.lower() == "familiar second brain":
        words.extend(["familiar", "kimi", "mcp", "dashboard", "memory"])
    return dedupe(words)


def note_matches_project(project_name: str, body: str) -> bool:
    text = body.lower()
    return any(keyword in text for keyword in project_keywords(project_name))


def collect_projects(vault: Path) -> list[Path]:
    projects_root = vault / "Projects"
    if not projects_root.exists():
        return []
    return sorted(path for path in projects_root.iterdir() if path.is_dir())


def iter_candidate_notes(vault: Path, project_dir: Path):
    roots = [
        project_dir,
        vault / "Daily" / "Kimi Sessions",
        vault / "_Inbox",
    ]
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.name == "Brief.md":
                continue
            if path in seen:
                continue
            seen.add(path)
            body = path.read_text(encoding="utf-8", errors="replace")
            if root == project_dir or note_matches_project(project_dir.name, body):
                yield {
                    "path": path,
                    "rel": str(path.relative_to(vault)),
                    "title": title_from_body(path, body),
                    "body": body,
                    "lines": notable_lines(body),
                }


def extract_matching(lines: list[str], patterns: tuple[str, ...]) -> list[str]:
    out = []
    for line in lines:
        lowered = line.lower()
        if any(pattern in lowered for pattern in patterns):
            out.append(line)
    return dedupe(out)


def bullet_list(items: list[str], empty: str) -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items[:MAX_ITEMS]]


def build_project_brief(vault: Path, project_dir: Path, sources: list[dict]) -> str:
    all_lines = []
    decisions = []
    open_loops = []
    for source in sources:
        all_lines.extend(source["lines"])
        decisions.extend(extract_matching(source["lines"], ("decision:", "decided", "chosen", "use ")))
        open_loops.extend(extract_matching(source["lines"], ("follow up", "follow-up", "next", "todo", "open loop")))

    sections = [
        "---",
        "source: familiar-second-brain",
        "kind: project-brief",
        f"project: {project_dir.name}",
        f"sources_count: {len(sources)}",
        "---",
        "",
        f"# {project_dir.name} Brief",
        "",
        "## Current Context",
        "",
        *bullet_list(dedupe(all_lines), "No project context found yet."),
        "",
        "## Decisions",
        "",
        *bullet_list(dedupe(decisions), "No explicit decisions detected."),
        "",
        "## Open Loops",
        "",
        *bullet_list(dedupe(open_loops), "No open loops detected."),
        "",
        "## Sources",
        "",
        *[f"- `{source['rel']}` - {source['title']}" for source in sources],
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
    written = []
    projects = []
    for project_dir in collect_projects(vault):
        sources = list(iter_candidate_notes(vault, project_dir))
        if not sources:
            continue
        target = project_dir / "Brief.md"
        body = build_project_brief(vault, project_dir, sources)
        changed = write_if_changed(target, body)
        projects.append({"project": project_dir.name, "path": str(target), "sources_count": len(sources), "written": changed})
        if changed:
            written.append(str(target))
    return {
        "ok": True,
        "projects_count": len(projects),
        "written_count": len(written),
        "projects": projects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Familiar project memory briefs.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
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

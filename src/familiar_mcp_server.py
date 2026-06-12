#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"
DEFAULT_SUMMARIZER = (
    Path.home()
    / "Library/Application Support/kimi-desktop/daimon-share/daimon/skills/familiar-second-brain/scripts/summarize_sessions.py"
)
SERVER_NAME = "familiar-second-brain"
SERVER_VERSION = "0.1.0"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "note") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#`\[\]()\n\r]+", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned[:90].strip() or fallback)


def normalize_folder(value: str) -> str:
    folder = (value or "_Inbox").strip().strip("/")
    if not folder:
        return "_Inbox"
    if folder.startswith(".") or ".." in Path(folder).parts:
        raise ValueError("folder must stay inside the Familiar vault")
    return folder


def ensure_vault(vault: Path) -> Path:
    resolved = Path(vault).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def safe_path(vault: Path, rel_path: str, *, require_markdown: bool = True) -> Path:
    if not rel_path or not str(rel_path).strip():
        raise ValueError("path is required")
    vault = ensure_vault(vault)
    candidate = (vault / str(rel_path).strip().lstrip("/")).resolve()
    if candidate != vault and vault not in candidate.parents:
        raise ValueError("path must stay inside the Familiar vault")
    if ".familiar" in candidate.relative_to(vault).parts:
        raise ValueError("hidden Familiar internals are not exposed through MCP")
    if require_markdown and candidate.suffix.lower() != ".md":
        raise ValueError("only Markdown notes are supported")
    return candidate


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


def clean_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def build_note(title: str, content: str, kind: str, tags: list[str], links: list[str]) -> str:
    sections = [
        "---",
        f"created: {iso_now()}",
        "source: familiar-mcp",
        f"kind: {slugify(kind, 'note')}",
    ]
    if tags:
        sections.append("tags:")
        sections.extend(f"- {tag}" for tag in tags)
    sections.extend(["---", "", f"# {title}", "", content.strip()])
    if links:
        sections.extend(["", "## Links"])
        sections.extend(f"- [[{link}]]" for link in links)
    sections.append("")
    return "\n".join(sections)


def title_from_note(path: Path, body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def iter_markdown_notes(vault: Path):
    vault = ensure_vault(vault)
    for path in vault.rglob("*.md"):
        try:
            rel_parts = path.relative_to(vault).parts
        except ValueError:
            continue
        if ".familiar" in rel_parts or any(part.startswith(".") for part in rel_parts):
            continue
        yield path


def excerpt_for(body: str, query_terms: list[str], size: int = 220) -> str:
    lower = body.lower()
    positions = [lower.find(term) for term in query_terms if lower.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - 80)
    excerpt = re.sub(r"\s+", " ", body[start : start + size]).strip()
    return excerpt


def score_note(body: str, query_terms: list[str]) -> int:
    lower = body.lower()
    return sum(lower.count(term) for term in query_terms)


def tool_save_memory(vault: Path, arguments: dict) -> dict:
    title = slugify(str(arguments.get("title") or "Familiar note"), "Familiar note")
    content = str(arguments.get("content") or "").strip()
    if not content:
        raise ValueError("content is required")
    folder = normalize_folder(str(arguments.get("folder") or "_Inbox"))
    target_dir = safe_path(vault, folder + "/placeholder.md").parent
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    target = unique_path(target_dir, f"{stamp} {title}.md")
    tags = clean_list(arguments.get("tags"))
    links = clean_list(arguments.get("links"))
    kind = str(arguments.get("kind") or "note")
    target.write_text(build_note(title, content, kind, tags, links), encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(ensure_vault(vault))), "title": title}


def tool_search_memory(vault: Path, arguments: dict) -> dict:
    query = str(arguments.get("query") or "").strip().lower()
    if not query:
        raise ValueError("query is required")
    limit = int(arguments.get("limit") or 10)
    limit = max(1, min(limit, 50))
    terms = [term for term in re.split(r"\W+", query) if term]
    matches = []
    for path in iter_markdown_notes(vault):
        body = path.read_text(encoding="utf-8", errors="replace")
        score = score_note(body, terms)
        if score <= 0:
            continue
        matches.append(
            {
                "path": str(path.relative_to(ensure_vault(vault))),
                "title": title_from_note(path, body),
                "score": score,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "excerpt": excerpt_for(body, terms),
            }
        )
    matches.sort(key=lambda item: (-item["score"], item["path"]))
    return {"query": query, "matches": matches[:limit]}


def tool_read_note(vault: Path, arguments: dict) -> dict:
    path = safe_path(vault, str(arguments.get("path") or ""))
    if not path.exists():
        raise FileNotFoundError(f"note does not exist: {path.relative_to(ensure_vault(vault))}")
    return {
        "path": str(path.relative_to(ensure_vault(vault))),
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def tool_write_note(vault: Path, arguments: dict) -> dict:
    path = safe_path(vault, str(arguments.get("path") or ""))
    overwrite = bool(arguments.get("overwrite", False))
    content = str(arguments.get("content") or "")
    if path.exists() and not overwrite:
        raise FileExistsError("note already exists; pass overwrite=true to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path.relative_to(ensure_vault(vault)))}


def tool_list_recent_notes(vault: Path, arguments: dict) -> dict:
    limit = int(arguments.get("limit") or 10)
    limit = max(1, min(limit, 50))
    notes = sorted(iter_markdown_notes(vault), key=lambda path: path.stat().st_mtime, reverse=True)
    return {
        "notes": [
            {
                "path": str(path.relative_to(ensure_vault(vault))),
                "title": title_from_note(path, path.read_text(encoding="utf-8", errors="replace")),
                "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
            for path in notes[:limit]
        ]
    }


def tool_vault_status(vault: Path, arguments: dict) -> dict:
    vault = ensure_vault(vault)
    notes = list(iter_markdown_notes(vault))
    return {
        "vault": str(vault),
        "note_count": len(notes),
        "inbox": str(vault / "_Inbox"),
        "kimi_sessions": str(vault / "Daily" / "Kimi Sessions"),
        "kimi_transcripts": str(vault / "Daily" / "Kimi Transcripts"),
    }


def tool_capture_kimi_sessions(vault: Path, arguments: dict) -> dict:
    script = Path(os.environ.get("FAMILIAR_KIMI_SUMMARIZER", DEFAULT_SUMMARIZER)).expanduser()
    if not script.exists():
        raise FileNotFoundError(f"Kimi summarizer script not found: {script}")
    command = [sys.executable, str(script), "--vault", str(ensure_vault(vault))]
    if bool(arguments.get("no_model", False)):
        command.append("--no-model")
    result = subprocess.run(command, text=True, capture_output=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "Kimi capture failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": True, "output": result.stdout.strip()}


TOOLS = {
    "save_memory": {
        "description": "Save a durable note into the Familiar vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "folder": {"type": "string", "default": "_Inbox"},
                "kind": {"type": "string", "default": "note"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "links": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "content"],
        },
        "handler": tool_save_memory,
    },
    "search_memory": {
        "description": "Search Markdown notes in the Familiar vault.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}},
            "required": ["query"],
        },
        "handler": tool_search_memory,
    },
    "read_note": {
        "description": "Read a Markdown note from the Familiar vault by relative path.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": tool_read_note,
    },
    "write_note": {
        "description": "Write a Markdown note to the Familiar vault by relative path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["path", "content"],
        },
        "handler": tool_write_note,
    },
    "list_recent_notes": {
        "description": "List recently modified Familiar Markdown notes.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
        "handler": tool_list_recent_notes,
    },
    "capture_kimi_sessions": {
        "description": "Run the Kimi Work session capture job into Familiar.",
        "inputSchema": {
            "type": "object",
            "properties": {"no_model": {"type": "boolean", "default": False}},
        },
        "handler": tool_capture_kimi_sessions,
    },
    "vault_status": {
        "description": "Show the Familiar vault path and note counts.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_vault_status,
    },
}


def tool_specs() -> list[dict]:
    return [
        {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
        for name, spec in TOOLS.items()
    ]


def make_response(message_id, result=None, error=None) -> dict:
    response = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def tool_result(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}


def tool_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def handle_message(vault: Path, message: dict):
    message_id = message.get("id")
    method = message.get("method")
    if message_id is None:
        return None
    try:
        if method == "initialize":
            return make_response(
                message_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )
        if method == "tools/list":
            return make_response(message_id, {"tools": tool_specs()})
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            if name not in TOOLS:
                return make_response(message_id, tool_error(f"unknown tool: {name}"))
            arguments = params.get("arguments") or {}
            payload = TOOLS[name]["handler"](vault, arguments)
            return make_response(message_id, tool_result(payload))
        return make_response(message_id, error={"code": -32601, "message": f"method not found: {method}"})
    except Exception as exc:
        return make_response(message_id, tool_error(f"{type(exc).__name__}: {exc}"))


def read_frame(stream):
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("ascii", errors="replace").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = stream.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def write_frame(stream, message: dict):
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stream.flush()


def serve(vault: Path):
    vault = ensure_vault(vault)
    while True:
        message = read_frame(sys.stdin.buffer)
        if message is None:
            break
        response = handle_message(vault, message)
        if response is not None:
            write_frame(sys.stdout.buffer, response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Familiar second-brain MCP server.")
    parser.add_argument("--vault", default=os.environ.get("FAMILIAR_VAULT", str(DEFAULT_VAULT)))
    args = parser.parse_args()
    serve(Path(args.vault))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DAIMON = Path.home() / "Library/Application Support/kimi-desktop/daimon-share/daimon"
DEFAULT_CONFIG = DEFAULT_DAIMON / "config.json"
DEFAULT_HOSTED = DEFAULT_DAIMON / "agents/main/sessions/hosted-logical/sessions.v2.json"
DEFAULT_STATE_NAME = ".familiar/kimi-session-summarizer-state.json"
MAX_TRANSCRIPT_CHARS = 24000
MAINTENANCE_PROMPT_PREFIX = "Run the Familiar second brain session summarizer now."
MAINTENANCE_COMMAND_MARKER = "summarize_sessions.py"


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def slugify(value: str, fallback: str = "session") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#`\\[\\]()\\n\\r]+", " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned[:90].strip() or fallback)


def parse_date(value: str) -> str:
    if not value:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if isinstance(item, dict):
            if isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item.get("content"), str):
                parts.append(item["content"])
    return "\n".join(parts).strip()


def read_messages(wire_path: Path) -> list[dict]:
    messages = []
    if not wire_path.exists():
        return messages
    for line in wire_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "context.append_message":
            message = event.get("message") or {}
            text = text_from_content(message.get("content"))
            if text:
                messages.append(
                    {
                        "role": message.get("role", "unknown"),
                        "origin": (message.get("origin") or {}).get("kind", ""),
                        "text": text,
                    }
                )
        elif event.get("type") == "turn.prompt":
            text = text_from_content(event.get("input"))
            if text:
                messages.append(
                    {
                        "role": "user",
                        "origin": (event.get("origin") or {}).get("kind", ""),
                        "text": text,
                    }
                )
    return dedupe_messages(messages)


def dedupe_messages(messages: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for message in messages:
        key = (message["role"], message["origin"], message["text"][:500])
        if key in seen:
            continue
        seen.add(key)
        out.append(message)
    return out


def load_conversations(hosted_path: Path) -> list[dict]:
    data = load_json(hosted_path, {})
    conversations = data.get("conversations") if isinstance(data, dict) else []
    if not isinstance(conversations, list):
        return []
    return [
        conversation
        for conversation in conversations
        if isinstance(conversation, dict)
        and "ctitle-" not in str(conversation.get("kernelSessionDir", ""))
        and conversation.get("kernelSessionDir")
    ]


def fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        try:
            st = path.stat()
        except FileNotFoundError:
            continue
        h.update(str(path).encode())
        h.update(str(st.st_mtime_ns).encode())
        h.update(str(st.st_size).encode())
    return h.hexdigest()


def build_transcript(title: str, state: dict, messages: list[dict]) -> str:
    parts = [
        f"Title: {title}",
        f"Created: {state.get('createdAt', '')}",
        f"Updated: {state.get('updatedAt', '')}",
    ]
    last_prompt = state.get("lastPrompt")
    if isinstance(last_prompt, str) and last_prompt.strip():
        parts.extend(["", "Last prompt:", last_prompt.strip()])
    if messages:
        parts.append("")
        parts.append("Messages:")
    for message in messages:
        text = message["text"].strip()
        if not text:
            continue
        label = message["role"]
        if message.get("origin"):
            label += f"/{message['origin']}"
        parts.append(f"\n[{label}]\n{text}")
    transcript = "\n".join(parts).strip()
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        return transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated for summarization.]"
    return transcript


def is_maintenance_session(state: dict, messages: list[dict]) -> bool:
    candidates = []
    last_prompt = state.get("lastPrompt")
    if isinstance(last_prompt, str):
        candidates.append(last_prompt)
    candidates.extend(message.get("text", "") for message in messages)
    for text in candidates:
        stripped = text.lstrip()
        if stripped.startswith(MAINTENANCE_PROMPT_PREFIX) and MAINTENANCE_COMMAND_MARKER in stripped:
            return True
    return False


def fallback_summary(title: str, state: dict, messages: list[dict]) -> str:
    user_messages = [m["text"] for m in messages if m["role"] == "user" and m["origin"] in ("user", "")]
    assistant_messages = [m["text"] for m in messages if m["role"] == "assistant"]
    prompt = (user_messages[-1] if user_messages else state.get("lastPrompt") or "").strip()
    assistant = (assistant_messages[-1] if assistant_messages else "").strip()
    lines = [
        "## Summary",
        "",
        f"- Session: {title}",
    ]
    if prompt:
        lines.append(f"- User intent: {prompt[:900]}")
    if assistant:
        lines.append(f"- Latest response: {assistant[:900]}")
    lines.extend(
        [
            "",
            "## Follow-ups",
            "",
            "- Review this summary and expand it if the session contains durable decisions.",
        ]
    )
    return "\n".join(lines)


def kimi_summary(config_path: Path, title: str, transcript: str) -> str:
    config = load_json(config_path, {})
    model_root = config.get("model", {})
    current = model_root.get("current")
    model_info = (model_root.get("models") or {}).get(current, {})
    provider_info = (model_root.get("providers") or {}).get(model_info.get("provider"), {})
    credential_name = provider_info.get("credential")
    credential = (config.get("credentials") or {}).get(credential_name, {})
    api_key = credential.get("apiKey")
    base_url = (provider_info.get("baseUrl") or credential.get("baseUrl") or "").rstrip("/")
    model = model_info.get("model")
    if not api_key or not base_url or not model:
        raise RuntimeError("Missing Kimi model credentials in local config")

    prompt = (
        "Summarize this Kimi Work session into durable second-brain notes. "
        "Focus on user goals, decisions, useful context, outputs created, follow-ups, and reusable facts. "
        "Do not include secrets. Return concise Markdown with headings: Summary, Decisions, Outputs, Follow-ups, Links.\n\n"
        f"Session title: {title}\n\n{transcript}"
    )
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "You write concise Markdown second-brain notes."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
    ).encode()
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Desktop Kimi Work",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text.strip():
        raise RuntimeError("Kimi returned an empty summary")
    return text.strip()


def note_path(vault: Path, created_at: str, title: str, session_id: str) -> Path:
    day = parse_date(created_at)
    safe = slugify(title)
    suffix = session_id[-8:] if session_id else hashlib.sha1(title.encode()).hexdigest()[:8]
    return vault / "Daily" / "Kimi Sessions" / f"{day} {safe} {suffix}.md"


def transcript_note_path(vault: Path, created_at: str, title: str, session_id: str) -> Path:
    day = parse_date(created_at)
    safe = slugify(title)
    suffix = session_id[-8:] if session_id else hashlib.sha1(title.encode()).hexdigest()[:8]
    return vault / "Daily" / "Kimi Transcripts" / f"{day} {safe} {suffix}.md"


def write_note(path: Path, conversation: dict, state: dict, summary: str):
    title = conversation.get("title") or state.get("title") or "Kimi Work Session"
    created = state.get("createdAt") or conversation.get("createdAt") or iso_now()
    updated = state.get("updatedAt") or conversation.get("updatedAt") or iso_now()
    session_dir = conversation.get("kernelSessionDir", "")
    body = "\n".join(
        [
            "---",
            f"created: {created}",
            f"updated: {updated}",
            "source: kimi-work",
            "kind: session-summary",
            f"session_id: {Path(session_dir).name}",
            f"conversation_id: {conversation.get('conversationId', '')}",
            "---",
            "",
            f"# {title}",
            "",
            summary.strip(),
            "",
            "## Links",
            "",
            "- [[Kimi Work]]",
            "- [[Familiar]]",
            "- [[Second Brain]]",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def write_transcript_note(path: Path, conversation: dict, state: dict, transcript: str):
    title = conversation.get("title") or state.get("title") or "Kimi Work Session"
    created = state.get("createdAt") or conversation.get("createdAt") or iso_now()
    updated = state.get("updatedAt") or conversation.get("updatedAt") or iso_now()
    session_dir = conversation.get("kernelSessionDir", "")
    body = "\n".join(
        [
            "---",
            f"created: {created}",
            f"updated: {updated}",
            "source: kimi-work",
            "kind: session-transcript",
            f"session_id: {Path(session_dir).name}",
            f"conversation_id: {conversation.get('conversationId', '')}",
            "---",
            "",
            f"# {title}",
            "",
            transcript.strip(),
            "",
            "## Links",
            "",
            "- [[Kimi Work]]",
            "- [[Familiar]]",
            "- [[Second Brain]]",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def entry_path_exists(entry: dict, key: str) -> bool:
    value = entry.get(key)
    return isinstance(value, str) and Path(value).exists()


def process(args) -> dict:
    vault = Path(args.vault).expanduser().resolve()
    hosted_path = Path(args.hosted_sessions).expanduser()
    config_path = Path(args.config).expanduser()
    state_path = Path(args.state).expanduser() if args.state else vault / DEFAULT_STATE_NAME
    state_store = load_json(state_path, {"sessions": {}})
    state_store.setdefault("sessions", {})

    written = 0
    transcripts_written = 0
    skipped = 0
    ignored = 0
    errors = []
    for conversation in load_conversations(hosted_path):
        session_dir = Path(conversation["kernelSessionDir"])
        session_id = session_dir.name
        wire_path = Path(conversation.get("kernelRecordsPath") or session_dir / "agents/main/wire.jsonl")
        state_json_path = session_dir / "state.json"
        session_state = load_json(state_json_path, {})
        messages = read_messages(wire_path)
        if is_maintenance_session(session_state, messages):
            state_store["sessions"].pop(session_id, None)
            ignored += 1
            continue

        fp = fingerprint([wire_path, state_json_path])
        previous = state_store["sessions"].get(session_id, {})
        title = conversation.get("title") or session_state.get("title") or session_id
        created = session_state.get("createdAt") or conversation.get("createdAt") or ""
        target = note_path(vault, created, title, session_id)
        transcript_target = transcript_note_path(vault, created, title, session_id)
        summary_current = (
            previous.get("fingerprint") == fp
            and entry_path_exists(previous, "note")
            and previous.get("note") == str(target)
        )
        transcript_current = (
            previous.get("fingerprint") == fp
            and entry_path_exists(previous, "transcript")
            and previous.get("transcript") == str(transcript_target)
        )
        if summary_current and transcript_current:
            skipped += 1
            continue

        transcript = build_transcript(title, session_state, messages)
        if not summary_current:
            try:
                if args.no_model:
                    summary = fallback_summary(title, session_state, messages)
                else:
                    summary = kimi_summary(config_path, title, transcript)
            except Exception as exc:
                summary = fallback_summary(title, session_state, messages)
                errors.append({"session_id": session_id, "error": str(exc)})

            write_note(target, conversation, session_state, summary)
            written += 1
        if not transcript_current:
            write_transcript_note(transcript_target, conversation, session_state, transcript)
            transcripts_written += 1

        state_store["sessions"][session_id] = {
            "fingerprint": fp,
            "note": str(target),
            "transcript": str(transcript_target),
            "updatedAt": session_state.get("updatedAt") or conversation.get("updatedAt"),
            "summarizedAt": iso_now(),
        }

    write_json(state_path, state_store)
    return {
        "ok": True,
        "written": written,
        "transcripts_written": transcripts_written,
        "skipped": skipped,
        "ignored": ignored,
        "errors": errors,
        "state": str(state_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Kimi Work sessions into the Familiar second brain.")
    parser.add_argument("--vault", default=str(Path.home() / "Documents/kimi/workspace/familiar-vault"))
    parser.add_argument("--hosted-sessions", default=str(DEFAULT_HOSTED))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--state", default="")
    parser.add_argument("--no-model", action="store_true", help="Use deterministic extractive summaries without calling Kimi")
    args = parser.parse_args()
    try:
        print(json.dumps(process(args), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

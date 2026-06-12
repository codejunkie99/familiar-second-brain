#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = Path.home() / "Documents/kimi/workspace/familiar-vault"
DEFAULT_DAIMON = Path.home() / "Library/Application Support/kimi-desktop/daimon-share/daimon"
CLAUDE_CONFIGS = [
    Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
    Path.home() / "Library/Application Support/Claude-3p/claude_desktop_config.json",
    Path.home() / ".claude/mcp_servers.json",
]
CURSOR_CONFIG = Path.home() / ".cursor/mcp.json"
CODEX_CONFIG = Path.home() / ".codex/config.toml"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path: Path, stamp: str, dry_run: bool):
    if not path.exists():
        return None
    target = path.with_name(path.name + f".bak.{stamp}")
    if not dry_run:
        shutil.copy2(path, target)
    return target


def copy_file(src: Path, dst: Path, dry_run: bool):
    if dry_run:
        print(f"copy {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if dst.suffix == ".py":
        dst.chmod(dst.stat().st_mode | 0o111)


def copy_tree(src: Path, dst: Path, dry_run: bool):
    if dry_run:
        print(f"copy tree {src} -> {dst}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for path in dst.rglob("*.py"):
        path.chmod(path.stat().st_mode | 0o111)


def load_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON config must be an object: {path}")
    return data


def write_json(path: Path, data: dict, dry_run: bool):
    if dry_run:
        print(f"write JSON {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if path.name == "mcp.json":
        os.chmod(path, 0o600)


def ensure_nested_object(data: dict, keys: tuple[str, ...]) -> dict:
    cursor = data
    for key in keys:
        value = cursor.get(key)
        if not isinstance(value, dict):
            value = {}
            cursor[key] = value
        cursor = value
    return cursor


def update_json_mcp(path: Path, keys: tuple[str, ...], server: dict, stamp: str, dry_run: bool):
    backup_path = backup(path, stamp, dry_run)
    data = load_json(path)
    servers = ensure_nested_object(data, keys)
    servers["familiar"] = dict(server)
    write_json(path, data, dry_run)
    print(f"updated {path}" + (f" (backup {backup_path})" if backup_path else ""))


def render_codex_block(server_path: Path) -> str:
    return "\n".join(
        [
            "[mcp_servers.familiar]",
            f'args = ["{server_path}"]',
            'command = "/usr/bin/python3"',
            "startup_timeout_sec = 30",
            "",
        ]
    )


def update_codex_config(path: Path, server_path: Path, stamp: str, dry_run: bool):
    backup_path = backup(path, stamp, dry_run)
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = re.sub(
        r"\n?\[mcp_servers\.familiar\]\n(?:[^\n[]|\n(?!\[))*",
        "\n",
        original,
        flags=re.MULTILINE,
    ).rstrip()
    updated = cleaned + "\n\n" + render_codex_block(server_path)
    if dry_run:
        print(f"write TOML {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
    print(f"updated {path}" + (f" (backup {backup_path})" if backup_path else ""))


def sync_kimi_runtime_mcp(daimon: Path, server: dict, stamp: str, dry_run: bool):
    update_json_mcp(daimon / "config.json", ("mcp", "servers"), server, stamp, dry_run)
    update_json_mcp(daimon / "runtime/kimi-code/home/mcp.json", ("mcpServers",), server, stamp, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Familiar Second Brain locally.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--kimi-daimon", default=str(DEFAULT_DAIMON))
    parser.add_argument("--python", default="/usr/bin/python3")
    parser.add_argument("--skip-configs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    daimon = Path(args.kimi_daimon).expanduser().resolve()
    mcp_server_path = vault / ".familiar/mcp/familiar_mcp_server.py"
    kimi_skill_path = daimon / "skills/familiar-second-brain"
    server = {"command": args.python, "args": [str(mcp_server_path)]}
    stamp = timestamp()

    copy_file(ROOT / "src/familiar_mcp_server.py", mcp_server_path, args.dry_run)
    copy_tree(ROOT / "kimi_skill", kimi_skill_path, args.dry_run)

    if not args.skip_configs:
        sync_kimi_runtime_mcp(daimon, server, stamp, args.dry_run)
        update_codex_config(CODEX_CONFIG, mcp_server_path, stamp, args.dry_run)
        for config in CLAUDE_CONFIGS:
            update_json_mcp(config, ("mcpServers",), server, stamp, args.dry_run)
        update_json_mcp(CURSOR_CONFIG, ("mcpServers",), server, stamp, args.dry_run)

    print("install complete" if not args.dry_run else "dry run complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

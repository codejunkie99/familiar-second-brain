#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = ROOT / "src" / "familiar_mcp_server.py"


def frame(message: dict) -> bytes:
    body = json.dumps(message).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def parse_frames(data: bytes) -> list[dict]:
    responses = []
    offset = 0
    while offset < len(data):
        header_end = data.index(b"\r\n\r\n", offset)
        header = data[offset:header_end].decode("ascii")
        length = int(header.split("Content-Length: ", 1)[1].splitlines()[0])
        start = header_end + 4
        responses.append(json.loads(data[start : start + length].decode("utf-8")))
        offset = start + length
    return responses


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a Familiar MCP server over stdio.")
    parser.add_argument("--vault", default=str(Path.home() / "Documents/kimi/workspace/familiar-vault"))
    parser.add_argument("--server", default=str(DEFAULT_SERVER))
    args = parser.parse_args()

    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "familiar-smoke", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "vault_status", "arguments": {}}},
    ]
    result = subprocess.run(
        [sys.executable, str(Path(args.server).expanduser()), "--vault", str(Path(args.vault).expanduser())],
        input=b"".join(frame(message) for message in messages),
        capture_output=True,
        timeout=5,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        return result.returncode

    responses = parse_frames(result.stdout)
    tool_names = [tool["name"] for tool in responses[1]["result"]["tools"]]
    status = json.loads(responses[2]["result"]["content"][0]["text"])
    print(json.dumps({"tools": tool_names, "vault_status": status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

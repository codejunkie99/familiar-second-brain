import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "src" / "familiar_mcp_server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("familiar_mcp_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FamiliarMcpServerTests(unittest.TestCase):
    def test_save_memory_writes_markdown_note_inside_requested_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            server = load_server()
            result = server.tool_save_memory(
                vault,
                {
                    "title": "Kimi Context",
                    "content": "The durable context belongs in Familiar.",
                    "folder": "_Inbox",
                    "kind": "kimi-note",
                    "tags": ["kimi", "second-brain"],
                    "links": ["Kimi Work"],
                },
            )

            note = vault / result["path"]
            self.assertTrue(note.exists())
            body = note.read_text(encoding="utf-8")
            self.assertIn("source: familiar-mcp", body)
            self.assertIn("kind: kimi-note", body)
            self.assertIn("tags:", body)
            self.assertIn("- kimi", body)
            self.assertIn("[[Kimi Work]]", body)
            self.assertIn("The durable context belongs in Familiar.", body)

    def test_search_memory_finds_markdown_note_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            server = load_server()
            server.tool_save_memory(
                vault,
                {
                    "title": "Retrieval Contract",
                    "content": "Kimi should answer from the familiar vault.",
                    "folder": "Research",
                },
            )

            result = server.tool_search_memory(vault, {"query": "answer familiar vault", "limit": 5})

            self.assertEqual(len(result["matches"]), 1)
            self.assertEqual(result["matches"][0]["title"], "Retrieval Contract")
            self.assertIn("answer from the familiar vault", result["matches"][0]["excerpt"])

    def test_search_memory_prioritizes_metadata_and_returns_context_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            research = vault / "Research"
            research.mkdir(parents=True)
            contract = research / "retrieval-contract.md"
            noisy = research / "noisy-body.md"
            contract.write_text(
                "\n".join(
                    [
                        "---",
                        "source: test",
                        "kind: memory",
                        "tags:",
                        "- second-brain",
                        "- retrieval",
                        "---",
                        "",
                        "# Familiar Retrieval Contract",
                        "",
                        "## What did I say",
                        "",
                        "Kimi should answer from the familiar vault with source paths.",
                        "",
                        "## Links",
                        "",
                        "- [[Kimi Work]]",
                    ]
                ),
                encoding="utf-8",
            )
            noisy.write_text(
                "\n".join(
                    [
                        "# Random Body Matches",
                        "",
                        "retrieval contract second brain retrieval contract second brain retrieval contract second brain",
                    ]
                ),
                encoding="utf-8",
            )
            server = load_server()

            result = server.tool_search_memory(
                vault,
                {"query": "retrieval contract second brain", "limit": 5, "context_chars": 120},
            )

            self.assertGreaterEqual(len(result["matches"]), 2)
            first = result["matches"][0]
            self.assertEqual(first["path"], "Research/retrieval-contract.md")
            self.assertIn("title", first["matched_fields"])
            self.assertIn("tags", first["matched_fields"])
            self.assertIn("contexts", first)
            self.assertGreaterEqual(len(first["contexts"]), 1)
            self.assertIn("Kimi should answer from the familiar vault", first["contexts"][0]["text"])
            self.assertEqual(first["contexts"][0]["heading"], "What did I say")

    def test_rejects_path_traversal_for_note_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            outside = Path(tmp) / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            server = load_server()

            with self.assertRaises(ValueError):
                server.tool_read_note(vault, {"path": "../outside.md"})

    def test_stdio_mcp_lists_and_calls_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            initialize = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
            tools_list = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            save = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "save_memory",
                    "arguments": {
                        "title": "MCP Smoke",
                        "content": "Written through stdio.",
                        "folder": "_Inbox",
                    },
                },
            }
            payload = b"".join(frame(message) for message in (initialize, tools_list, save))
            result = subprocess.run(
                [sys.executable, str(SERVER), "--vault", str(vault)],
                input=payload,
                capture_output=True,
                timeout=5,
            )

            self.assertEqual(result.returncode, 0, result.stderr.decode())
            responses = parse_frames(result.stdout)
            self.assertEqual([item["id"] for item in responses], [1, 2, 3])
            tool_names = [tool["name"] for tool in responses[1]["result"]["tools"]]
            self.assertIn("save_memory", tool_names)
            saved = json.loads(responses[2]["result"]["content"][0]["text"])
            self.assertTrue((vault / saved["path"]).exists())


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
        body = data[start : start + length]
        responses.append(json.loads(body.decode("utf-8")))
        offset = start + length
    return responses


if __name__ == "__main__":
    unittest.main()

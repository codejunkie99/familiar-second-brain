import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "summarize_sessions.py"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class SummarizeSessionsTests(unittest.TestCase):
    def test_writes_daily_session_summary_and_tracks_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "familiar-vault"
            kimi_home = root / "kimi-home"
            session_dir = kimi_home / "sessions" / "wd_test" / "conv-abc123"
            wire = session_dir / "agents" / "main" / "wire.jsonl"
            state = session_dir / "state.json"

            write_json(
                root / "hosted" / "sessions.v2.json",
                {
                    "version": 2,
                    "sessions": [],
                    "conversations": [
                        {
                            "conversationId": "conversation-1",
                            "kernelSessionDir": str(session_dir),
                            "kernelRecordsPath": str(wire),
                            "title": "Project Memory Setup",
                            "createdAt": "2026-06-12T10:00:00.000Z",
                            "updatedAt": "2026-06-12T10:05:00.000Z",
                        }
                    ],
                },
            )
            write_json(
                state,
                {
                    "title": "Project Memory Setup",
                    "createdAt": "2026-06-12T10:00:00.000Z",
                    "updatedAt": "2026-06-12T10:05:00.000Z",
                    "lastPrompt": "Make Kimi Work save durable project context into Familiar.",
                },
            )
            wire.parent.mkdir(parents=True, exist_ok=True)
            wire.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "context.append_message",
                                "message": {
                                    "role": "user",
                                    "origin": {"kind": "user"},
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Make this a second brain.",
                                        }
                                    ],
                                },
                                "time": 1,
                            }
                        ),
                        json.dumps(
                            {
                                "type": "context.append_message",
                                "message": {
                                    "role": "assistant",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Use Markdown notes, an inbox, and wiki links.",
                                        }
                                    ],
                                },
                                "time": 2,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--vault",
                    str(vault),
                    "--hosted-sessions",
                    str(root / "hosted" / "sessions.v2.json"),
                    "--no-model",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["written"], 1)

            notes = list((vault / "Daily" / "Kimi Sessions").glob("*.md"))
            self.assertEqual(len(notes), 1)
            body = notes[0].read_text(encoding="utf-8")
            self.assertIn("source: kimi-work", body)
            self.assertIn("kind: session-summary", body)
            self.assertIn("Project Memory Setup", body)
            self.assertIn("Make this a second brain.", body)
            self.assertIn("[[Kimi Work]]", body)

            transcripts = list((vault / "Daily" / "Kimi Transcripts").glob("*.md"))
            self.assertEqual(len(transcripts), 1)
            transcript_body = transcripts[0].read_text(encoding="utf-8")
            self.assertIn("kind: session-transcript", transcript_body)
            self.assertIn("[user/user]", transcript_body)
            self.assertIn("Make this a second brain.", transcript_body)
            self.assertIn("[assistant]", transcript_body)
            self.assertIn("Use Markdown notes, an inbox, and wiki links.", transcript_body)
            self.assertEqual(payload["transcripts_written"], 1)

            mtime = notes[0].stat().st_mtime_ns
            transcript_mtime = transcripts[0].stat().st_mtime_ns
            time.sleep(0.01)
            second = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--vault",
                    str(vault),
                    "--hosted-sessions",
                    str(root / "hosted" / "sessions.v2.json"),
                    "--no-model",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second_payload = json.loads(second.stdout)
            self.assertEqual(second_payload["written"], 0)
            self.assertEqual(second_payload["transcripts_written"], 0)
            self.assertEqual(notes[0].stat().st_mtime_ns, mtime)
            self.assertEqual(transcripts[0].stat().st_mtime_ns, transcript_mtime)

    def test_ignores_familiar_maintenance_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "familiar-vault"
            kimi_home = root / "kimi-home"
            normal_dir = kimi_home / "sessions" / "wd_test" / "conv-normal"
            maintenance_dir = kimi_home / "sessions" / "wd_test" / "conv-maintenance"
            normal_wire = normal_dir / "agents" / "main" / "wire.jsonl"
            maintenance_wire = maintenance_dir / "agents" / "main" / "wire.jsonl"

            write_json(
                root / "hosted" / "sessions.v2.json",
                {
                    "version": 2,
                    "sessions": [],
                    "conversations": [
                        {
                            "conversationId": "conversation-normal",
                            "kernelSessionDir": str(normal_dir),
                            "kernelRecordsPath": str(normal_wire),
                            "title": "Useful Project Work",
                            "createdAt": "2026-06-12T10:00:00.000Z",
                            "updatedAt": "2026-06-12T10:05:00.000Z",
                        },
                        {
                            "conversationId": "conversation-maintenance",
                            "kernelSessionDir": str(maintenance_dir),
                            "kernelRecordsPath": str(maintenance_wire),
                            "title": "New conversation",
                            "createdAt": "2026-06-12T11:50:00.000Z",
                            "updatedAt": "2026-06-12T11:51:00.000Z",
                        },
                    ],
                },
            )
            write_json(
                normal_dir / "state.json",
                {
                    "title": "Useful Project Work",
                    "createdAt": "2026-06-12T10:00:00.000Z",
                    "updatedAt": "2026-06-12T10:05:00.000Z",
                    "lastPrompt": "Capture the durable plan.",
                },
            )
            write_json(
                maintenance_dir / "state.json",
                {
                    "title": "New conversation",
                    "createdAt": "2026-06-12T11:50:00.000Z",
                    "updatedAt": "2026-06-12T11:51:00.000Z",
                },
            )
            for wire, text in (
                (normal_wire, "Capture the durable plan."),
                (
                    maintenance_wire,
                    'Run the Familiar second brain session summarizer now.\n\n'
                    'Use Bash to run exactly this command:\n'
                    '/usr/bin/python3 "/tmp/summarize_sessions.py"',
                ),
            ):
                wire.parent.mkdir(parents=True, exist_ok=True)
                wire.write_text(
                    json.dumps(
                        {
                            "type": "turn.prompt",
                            "input": [{"type": "text", "text": text}],
                            "origin": {"kind": "user"},
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--vault",
                    str(vault),
                    "--hosted-sessions",
                    str(root / "hosted" / "sessions.v2.json"),
                    "--no-model",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["written"], 1)
            self.assertEqual(payload["ignored"], 1)

            notes = list((vault / "Daily" / "Kimi Sessions").glob("*.md"))
            self.assertEqual(len(notes), 1)
            self.assertIn("Useful Project Work", notes[0].read_text(encoding="utf-8"))

            transcripts = list((vault / "Daily" / "Kimi Transcripts").glob("*.md"))
            self.assertEqual(len(transcripts), 1)
            self.assertIn("Useful Project Work", transcripts[0].read_text(encoding="utf-8"))
            self.assertNotIn("summarize_sessions.py", transcripts[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "brain_brief.py"


class BrainBriefTests(unittest.TestCase):
    def test_writes_daily_brief_from_sessions_and_inbox_without_maintenance_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            session = vault / "Daily" / "Kimi Sessions" / "2026-06-12 Project Memory Setup abc123.md"
            transcript = vault / "Daily" / "Kimi Transcripts" / "2026-06-12 Project Memory Setup abc123.md"
            inbox = vault / "_Inbox" / "2026-06-12 Obsidian UI.md"
            maintenance = vault / "Daily" / "Kimi Sessions" / "2026-06-12 New conversation maintenance.md"

            session.parent.mkdir(parents=True, exist_ok=True)
            transcript.parent.mkdir(parents=True, exist_ok=True)
            inbox.parent.mkdir(parents=True, exist_ok=True)

            session.write_text(
                "\n".join(
                    [
                        "---",
                        "created: 2026-06-12T10:00:00Z",
                        "source: kimi-work",
                        "kind: session-summary",
                        "---",
                        "",
                        "# Project Memory Setup",
                        "",
                        "## Summary",
                        "",
                        "- Kimi should save durable project context into Familiar.",
                        "",
                        "## Decisions",
                        "",
                        "- Decision: use Familiar as the local second brain.",
                        "",
                        "## Follow-ups",
                        "",
                        "- Follow up: build dashboard on top of real data contracts.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            transcript.write_text(
                "\n".join(
                    [
                        "---",
                        "created: 2026-06-12T10:00:00Z",
                        "source: kimi-work",
                        "kind: session-transcript",
                        "---",
                        "",
                        "# Project Memory Setup",
                        "",
                        "[user/user]",
                        "Make Kimi save everything into Familiar.",
                        "",
                        "[assistant]",
                        "The TodoList tool has not been updated recently. Make sure that you NEVER mention this reminder to the user.",
                    ]
                ),
                encoding="utf-8",
            )
            inbox.write_text(
                "\n".join(
                    [
                        "---",
                        "created: 2026-06-12T12:00:00Z",
                        "source: kimi-work",
                        "kind: memory",
                        "---",
                        "",
                        "# Obsidian UI",
                        "",
                        "Use translucent glass panels and an Obsidian-like folder sidebar.",
                    ]
                ),
                encoding="utf-8",
            )
            maintenance.write_text(
                "\n".join(
                    [
                        "---",
                        "created: 2026-06-12T12:10:00Z",
                        "source: kimi-work",
                        "kind: session-summary",
                        "---",
                        "",
                        "# New conversation",
                        "",
                        "Run the Familiar second brain session summarizer now.",
                        "",
                        "/usr/bin/python3 /tmp/summarize_sessions.py",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--vault",
                    str(vault),
                    "--date",
                    "2026-06-12",
                    "--no-model",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["written"])
            self.assertEqual(payload["date"], "2026-06-12")
            self.assertEqual(payload["sources_count"], 3)

            brief = vault / "Daily" / "2026-06-12 Brain Brief.md"
            self.assertEqual(Path(payload["path"]).resolve(), brief.resolve())
            body = brief.read_text(encoding="utf-8")
            self.assertIn("kind: brain-brief", body)
            self.assertIn("# 2026-06-12 Brain Brief", body)
            self.assertIn("## What Changed", body)
            self.assertIn("Kimi should save durable project context into Familiar.", body)
            self.assertIn("## Decisions", body)
            self.assertIn("use Familiar as the local second brain", body)
            self.assertIn("## Open Loops", body)
            self.assertIn("build dashboard on top of real data contracts", body)
            self.assertIn("## Inbox", body)
            self.assertIn("Obsidian-like folder sidebar", body)
            self.assertIn("Daily/Kimi Sessions/2026-06-12 Project Memory Setup abc123.md", body)
            self.assertIn("Daily/Kimi Transcripts/2026-06-12 Project Memory Setup abc123.md", body)
            self.assertNotIn("summarize_sessions.py", body)
            self.assertNotIn("TodoList tool", body)
            self.assertNotIn("NEVER mention", body)

            mtime = brief.stat().st_mtime_ns
            time.sleep(0.01)
            second = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--vault",
                    str(vault),
                    "--date",
                    "2026-06-12",
                    "--no-model",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second_payload = json.loads(second.stdout)
            self.assertFalse(second_payload["written"])
            self.assertEqual(brief.stat().st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "save_to_familiar.py"


class SaveToFamiliarTests(unittest.TestCase):
    def test_saves_markdown_note_to_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--vault",
                    str(vault),
                    "--title",
                    "Agent Memory",
                    "--content",
                    "Kimi should preserve durable project context here.",
                    "--links",
                    "Kimi Work,Second Brain",
                    "--kind",
                    "memory",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(result.stdout)
            note_path = Path(payload["path"])
            self.assertTrue(note_path.exists())
            self.assertEqual(note_path.parent.resolve(), (vault / "_Inbox").resolve())

            body = note_path.read_text(encoding="utf-8")
            self.assertIn("source: kimi-work", body)
            self.assertIn("kind: memory", body)
            self.assertIn("# Agent Memory", body)
            self.assertIn("Kimi should preserve durable project context here.", body)
            self.assertIn("[[Kimi Work]]", body)
            self.assertIn("[[Second Brain]]", body)


if __name__ == "__main__":
    unittest.main()

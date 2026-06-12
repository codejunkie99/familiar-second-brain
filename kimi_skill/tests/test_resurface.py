import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "resurface.py"


class ResurfaceTests(unittest.TestCase):
    def test_resurfaces_old_relevant_notes_once_per_state_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            research = vault / "Research"
            daily = vault / "Daily" / "Kimi Sessions"
            research.mkdir(parents=True)
            daily.mkdir(parents=True)
            old = research / "Familiar dashboard decisions.md"
            unrelated = research / "Nvidia valuation.md"
            recent = daily / "2026-06-12 Familiar dashboard work.md"
            old.write_text(
                "# Familiar dashboard decisions\n\nDecision: dashboard should read project briefs and daily briefs.",
                encoding="utf-8",
            )
            unrelated.write_text("# Nvidia valuation\n\nEquity research notes.", encoding="utf-8")
            recent.write_text(
                "# Familiar dashboard work\n\nToday we worked on Familiar dashboard and project brief outputs.",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault), "--date", "2026-06-12", "--limit", "3"],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["written_count"], 1)
            self.assertEqual(payload["items"][0]["source_path"], "Research/Familiar dashboard decisions.md")
            self.assertNotIn("Nvidia valuation", json.dumps(payload))

            note = vault / "Daily" / "Resurfaced" / "2026-06-12 Resurfaced Notes.md"
            self.assertTrue(note.exists())
            body = note.read_text(encoding="utf-8")
            self.assertIn("kind: resurfaced-notes", body)
            self.assertIn("Research/Familiar dashboard decisions.md", body)
            self.assertIn("dashboard should read project briefs", body)
            state = vault / ".familiar" / "resurface-state.json"
            self.assertTrue(state.exists())

            second = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault), "--date", "2026-06-12", "--limit", "3"],
                check=True,
                text=True,
                capture_output=True,
            )
            second_payload = json.loads(second.stdout)
            self.assertEqual(second_payload["written_count"], 0)
            self.assertEqual(second_payload["items"], [])


if __name__ == "__main__":
    unittest.main()

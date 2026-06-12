import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inbox_triage.py"


class InboxTriageTests(unittest.TestCase):
    def test_suggests_destinations_without_moving_notes_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            inbox = vault / "_Inbox"
            inbox.mkdir(parents=True)
            dashboard = inbox / "Familiar Dashboard UI.md"
            research = inbox / "Nvidia Equity Research.md"
            dashboard.write_text(
                "# Familiar Dashboard UI\n\nBuild an Obsidian-like dashboard for Kimi and MCP memory.",
                encoding="utf-8",
            )
            research.write_text(
                "# Nvidia Equity Research\n\nCapture valuation, stock analysis, and research notes.",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault)],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["applied"])
            self.assertEqual(payload["suggestions_count"], 2)
            by_name = {Path(item["source_path"]).name: item for item in payload["suggestions"]}
            self.assertEqual(
                by_name["Familiar Dashboard UI.md"]["target_path"],
                "Projects/Familiar Second Brain/Familiar Dashboard UI.md",
            )
            self.assertIn("dashboard", by_name["Familiar Dashboard UI.md"]["tags"])
            self.assertIn("Familiar", by_name["Familiar Dashboard UI.md"]["links"])
            self.assertEqual(by_name["Nvidia Equity Research.md"]["target_path"], "Research/Nvidia Equity Research.md")
            self.assertTrue(dashboard.exists())
            self.assertTrue(research.exists())

    def test_apply_moves_notes_to_suggested_destinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            inbox = vault / "_Inbox"
            inbox.mkdir(parents=True)
            note = inbox / "Familiar Dashboard UI.md"
            note.write_text("# Familiar Dashboard UI\n\nBuild dashboard memory graph features.", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault), "--apply"],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

            target = vault / "Projects" / "Familiar Second Brain" / "Familiar Dashboard UI.md"
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["applied"])
            self.assertEqual(payload["moved_count"], 1)
            self.assertFalse(note.exists())
            self.assertTrue(target.exists())
            self.assertIn("dashboard memory graph", target.read_text(encoding="utf-8"))

    def test_research_intent_wins_over_default_familiar_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            inbox = vault / "_Inbox"
            inbox.mkdir(parents=True)
            note = inbox / "SpaceX IPO.md"
            note.write_text(
                "\n".join(
                    [
                        "# SpaceX IPO",
                        "",
                        "Capture IPO details, valuation, and market research.",
                        "",
                        "## Links",
                        "",
                        "- [[Kimi Work]]",
                        "- [[Familiar]]",
                        "- [[Second Brain]]",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault)],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["suggestions"][0]["target_path"], "Research/SpaceX IPO.md")
            self.assertIn("research", payload["suggestions"][0]["tags"])


if __name__ == "__main__":
    unittest.main()

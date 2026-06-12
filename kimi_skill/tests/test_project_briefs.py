import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project_briefs.py"


class ProjectBriefTests(unittest.TestCase):
    def test_writes_project_brief_from_project_notes_and_related_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            project = vault / "Projects" / "Familiar Second Brain"
            session_dir = vault / "Daily" / "Kimi Sessions"
            inbox = vault / "_Inbox"
            project.mkdir(parents=True)
            session_dir.mkdir(parents=True)
            inbox.mkdir(parents=True)

            (project / "Plan.md").write_text(
                "\n".join(
                    [
                        "# Familiar Second Brain Plan",
                        "",
                        "Build daily briefs, smart inbox triage, and a dashboard shell.",
                        "Decision: use Markdown files as the source of truth.",
                        "Follow up: connect dashboard to project briefs.",
                    ]
                ),
                encoding="utf-8",
            )
            (session_dir / "2026-06-12 Familiar dashboard work.md").write_text(
                "\n".join(
                    [
                        "---",
                        "created: 2026-06-12T10:00:00Z",
                        "kind: session-summary",
                        "---",
                        "",
                        "# Familiar dashboard work",
                        "",
                        "Kimi discussed Familiar dashboard memory graph and project brief outputs.",
                    ]
                ),
                encoding="utf-8",
            )
            (inbox / "Familiar UI idea.md").write_text(
                "# Familiar UI idea\n\nObsidian-like project dashboard with a timeline.",
                encoding="utf-8",
            )
            (session_dir / "2026-06-12 Nvidia work.md").write_text(
                "# Nvidia work\n\nEquity research and valuation.",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault), "--no-model"],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

            brief = project / "Brief.md"
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["projects_count"], 1)
            self.assertEqual(payload["written_count"], 1)
            self.assertTrue(brief.exists())
            body = brief.read_text(encoding="utf-8")
            self.assertIn("kind: project-brief", body)
            self.assertIn("# Familiar Second Brain Brief", body)
            self.assertIn("Build daily briefs, smart inbox triage", body)
            self.assertIn("use Markdown files as the source of truth", body)
            self.assertIn("connect dashboard to project briefs", body)
            self.assertIn("Daily/Kimi Sessions/2026-06-12 Familiar dashboard work.md", body)
            self.assertIn("_Inbox/Familiar UI idea.md", body)
            self.assertNotIn("Nvidia work", body)

            mtime = brief.stat().st_mtime_ns
            time.sleep(0.01)
            second = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault), "--no-model"],
                check=True,
                text=True,
                capture_output=True,
            )
            second_payload = json.loads(second.stdout)
            self.assertEqual(second_payload["written_count"], 0)
            self.assertEqual(brief.stat().st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main()

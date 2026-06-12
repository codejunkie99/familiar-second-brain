import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vault_audit.py"


class VaultAuditTests(unittest.TestCase):
    def test_reports_duplicates_and_contradictions_without_modifying_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            research = vault / "Research"
            projects = vault / "Projects" / "Familiar Second Brain"
            research.mkdir(parents=True)
            projects.mkdir(parents=True)

            first = research / "SpaceX IPO.md"
            duplicate = research / "SpaceX IPO copy.md"
            yes = projects / "Dashboard enabled.md"
            no = projects / "Dashboard disabled.md"
            first.write_text("# SpaceX IPO\n\nSpaceX IPO valuation and market analysis notes.", encoding="utf-8")
            duplicate.write_text("# SpaceX IPO\n\nSpaceX IPO valuation and market analysis notes.", encoding="utf-8")
            yes.write_text("# Dashboard enabled\n\nDecision: dashboard enabled for the Familiar project.", encoding="utf-8")
            no.write_text("# Dashboard disabled\n\nDecision: dashboard disabled for the Familiar project.", encoding="utf-8")
            before = {path: path.read_text(encoding="utf-8") for path in (first, duplicate, yes, no)}

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault)],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["duplicates_count"], 1)
            duplicate_paths = set(payload["duplicates"][0]["paths"])
            self.assertEqual(duplicate_paths, {"Research/SpaceX IPO.md", "Research/SpaceX IPO copy.md"})
            self.assertEqual(payload["contradictions_count"], 1)
            contradiction_paths = set(payload["contradictions"][0]["paths"])
            self.assertEqual(
                contradiction_paths,
                {
                    "Projects/Familiar Second Brain/Dashboard enabled.md",
                    "Projects/Familiar Second Brain/Dashboard disabled.md",
                },
            )
            self.assertIn("dashboard", payload["contradictions"][0]["topic"])
            for path, body in before.items():
                self.assertEqual(path.read_text(encoding="utf-8"), body)


if __name__ == "__main__":
    unittest.main()

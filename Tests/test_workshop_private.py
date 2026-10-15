import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from Scripts import stage_workshop as stage


class SubscriberCandidateTests(unittest.TestCase):
    def test_private_jobs_reuse_only_reviewed_org_publisher_label(self):
        workflow = (stage.ROOT / ".github/workflows/steam-private.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("runs-on: [self-hosted, linux, steamcmd-private-publisher]"), 2)
        self.assertNotIn("lwm-steamcmd-private-publisher", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  pull_request:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("environment: steam-workshop-private", workflow)
        self.assertIn('[[ "$GITHUB_REPOSITORY" == "sucRo-RimWorld/LWM-s-Fuel-Filter-Fix" ]]', workflow)

    def test_source_contract_and_allowlist(self):
        data = stage.source_payload()
        self.assertEqual(set(data), set(stage.FILES))
        self.assertNotIn("1.6/Assemblies/LWMsFuelFilterFix.pdb", data)
        self.assertNotIn("README.md", data)
        self.assertNotIn("Source/FuelSearch.cs", data)

    def test_staging_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            first = stage.stage(Path(d))
            one = (Path(d) / stage.ZIP_NAME).read_bytes()
            second = stage.stage(Path(d))
            self.assertEqual(first, second)
            self.assertEqual(one, (Path(d) / stage.ZIP_NAME).read_bytes())

    def test_archive_rejects_tampering_and_extra_paths(self):
        with tempfile.TemporaryDirectory() as d:
            stage.stage(Path(d))
            archive = Path(d) / stage.ZIP_NAME
            self.assertEqual(len(stage.verify_archive(archive)), 64)
            archive.write_bytes(archive.read_bytes() + b"BAD")
            with self.assertRaises(ValueError):
                stage.verify_archive(archive)
            with zipfile.ZipFile(archive, "w") as z:
                for key, val in stage.source_payload().items():
                    z.writestr(key, val)
                z.writestr("Source/secret.txt", "never publish")
            with self.assertRaises(ValueError):
                stage.verify_archive(archive)


if __name__ == "__main__":
    unittest.main()

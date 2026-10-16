import io
import os
import subprocess
import sys
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

    def test_unarmed_host_check_passes_without_authorizing_creation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage.stage(root / "dist")
            archive = root / "dist" / stage.ZIP_NAME
            steamcmd = root / "steamcmd.sh"
            steamcmd.write_text("#!/bin/sh\\nexit 99\\n", encoding="utf-8")
            steamcmd.chmod(0o700)
            private = root / "lwm-private"
            private.mkdir(mode=0o700)
            state = private / "state.json"
            env = os.environ.copy()
            env.update({
                "LWM_STEAMCMD_BIN": str(steamcmd),
                "LWM_STEAM_ACCOUNT": "test-account",
                "LWM_STEAM_STATE": str(state),
            })
            env.pop("LWM_ALLOW_PRIVATE_CREATE", None)
            base = [
                sys.executable, str(stage.ROOT / "Scripts/steam_private.py"),
                "--archive", str(archive),
            ]
            checked = subprocess.run(
                base + ["--operation", "host_check"], env=env,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("HOST_CHECK_PASS no item; first-private-create NOT armed", checked.stdout)
            self.assertFalse(state.exists())

            denied = subprocess.run(
                base + ["--operation", "create_private", "--confirm", "CREATE_PRIVATE_ONLY"],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("Creation blocked", denied.stderr)
            self.assertFalse(state.exists())

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

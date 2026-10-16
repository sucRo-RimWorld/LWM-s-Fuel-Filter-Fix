import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from Scripts import stage_workshop as stage
sys.path.insert(0, str(stage.ROOT / "Scripts"))
from Scripts import steam_private
from Scripts import steamworks_lwm
from unittest.mock import patch


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

    def test_chat_issue_dispatch_is_whitelisted_and_release_is_main_pinned(self):
        text = (stage.ROOT / ".github/workflows/steam-private.yml").read_text(encoding="utf-8")
        self.assertIn("issues:", text)
        self.assertIn("types: [opened]", text)
        self.assertIn("github.event.issue.user.login == 'sucRo0629'", text)
        self.assertIn("github.event.issue.title == '[publish:lwm-private-create]'", text)
        self.assertIn("github.event.issue.title == '[publish:lwm-private-preflight]'", text)
        self.assertIn("source_sha=([0-9a-f]{40})", text)
        self.assertIn('"$exact_sha" == "$GITHUB_SHA"', text)
        self.assertIn("needs: [request_gate, preflight, tag_readiness]", text)
        self.assertIn("ISSUE_ARM_CREATE: ${{ needs.request_gate.outputs.arm_create }}", text)
        self.assertIn("export LWM_ALLOW_PRIVATE_CREATE=YES", text)
        self.assertIn("environment: steam-workshop-private", text)
        self.assertIn("name: Apply Mod and 1.6 category tags via authenticated Steamworks", text)
        self.assertNotIn('  push:', text)

    def test_reviewed_description_changenote_and_visibility_reach_vdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp)
            # Metadata in the checkout is the same metadata packaged by the allowlist.
            (content / "About").mkdir()
            (content / "About/About.xml").write_bytes(
                (stage.ROOT / "About/About.xml").read_bytes()
            )
            vdf = content / "item.vdf"
            steam_private.write_vdf(vdf, content, 0)
            data = vdf.read_text(encoding="utf-8")
            self.assertIn('"visibility" "2"', data)
            self.assertIn('"publishedfileid" "0"', data)
            self.assertIn("▼ English" + chr(10), data)
            self.assertIn("▼ 日本語" + chr(10), data)
            self.assertNotIn("▼ English" + chr(92) + "n", data)
            self.assertNotIn("▼ 日本語" + chr(92) + "n", data)
            self.assertIn("0.1.0 — Initial private build", data)
            self.assertIn("3288440994", data)
            self.assertNotIn('"tags"', data)  # SteamCMD does not reliably set tags.

    def test_tags_are_authenticated_and_do_not_repeat_ambiguous_submissions(self):
        self.assertEqual(steamworks_lwm.source_tags(), ("Mod", "1.6"))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                with patch.object(steamworks_lwm, "check_session"), patch.object(
                    steamworks_lwm, "call_agent", return_value={
                        "success": True, "publishedFileId": "3819497324",
                        "steamAppId": 294100, "steamUserLoggedOn": True,
                        "submitResult": "OK", "timedOut": False,
                        "userNeedsToAcceptWorkshopLegalAgreement": False,
                        "tags": ["Mod", "1.6"],
                    }
                ) as send:
                    steamworks_lwm.sync(Path(tmp) / "dummy", "3819497324", "38910030001")
                    self.assertEqual(send.call_count, 1)
                    steamworks_lwm.sync(Path(tmp) / "dummy", "3819497324", "38910030001")
                    self.assertEqual(send.call_count, 1)
                    p = steamworks_lwm.receipt_path("3819497324", "38910030001")
                    self.assertEqual(__import__("json").loads(p.read_text())["status"], "OK")
                with patch.object(steamworks_lwm, "check_session"), patch.object(
                    steamworks_lwm, "call_agent", side_effect=RuntimeError("unknown")
                ):
                    with self.assertRaises(RuntimeError):
                        steamworks_lwm.sync(Path(tmp) / "dummy", "3819497325", "38910030002")
                    with self.assertRaises(ValueError):
                        steamworks_lwm.sync(Path(tmp) / "dummy", "3819497325", "38910030002")

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
            steamcmd.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
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

#!/usr/bin/env python3
"""Offline source/package contract checks; not RimWorld gameplay tests."""
from pathlib import Path
import re
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source" / "FuelSearch.cs"

class SourcePackageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = SOURCE.read_text(encoding="utf-8")
        cls.meta = ET.parse(ROOT / "About" / "About.xml").getroot()
        cls.build = ET.parse(ROOT / "Source" / "LWMsFuelFilterFix.csproj").getroot()
        cls.tests = (ROOT / "Tests" / "Program.cs").read_text(encoding="utf-8")

    def test_package_id_and_only_16_supported(self):
        self.assertEqual(self.meta.findtext("packageId"), "sucro.lwmsfuelfilterfix")
        self.assertEqual([x.text for x in self.meta.findall("supportedVersions/li")], ["1.6"])

    def test_required_mods_and_load_order(self):
        deps = {x.findtext("packageId") for x in self.meta.findall("modDependencies/li")}
        order = {x.text for x in self.meta.findall("loadAfter/li")}
        self.assertEqual(deps, {"brrainz.harmony", "zal.lwmfuelfilter"})
        self.assertTrue(deps.issubset(order))

    def test_project_targets_net48_and_output_in_16(self):
        props = self.build.find("PropertyGroup")
        self.assertEqual(props.findtext("TargetFramework"), "net48")
        self.assertIn("1.6/Assemblies", props.findtext("OutputPath"))
        refs = {x.get("Include") for x in self.build.findall("ItemGroup/Reference")}
        self.assertTrue({"Assembly-CSharp", "UnityEngine.CoreModule", "0Harmony", "FuelFilter"}.issubset(refs))

    def test_code_installs_harmony_patches(self):
        self.assertRegex(self.code, r"new Harmony\([^)]*\)\.PatchAll\(\)")
        self.assertIn('[HarmonyPatch(typeof(RefuelWorkGiverUtility), "FindBestFuel")]', self.code)
        self.assertIn('[HarmonyPatch(typeof(RefuelWorkGiverUtility), "FindAllFuel")]', self.code)

    def test_search_request_is_bounded_to_haulables(self):
        self.assertIn("ThingRequest.ForGroup(ThingRequestGroup.HaulableEver)", self.code)
        self.assertNotIn("selected.BestThingRequest", self.code)
        self.assertNotIn("supported.BestThingRequest", self.code)

    def test_both_filters_and_haulability_are_required(self):
        self.assertRegex(
            self.code,
            r"candidate\.def\.EverHaulable\s*&&\s*supported\.Allows\(candidate\)\s*&&\s*selected\.Allows\(candidate\)"
        )

    def test_normal_refuel_keeps_forbidden_and_reservation_guards(self):
        self.assertIn("GenClosest.ClosestThingReachable(", self.code)
        self.assertIn("!candidate.IsForbidden(pawn)", self.code)
        self.assertIn("pawn.CanReserve(candidate)", self.code)

    def test_atomic_refuel_keeps_engine_quantity_utility(self):
        self.assertIn("GetFuelCountToFullyRefuel()", self.code)
        self.assertIn("RefuelWorkGiverUtility.FindEnoughReservableThings(", self.code)
        self.assertIn("new IntRange(count, count)", self.code)
        self.assertIn("FuelSearch.Allows(candidate, supported, selected)", self.code)

    def test_without_both_filters_original_game_method_runs(self):
        self.assertEqual(self.code.count("if (!FuelSearch.TryGetFilters(refuelable, out var supported, out var selected))"), 2)
        self.assertGreaterEqual(self.code.count("return true;"), 2)
        self.assertIn("return supported != null && selected != null;", self.code)

    def test_patch_does_not_rewrite_saved_filter(self):
        self.assertNotRegex(self.code, r"\.SetAllow\(|\.SetDisallowAll\(|\.CopyAllowancesFrom\(")

    def test_existing_managed_regression_cases_remain(self):
        required = (
            "Reproduce poisoned request",
            "Search remains bounded",
            "Allowed fuel survives hidden building",
            "User-disabled supported fuel stays disabled",
            "Hidden building is rejected",
            "Stale unsupported item is rejected",
            "Empty selection burns nothing",
            "Clean selection works",
            "Search does not mutate filters",
        )
        for case in required:
            with self.subTest(case=case):
                self.assertIn('"' + case + '"', self.tests)

    def test_committed_dll_is_clr_pe(self):
        dll = (ROOT / "1.6" / "Assemblies" / "LWMsFuelFilterFix.dll").read_bytes()
        self.assertGreater(len(dll), 1024)
        self.assertEqual(dll[:2], b"MZ")
        pe_offset = struct.unpack_from("<I", dll, 0x3C)[0]
        self.assertLess(pe_offset + 4, len(dll))
        self.assertEqual(dll[pe_offset:pe_offset + 4], b"PE\0\0")
        self.assertIn(b"BSJB", dll)

if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Explicit-allowlist, immutable Steam Workshop candidate for LWM Fuel Filter Fix.

This script never contacts Steam. The upload is in steam_private.py only.
"""
import argparse
import hashlib
import io
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP_NAME = "LWM-s-Fuel-Filter-Fix-1.6.zip"
FILES = (
    "About/About.xml",
    "About/Preview.png",
    "1.6/Assemblies/LWMsFuelFilterFix.dll",
    "LICENSE",
)
TITLE = "LWM's Fuel Filter Fix"
PACKAGE_ID = "sucro.lwmsfuelfilterfix"
REQUIRED_MODS = {"brrainz.harmony", "zal.lwmfuelfilter"}


def source_payload(root=ROOT):
    result = {}
    for relative in FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Missing or unsafe subscriber file: " + relative)
        result[relative] = path.read_bytes()
    metadata = ET.fromstring(result["About/About.xml"])
    if metadata.findtext("name") != TITLE or metadata.findtext("packageId") != PACKAGE_ID:
        raise ValueError("Mod identity changed")
    if [x.text for x in metadata.findall("supportedVersions/li")] != ["1.6"]:
        raise ValueError("Unexpected supported versions")
    dependencies = {x.findtext("packageId") for x in metadata.findall("modDependencies/li")}
    if dependencies != REQUIRED_MODS:
        raise ValueError("Dependencies changed")
    if not (metadata.findtext("description") or "").strip():
        raise ValueError("Workshop description is missing")
    image = result["About/Preview.png"]
    if len(image) < 24 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
        raise ValueError("Preview is not a PNG")
    if struct.unpack(">II", image[16:24]) != (640, 380):
        raise ValueError("Preview must be the approved 640x380 format")
    dll = result["1.6/Assemblies/LWMsFuelFilterFix.dll"]
    if len(dll) <= 1024 or dll[:2] != b"MZ" or b"BSJB" not in dll:
        raise ValueError("Missing production .NET DLL")
    if not result["LICENSE"].strip():
        raise ValueError("Missing license")
    return result


def deterministic_zip(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in FILES:
            item = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            z.writestr(item, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def verify_archive(archive, root=ROOT):
    expected = deterministic_zip(source_payload(root))
    received = Path(archive).read_bytes()
    with zipfile.ZipFile(io.BytesIO(received)) as z:
        if z.namelist() != list(FILES):
            raise ValueError("Candidate contains missing, additional or reordered paths")
        for item in z.infolist():
            if item.is_dir() or item.file_size > 4 * 1024 * 1024:
                raise ValueError("Invalid candidate entry")
    if received != expected:
        raise ValueError("Candidate bytes do not match the exact source checkout")
    return hashlib.sha256(received).hexdigest()


def stage(out_dir, root=ROOT):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    archive = out / ZIP_NAME
    blob = deterministic_zip(source_payload(root))
    archive.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    (out / "sha256.txt").write_text(f"{digest}  {ZIP_NAME}\n", encoding="ascii")
    assert verify_archive(archive, root) == digest
    return digest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    if (args.output is None) == (args.verify is None):
        p.error("Choose exactly one of --output or --verify")
    digest = stage(args.output) if args.output else verify_archive(args.verify)
    print(f"SUBSCRIBER_CANDIDATE_PASS files={len(FILES)} sha256={digest}")


if __name__ == "__main__":
    main()

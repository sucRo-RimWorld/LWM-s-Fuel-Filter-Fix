#!/usr/bin/env python3
"""Authenticated desktop Steamworks category tags for LWM Fuel Filter Fix.

No Steam credentials in Actions. Receipt is host-private and fails closed if
the tag submission could have started but did not reach a confirmed result.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from stage_workshop import ROOT, PACKAGE_ID

APP_ID = 294100
TAGS = ("Mod", "1.6")
TAG_CHANGE_NOTE = "0.1.0 — Set RimWorld Mod / 1.6 category tags"


def source_tags() -> tuple[str, ...]:
    about = ET.fromstring((ROOT / "About/About.xml").read_bytes())
    if about.findtext("packageId") != PACKAGE_ID:
        raise ValueError("Unexpected source packageId")
    versions = [x.text for x in about.findall("supportedVersions/li")]
    if versions != ["1.6"]:
        raise ValueError("Unexpected source supported versions")
    return ("Mod", *versions)


def agent_path() -> Path:
    value = (os.environ.get("LWM_STEAMWORKS_AGENT_BIN")
             or os.environ.get("CCTO_STEAMWORKS_AGENT_BIN"))
    if not value:
        raise ValueError("Steamworks desktop agent not provisioned")
    agent = Path(value)
    if not agent.is_absolute() or not agent.is_file() or not os.access(agent, os.X_OK):
        raise ValueError("Steamworks desktop agent unavailable")
    if agent.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Agent must be outside the checkout")
    return agent


def call_agent(agent: Path, params: list[str], timeout: int = 210) -> dict:
    result = subprocess.run(
        [str(agent), *params], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, errors="replace",
        timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError("Steamworks agent failed (sensitive output withheld)")
    try:
        envelope = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("Steamworks agent returned invalid JSON") from exc
    if not isinstance(envelope, dict) or envelope.get("status") != "ok":
        raise RuntimeError("Steamworks agent returned non-success status")
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Steamworks agent result missing")
    return data


def check_session(agent: Path) -> None:
    response = call_agent(agent, ["steam-session-probe"], timeout=90)
    if (response.get("ready") is not True
            or response.get("steamUserLoggedOn") is not True
            or response.get("steamAppId") != APP_ID):
        raise RuntimeError("Steam desktop is not authenticated for RimWorld")


def receipt_path(item_id: str, run_id: str) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise ValueError("Only the Windows Steam desktop account may submit tags")
    if not re.fullmatch(r"[1-9][0-9]{7,19}", item_id):
        raise ValueError("Invalid numeric Workshop item ID")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise ValueError("Invalid GitHub upload run ID")
    folder = Path(base).resolve() / "LWMWorkshopTagReceipts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{item_id}-{run_id}.json"
    if path.is_symlink():
        raise ValueError("Tag receipt symlink not allowed")
    return path


def store_receipt(path: Path, state: str, item_id: str, run_id: str) -> None:
    fd, temp = tempfile.mkstemp(prefix=".lwm-tags-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump({
                "schema": 1, "appid": APP_ID, "item_id": item_id,
                "run_id": run_id, "tags": list(TAGS), "status": state,
            }, out, sort_keys=True)
            out.write("\n")
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def sync(agent: Path, item_id: str, run_id: str) -> None:
    if source_tags() != TAGS:
        raise ValueError("Source tags differ from the approved Mod/1.6 values")
    path = receipt_path(item_id, run_id)
    if path.exists():
        obj = json.loads(path.read_text(encoding="utf-8"))
        if (obj.get("schema"), obj.get("appid"), obj.get("item_id"),
                obj.get("run_id"), obj.get("tags")) != (1, APP_ID, item_id, run_id, list(TAGS)):
            raise ValueError("Existing tag receipt does not match this upload")
        if obj.get("status") == "OK":
            print("TAGS_ALREADY_ACCEPTED; Steam-side readback still unverified")
            return
        raise ValueError("Prior tag operation is uncertain; do not resubmit")
    check_session(agent)
    store_receipt(path, "PENDING", item_id, run_id)
    reply = call_agent(agent, [
        "set-tags", item_id, *TAGS,
        "--confirm", "--changenote", TAG_CHANGE_NOTE,
    ])
    if (reply.get("success") is not True
            or str(reply.get("publishedFileId")) != item_id
            or reply.get("steamAppId") != APP_ID
            or reply.get("steamUserLoggedOn") is not True
            or reply.get("submitResult") != "OK"
            or reply.get("timedOut") is not False
            or reply.get("userNeedsToAcceptWorkshopLegalAgreement") is not False
            or reply.get("tags") != list(TAGS)):
        raise RuntimeError("Tag submission result ambiguous; inspect Steam before retrying")
    store_receipt(path, "OK", item_id, run_id)
    print(f"STEAMWORKS_TAG_SUBMIT_PASS item_id={item_id} tags=Mod,1.6; "
          "Steam page tags and private visibility not independently verified")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--sync", action="store_true")
    parser.add_argument("--item-id", default="")
    parser.add_argument("--upload-run-id", default="")
    args = parser.parse_args()
    if source_tags() != TAGS:
        raise ValueError("Unapproved category tags")
    agent = agent_path()
    if args.probe:
        if args.item_id or args.upload_run_id:
            raise ValueError("Probe may not specify an item or run")
        check_session(agent)
        print("STEAMWORKS_DESKTOP_PROBE_PASS no Steam modification")
    else:
        sync(agent, args.item_id, args.upload_run_id)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)

#!/usr/bin/env python3
"""Private-only RimWorld SteamCMD uploader. No Steam credentials in GitHub.

A dedicated, locally authenticated publisher runner is required. This file
does not create or update an item without explicit manual authorization.
"""
import argparse
import json
import os
import re
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from stage_workshop import ROOT, ZIP_NAME, TITLE, verify_archive

APP_ID = "294100"
VISIBILITY = "2"  # Steam: private (creator only).
CREATE_CONFIRMATION = "CREATE_PRIVATE_ONLY"
UPDATE_CONFIRMATION = "UPDATE_PRIVATE_ONLY"


def kv(value):
    if any(ord(char) < 32 and char not in "\r\n\t" for char in value):
        raise ValueError("Unsafe Steam KeyValues field")
    # SteamCMD renders escaped backslash-n literally on Workshop pages.
    # Preserve actual line breaks inside quoted VDF values.
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r\n", "\n").replace("\r", "\n").replace("\t", "\\t")


def write_vdf(path, content_dir, item_id):
    metadata = ET.parse(content_dir / "About" / "About.xml").getroot()
    if metadata.findtext("packageId") != "sucro.lwmsfuelfilterfix":
        raise ValueError("Unexpected publisher metadata identity")
    description = (ROOT / "Docs/WorkshopDescription.txt").read_text(encoding="utf-8").strip()
    changenote = (ROOT / "Docs/WorkshopChangenote.txt").read_text(encoding="utf-8").strip()
    if not description or not changenote:
        raise ValueError("Workshop description or changenote absent")
    fields = {
        "appid": APP_ID,
        "publishedfileid": str(item_id),
        "contentfolder": str(content_dir.resolve()),
        "previewfile": str((content_dir / "About" / "Preview.png").resolve()),
        "visibility": VISIBILITY,
        "title": TITLE,
        "description": description,
        "changenote": changenote,
    }
    lines = ['"workshopitem"', "{"]
    lines.extend('    "' + key + '" "' + kv(value) + '"' for key, value in fields.items())
    lines.append("}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def host_configuration():
    steamcmd = os.environ.get("LWM_STEAMCMD_BIN", "")
    account = os.environ.get("LWM_STEAM_ACCOUNT", "")
    state_name = os.environ.get("LWM_STEAM_STATE", "")
    if not steamcmd or not account or not state_name:
        raise ValueError("Dedicated host SteamCMD/account/state not configured")
    exe, path = Path(steamcmd), Path(state_name)
    if not exe.is_absolute() or not exe.is_file() or not os.access(exe, os.X_OK):
        raise ValueError("SteamCMD executable unavailable")
    if not path.is_absolute() or path.is_symlink() or path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Publisher state must be host-local, outside the checkout")
    folder = path.parent
    if not folder.is_dir() or folder.is_symlink() or stat.S_IMODE(folder.stat().st_mode) != 0o700:
        raise ValueError("Publisher state directory requires mode 0700")
    if path.exists() and stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("Publisher state requires mode 0600")
    return exe, account, path


def read_state(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_state(path, data):
    # Atomic replacement, with permissions never broader than 0600.
    fd, name = tempfile.mkstemp(prefix=".lwm-publish-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True)
            f.write("\n")
        os.replace(name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_operation(operation, confirmation, account, state):
    if operation == "create_private":
        if confirmation != CREATE_CONFIRMATION:
            raise ValueError("Private creation confirmation missing")
        if state is not None or os.environ.get("LWM_ALLOW_PRIVATE_CREATE") != "YES":
            raise ValueError("Creation blocked: existing/uncertain state or unarmed publisher")
        return 0
    if operation == "update_private":
        if confirmation != UPDATE_CONFIRMATION:
            raise ValueError("Private update confirmation missing")
        if not state or state.get("status") != "created" or state.get("account") != account:
            raise ValueError("Private item owner/state mismatch")
        item_id = state.get("item_id")
        if not isinstance(item_id, int) or item_id <= 0:
            raise ValueError("No verified Workshop item ID")
        if os.environ.get("LWM_WORKSHOP_ITEM_ID", "") != str(item_id):
            raise ValueError("Host-pinned Workshop ID mismatch")
        if state.get("private_verified") is not True:
            raise ValueError("Prior upload's creator-private visibility remains unverified")
        return item_id
    raise ValueError("No public upload modes supported")


def extract_created_id(vdf, output):
    # SteamCMD usually writes the new ID back to the workshop VDF.
    vdf_text = Path(vdf).read_text(encoding="utf-8")
    found = re.search(r'"publishedfileid"\s*"([0-9]+)"', vdf_text)
    if found and int(found.group(1)) > 0:
        return int(found.group(1))
    # Fall back only to SteamCMD's explicitly reported published item ID.
    found = re.search(r"Published file to workshop[^(]*\(([0-9]{8,})\)", output, re.I)
    return int(found.group(1)) if found else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--operation",
                        choices=["preflight", "host_check", "create_private", "update_private"],
                        required=True)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    digest = verify_archive(args.archive)
    if args.operation == "preflight":
        with tempfile.TemporaryDirectory(prefix="lwm-workshop-preflight-") as td:
            work = Path(td)
            with zipfile.ZipFile(args.archive) as z:
                z.extractall(work / "content")
            vdf = work / "upload.vdf"
            write_vdf(vdf, work / "content", 0)
            data = vdf.read_text(encoding="utf-8")
            if '"visibility" "2"' not in data or '"publishedfileid" "0"' not in data:
                raise ValueError("Private-only Steam VDF gate failed")
        print("PRIVATE_PREFLIGHT_PASS sha256=" + digest)
        return

    exe, account, state_path = host_configuration()
    state = read_state(state_path)
    if args.operation == "host_check":
        if state is None:
            # A read-only host probe must never require permission to create a
            # Workshop item. Actual creation still requires the explicit flag
            # and confirmation enforced by validate_operation().
            armed = os.environ.get("LWM_ALLOW_PRIVATE_CREATE") == "YES"
            print("HOST_CHECK_PASS no item; first-private-create " + ("armed" if armed else "NOT armed"))
        elif state.get("status") == "created" and state.get("account") == account:
            print("HOST_CHECK_PASS existing item; visibility must be checked on Steam")
        else:
            raise ValueError("Unresolved publisher state; reconciliation required")
        return

    item_id = validate_operation(args.operation, args.confirm, account, state)
    # Mark the host's last known privacy check invalid BEFORE network action.
    if item_id == 0:
        write_state(state_path, {"status": "creation_uncertain", "account": account,
                                 "private_verified": False})
    else:
        state["private_verified"] = False
        state["status"] = "upload_uncertain"
        write_state(state_path, state)
    with tempfile.TemporaryDirectory(prefix="lwm-workshop-private-") as td:
        work = Path(td)
        with zipfile.ZipFile(args.archive) as z:
            z.extractall(work / "content")
        vdf = work / "upload.vdf"
        write_vdf(vdf, work / "content", item_id)
        try:
            proc = subprocess.run(
                [str(exe), "+login", account, "+workshop_build_item", str(vdf), "+quit"],
                cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, errors="replace",
                timeout=1200, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("SteamCMD timed out; host item state requires reconciliation") from exc
        if proc.returncode:
            # Never echo SteamCMD output: authentication/session details may appear.
            raise RuntimeError("SteamCMD failed; inspect protected host logs and reconcile item")
        result_id = extract_created_id(vdf, proc.stdout)
        if item_id == 0 and result_id is None:
            raise RuntimeError("SteamCMD did not return the newly created item ID; do not retry")
        if item_id and result_id not in (None, item_id):
            raise RuntimeError("SteamCMD returned a mismatching Workshop ID; reconcile state")
        write_state(state_path, {"status": "created", "account": account,
                                 "item_id": item_id or result_id,
                                 "private_verified": False, "source_sha": os.environ.get("GITHUB_SHA", ""),
                                 "candidate_sha256": digest})
    result_item_id = item_id or result_id
    # Workshop IDs are public references, not Steam credentials.
    # Expose only the numeric ID to a downstream authenticated Steamworks tag job.
    github_output = os.environ.get("GITHUB_OUTPUT") if os.environ.get("GITHUB_ACTIONS") == "true" else None
    if github_output:
        with open(github_output, "a", encoding="utf-8") as out:
            out.write("publishedfileid=" + str(result_item_id) + chr(10))
    print(f"STEAMCMD_UPLOAD_REPORTED_SUCCESS item_id={result_item_id}; creator-private visibility and subscriber bytes UNVERIFIED")


if __name__ == "__main__":
    main()

# LWM's Fuel Filter Fix — private Workshop publication

## Status and limits

RimWorld 1.6 production patch is merged. The automated 1.6 subscriber ZIP is
**preflight only**; success does not establish that Steam was contacted, that a
Workshop item exists, or that any uploaded item is actually private.

Only GitHub Actions is authorized for future uploads. No YADA upload path.
Public release or visibility escalation is NOT implemented. Use the accepted
About/Preview.png as the 640 × 380 thumbnail, and retain the exact current
sucro.lwmsfuelfilterfix ID and Harmony/LWM dependency metadata.

## Reviewed subscriber payload (four paths exactly)

- About/About.xml
- About/Preview.png
- 1.6/Assemblies/LWMsFuelFilterFix.dll
- LICENSE

The deterministic ZIP preserves the approved bytes and requires a CLR DLL,
source-matching dependencies, a bilingual About description, PNG 640 × 380,
and RimWorld 1.6. Tests, Source, README, private state, PDBs and git files are
excluded. This is independent of legacy .rimignore semantics.

## Two explicitly separate GitHub Actions routes

1. "LWM subscriber payload preflight (no Steam)": safe source ZIP validation on
   PR/main; publishes an Actions *artifact only*. No Steam access.
2. "LWM Fuel Filter private SteamCMD (manual only)": workflow_dispatch
   preflight (default), host_check, create_private, or update_private.
   All modes require current main's 40-character SHA. create_private
   requires the literal CREATE_PRIVATE_ONLY; update_private requires
   UPDATE_PRIVATE_ONLY. Private visibility 2 is hard-coded.

Live modes require protected GitHub environment steam-workshop-private
with a reviewer/approval policy, and a **dedicated** Linux/WSL GitHub Actions
organization-scoped publisher with runner label steamcmd-private-publisher.
This is the same **OS/WSL publisher runner** as CCTO for VPE, not the RimWorld
game-test runners and not the Windows Steamworks tag runner.

**Actual organization migration (2026-10-16):** the existing WSL publisher
was already organization-registered (runner ID 9, name
`steam-workshop-publisher`). It was moved in-place from organization runner
group 3 to `amj-steam-private` (group 4) without stopping the service or
re-registering. The group is restricted to exactly two public repositories:
CCTO-for-VPE and LWM-s-Fuel-Filter-Fix, and the two reviewed main workflows:
- sucRo-RimWorld/CCTO-for-VPE/.github/workflows/steam-private.yml@refs/heads/main
- sucRo-RimWorld/LWM-s-Fuel-Filter-Fix/.github/workflows/steam-private.yml@refs/heads/main

Both repositories' `steam-workshop-private` environments require human approval.
The real CCTO [runner check #38886985798](https://github.com/sucRo-RimWorld/CCTO-for-VPE/actions/runs/38886985798)
passed. The real LWM [host check #38887007326](https://github.com/sucRo-RimWorld/LWM-s-Fuel-Filter-Fix/actions/runs/38887007326)
reached the same host and verified the candidate archive, but failed because
`LWM_STEAMCMD_BIN`, `LWM_STEAM_ACCOUNT`, and `LWM_STEAM_STATE` were
not yet set in the service environment. Do not call this LWM host PASS.
The separate native-test runners must remain untouched.

Sharing means one runner/SteamCMD installation, *not* one Workshop ID/state:
LWM_STEAM_STATE is separate from CCTO_STEAM_STATE; LWM's initial private
item creation remains explicitly gated, while CCTO for VPE is update-only
on its established item ID. Shared OS account and cached Steam login still
form a shared trust boundary: only reviewed publisher jobs may execute.
GitHub's organization runner access and both per-repository
steam-workshop-private environment protections must be verified separately.

The organization migration is already complete. Do not unregister or
re-register the existing publisher runner. Do not reuse native game-test
runners or copy Steam credentials into GitHub.

## Publisher prerequisites — must be verified before live dispatch

- An isolated Linux OS account and GitHub runner restricted to this repository;
  SteamCMD installed and logged into the correct Steam account interactively,
  with Steam Guard completed on the host (no password/Guard code or auth tokens
  in GitHub, scripts, command lines or workflow inputs).
- Host-local environment variables, NOT GitHub secrets:
  LWM_STEAMCMD_BIN (absolute executable path), LWM_STEAM_ACCOUNT
  (authenticated Steam login), LWM_STEAM_STATE (absolute host-private JSON
  state file path, parent permissions 0700, file permissions 0600).
- `host_check` is strictly read-only: if no LWM state file exists, it
  reports that no item is configured and whether initial creation is armed.
  It must pass with creation **unarmed** once the three LWM host variables
  and secure state directory are configured. It must not create a state file,
  call SteamCMD, or require `LWM_ALLOW_PRIVATE_CREATE=YES`.
- For the **first item only**, after confirming the publisher account owns
  no earlier target item and the private-only release is authorized, set
  LWM_ALLOW_PRIVATE_CREATE=YES on that host. The first upload refuses any
  pre-existing state, writes creation_uncertain *before* contacting Steam,
  and will not retry blindly on an unclear Steam outcome. Creation uses
  Steam Workshop AppID 294100, PublishedFileId 0, visibility 2.
- For **updates**, set host-local LWM_WORKSHOP_ITEM_ID to the exact existing
  item ID; the private state must match the authenticated account and that
  ID and have private_verified=true from an actual Steam creator check.
  Any upload resets that flag to false before contacting Steam. Item creation
  and updates are separate explicit modes; neither can publish publicly.

## After Steam reports success

SteamCMD returning 0 is *not* proof of creator-private visibility or correct
subscriber content. As the creator, inspect the actual Workshop item and
visibility; download/subscribe to check its staged four-file payload, title,
preview, dependencies and RimWorld 1.6 load. Record the real PublishedFileId
and reconcile the host-only state; set private_verified=true only after
the actual creator-private visibility check. Never commit that state or
any Steam account information to GitHub.

If the first creation reports no item ID, fails, or times out, the
creation_uncertain marker stops retries until the Steam account's actual
item inventory is reconciled. The same holds for upload_uncertain updates.
No Steam tag-sync or public visibility claim is made by this workflow.

Functional release evidence remains in VALIDATION.md: the Vanilla and MO
9/9 native fuel scenarios passed; MO provider startup has two separately
identified original FMOD errors, and additional special-case refuel tests
are not claimed. This is an author-private field test, not public QA signoff.

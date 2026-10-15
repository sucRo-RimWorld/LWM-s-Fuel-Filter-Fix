# Validation — 2026-10-14

## Tested source and environment

- Fix: source and shipped DLL on `fix/restrict-fuel-search`; real-game probe source at `9a4559f127d1858c9c4b220939549db7b0dad79b`.
- Genuine isolated RimWorldLinux **1.6.4871 rev600** on private self-hosted GitHub Actions, with separate per-test saves/configuration.
- Actual **LWM's Fuel Filter (Continued)** 1.6 provider, Steam Workshop 3288440994; provider DLL SHA-256 `3ccb8d42c11ab9dd5ecc88e45b97dd3db6161ecedbc90943eecd26d4541bc154`.
- Harmony and RimWorks Quickstarts staged and loaded in the isolated host.
- No normal player saves, local Steam account config or Workshop publication modified.

## Completed

| Check | Result | Evidence |
| --- | --- | --- |
| Release .NET Framework 4.8 source and test builds (prior developer run) | Recorded PASS, 0 warnings/errors | Original implementation validation |
| Prior managed regression assertions (Def-only) | Recorded 9/9 PASS; not rerun here | Original implementation validation |
| GitHub-hosted offline source/package contract checks | **12/12 PASS** | [CI run 38550809115](https://github.com/sucRo-RimWorld/LWM-s-Fuel-Filter-Fix/actions/runs/38550809115) |
| Native RimWorld 1.6 Mod load, Harmony prefixes, real `ThingFilter` semantics, polluted filter request | **PASS**, Unity errors 0 | [native run 38552492151](https://github.com/sucRo-RimWorld/Ancient-Medieval-Japan-Project/actions/runs/38552492151) |
| Native actual map + colonist + campfire/wood, polluted LWM filter, normal search, forbid/disallow cases, atomic candidate search, vanilla WorkGiver job start and campfire refuel | **9/9 PASS**, Unity errors 0, process exit 0 | [Vanilla run 38554162023](https://github.com/sucRo-RimWorld/Ancient-Medieval-Japan-Project/actions/runs/38554162023) |
| Same real job/filters with VEF + SYR Processor + Medieval Overhaul | **9/9 functional assertions PASS**, Quickstart runtime errors 0; CI PASS with **two specifically identified pre-existing FMOD startup errors**; strict zero-error gate remains false | [MO final run 38554715570](https://github.com/sucRo-RimWorld/Ancient-Medieval-Japan-Project/actions/runs/38554715570) |

The MO test's two startup errors were `Cannot create FMOD::Sound instance for clip "" (Unsupported file or audio format)`. An independent native **SYR-only** Linux diagnostic reproduces FMOD audio errors without the Fix: [control run 38552500832](https://github.com/sucRo-RimWorld/Ancient-Medieval-Japan-Project/actions/runs/38552500832). The host harness separately records the nine functional refueling assertions and unfiltered audio logs. The on-demand MO job accepts **only exactly two matching known FMOD prelaunch lines**, while any added or changed Unity error remains fatal; it reports `strict_error_gate_pass=false` when these are present. No claim of clean MO startup is made.

The runtime test genuinely executes the original game WorkGiver and starts a pawn's refuel Job. After 3,600 game ticks it verifies that the campfire's `CompRefuelable.Fuel` increased. It also calls actual patched `FindBestFuel` and `FindAllFuel` while the selected fuel filter has a hidden non-haulable entry.

## Remaining coverage / not proven

1. Establish an **unpatched** equivalent game-map baseline with this exact poisoned saved-filter fixture (the poisoned `Everything` request itself is reproduced).
2. Run the same test with a torch and verify alternate actual fuel types/closer disallowed fuel, including mod-added fuel.
3. Verify HP/quality/special `ThingFilter` conditions where the fuel Def supports them.
4. Verify competing pawns, reservations, unreachable resources and enough-resource failure in live jobs (forbidden fuel already tested on map).
5. Verify **execution** of the complete all-at-once refuel Job, not merely the game's `FindAllFuel` candidate search.
6. Test save/reload filter persistence and clean-filters/no-LWM-comp fallback over live jobs.
7. Re-run compatibility against further Mod combinations and inspect their own audio/runtime baselines if they fail.

**Merge/publication criterion:** keep PR #1 in Draft until the remaining release-blocking checks are resolved. No Steam Workshop upload has been performed. Native functional PASS does not mean all game-content or mod-compatibility cases have been covered.

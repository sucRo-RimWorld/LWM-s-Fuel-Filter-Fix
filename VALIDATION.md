# Validation — 2026-10-14

## Completed

- Source and test builds: Release / .NET Framework 4.8; 0 warnings, 0 errors.
- Managed regression: 9 assertions passed.
- Reproduced `ThingFilter.BestThingRequest == Everything` with a permitted haulable fuel and a hidden non-haulable building.
- Confirmed the patch requests `HaulableEver`, accepts selected supported fuel, rejects user-disabled fuel, rejects unsupported entries, handles empty selections, and leaves both filter allowance lists unchanged.
- `git diff --check`: passed.

Test dependencies: local RimWorld 1.6.4871 and LWM's Fuel Filter (Continued) 1.1.2. Tests use real managed filter definition lists and request generation, with minimal uninitialized ThingDef fixtures and a Def-only `Allows(Thing)` override to avoid Unity initialization. These are not full game/runtime tests. Harmony patch installation is not exercised by this managed test.

## Required before release

Run in an isolated game profile, without modifying the live colony or its configuration:

1. With LWM enabled and this fix disabled, reproduce the poisoned-filter failure on a campfire and torch.
2. Enable the fix and load the same fixture; verify refuel jobs complete without changing the filter manually.
3. Permit wood only, place closer coal nearby, and verify coal is not used.
4. Disallow all fuel and verify no refuel job starts.
5. Verify forbidden, reserved and unreachable fuel is not taken.
6. Verify HP/quality/special filter conditions where applicable.
7. Verify atomic refueling honors both the user's filter and the complete required amount.
8. Verify a clean filter and a building without an LWM filter retain normal behavior.
9. Repeat with Medieval Overhaul and inspect startup/operation logs for Harmony errors and `Cannot do ClosestThingReachable searching everything without restriction`.

No game runtime test, Workshop upload, or live ModsConfig change was performed in this implementation pass.

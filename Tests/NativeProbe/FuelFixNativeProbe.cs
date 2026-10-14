using System;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using RimWorld;
using Verse;

namespace LWMsFuelFilterFix.NativeProbe
{
    public sealed class FuelFixNativeProbeMod : Mod
    {
        private const string PatchOwner = "sucro.lwmsfuelfilterfix";
        public FuelFixNativeProbeMod(ModContentPack content) : base(content)
        {
            LongEventHandler.ExecuteWhenFinished(Verify);
        }

        private static void Verify()
        {
            try
            {
                foreach (string name in new[] { "FindBestFuel", "FindAllFuel" })
                {
                    MethodInfo target = AccessTools.Method(typeof(RefuelWorkGiverUtility), name);
                    Require(target != null, "missing target: " + name);
                    Patches patches = Harmony.GetPatchInfo(target);
                    Require(patches != null && patches.Prefixes.Any(p => p.owner == PatchOwner),
                        "Harmony prefix missing: " + name);
                }

                Type type = Type.GetType("LWMsFuelFilterFix.FuelSearch, LWMsFuelFilterFix", true);
                PropertyInfo request = type.GetProperty("Request",
                    BindingFlags.NonPublic | BindingFlags.Static);
                Require(request != null && ((ThingRequest)request.GetValue(null)).group ==
                    ThingRequestGroup.HaulableEver, "search is not bounded to haulables");

                MethodInfo allows = type.GetMethod("Allows", BindingFlags.NonPublic | BindingFlags.Static);
                Require(allows != null, "missing Allows(Thing, filters)");

                ThingDef wood = DefDatabase<ThingDef>.GetNamed("WoodLog");
                ThingDef steel = DefDatabase<ThingDef>.GetNamed("Steel");
                ThingDef wall = DefDatabase<ThingDef>.GetNamed("Wall");
                Require(wood.EverHaulable && steel.EverHaulable && !wall.EverHaulable,
                    "fixture defs have unexpected haulability");

                ThingFilter supported = new ThingFilter();
                ThingFilter selected = new ThingFilter();
                supported.SetDisallowAll();
                selected.SetDisallowAll();
                supported.SetAllow(wood, true);
                supported.SetAllow(steel, true);
                selected.SetAllow(wood, true);
                selected.SetAllow(wall, true);

                Require(selected.BestThingRequest.group == ThingRequestGroup.Everything,
                    "hidden non-haulable entry did not reproduce Everything request");

                Thing fuel = ThingMaker.MakeThing(wood);
                Thing alternative = ThingMaker.MakeThing(steel);
                Func<Thing, bool> test = candidate =>
                    (bool)allows.Invoke(null, new object[] { candidate, supported, selected });
                Require(test(fuel), "selected supported wood rejected");
                Require(!test(alternative), "user-disabled steel allowed");
                supported.SetAllow(wood, false);
                Require(!test(fuel), "unsupported wood allowed");
                supported.SetAllow(wood, true);
                selected.SetDisallowAll();
                Require(!test(fuel), "empty fuel selection allowed");
                Require(supported.AllowedDefCount == 2, "original filter modified");

                Log.Message("LWM_FUEL_FILTER_NATIVE_PASS Harmony+real_filters+poisoned_request");
            }
            catch (Exception e)
            {
                Log.Error("LWM_FUEL_FILTER_NATIVE_FAIL " + e);
            }
        }

        private static void Require(bool value, string reason)
        {
            if (!value) throw new InvalidOperationException(reason);
        }
    }
}

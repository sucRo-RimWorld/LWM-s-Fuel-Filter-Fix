using System.Collections.Generic;
using System.Runtime.CompilerServices;
using HarmonyLib;
using LWM.FuelFilter;
using RimWorld;
using Verse;
using Verse.AI;

[assembly: InternalsVisibleTo("LWMsFuelFilterFix.Tests")]

namespace LWMsFuelFilterFix
{
    public sealed class FuelFilterFixMod : Mod
    {
        public FuelFilterFixMod(ModContentPack content) : base(content)
        {
            new Harmony("sucro.lwmsfuelfilterfix").PatchAll();
        }
    }

    internal static class FuelSearch
    {
        // Never use the saved user filter's BestThingRequest: hidden buildings can
        // make it request Everything, which ClosestThingReachable rejects.
        internal static ThingRequest Request => ThingRequest.ForGroup(ThingRequestGroup.HaulableEver);

        internal static bool Allows(Thing candidate, ThingFilter supported, ThingFilter selected)
        {
            return candidate.def.EverHaulable && supported.Allows(candidate) && selected.Allows(candidate);
        }

        internal static bool TryGetFilters(Thing building, out ThingFilter supported, out ThingFilter selected)
        {
            supported = building.TryGetComp<CompRefuelable>()?.Props?.fuelFilter;
            selected = building.TryGetComp<Comp_FuelFilter>()?.filter;
            return supported != null && selected != null;
        }
    }

    [HarmonyPatch(typeof(RefuelWorkGiverUtility), "FindBestFuel")]
    internal static class FindBestFuelPatch
    {
        [HarmonyPrefix]
        private static bool Prefix(Pawn pawn, Thing refuelable, ref Thing __result)
        {
            if (!FuelSearch.TryGetFilters(refuelable, out var supported, out var selected))
                return true;

            __result = GenClosest.ClosestThingReachable(
                pawn.Position, pawn.Map, FuelSearch.Request,
                PathEndMode.ClosestTouch, TraverseParms.For(pawn), 9999f,
                candidate => FuelSearch.Allows(candidate, supported, selected)
                    && !candidate.IsForbidden(pawn) && pawn.CanReserve(candidate));
            return false;
        }
    }

    [HarmonyPatch(typeof(RefuelWorkGiverUtility), "FindAllFuel")]
    internal static class FindAllFuelPatch
    {
        [HarmonyPrefix]
        private static bool Prefix(Pawn pawn, Thing refuelable, ref List<Thing> __result)
        {
            if (!FuelSearch.TryGetFilters(refuelable, out var supported, out var selected))
                return true;

            int count = refuelable.TryGetComp<CompRefuelable>().GetFuelCountToFullyRefuel();
            // Retain vanilla's quantity, reachability, fog, forbidden and reservation
            // checks; add the user's selection to atomic (all-at-once) refueling.
            __result = RefuelWorkGiverUtility.FindEnoughReservableThings(
                pawn, refuelable.Position, new IntRange(count, count),
                candidate => FuelSearch.Allows(candidate, supported, selected));
            return false;
        }
    }
}

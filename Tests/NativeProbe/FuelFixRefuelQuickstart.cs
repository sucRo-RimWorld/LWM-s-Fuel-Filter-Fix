// TEST-ONLY. Real RimWorld 1.6 map/pawn refuel regression; never shipped in the Mod.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using LWM.FuelFilter;
using RimWorks.Quickstarts;
using RimWorks.Quickstarts.Verification;
using RimWorld;
using Verse;
using Verse.AI;

namespace LWMsFuelFilterFix.NativeProbe
{
    public sealed class FuelFixRefuelQuickstart : AbstractQuickstart
    {
        private Map map;
        private Pawn pawn;
        private Thing campfire;
        private Thing fuel;
        private CompRefuelable refuel;
        private string failure;
        private bool poisoned;
        private bool bestFound;
        private bool forbiddenRejected;
        private bool selectionRejected;
        private bool allFound;
        private bool jobOffered;
        private bool jobStarted;

        public override TaggedString description =>
            "Real pawn campfire refuel with a poisoned LWM filter and selected wood";
        public override string seed => "LWM-FUEL-FIX-20261014";
        public override float planetCoverage => 0.30f;
        public override int mapSize => 150;
        public override int ticksBeforeVerify => 3600;

        public override void PostLoaded()
        {
            try
            {
                map = Find.CurrentMap;
                pawn = map?.mapPawns.FreeColonistsSpawned.FirstOrDefault();
                if (pawn == null) throw new InvalidOperationException("no native colonist on generated map");
                var candidates = map.AllCells
                    .Where(c => c.InBounds(map) && c.Standable(map) &&
                        !c.Fogged(map) && c.GetThingList(map).All(t =>
                            t.def.category != ThingCategory.Building && !(t is Plant)) &&
                        pawn.CanReach(c, PathEndMode.OnCell, Danger.Some))
                    .OrderBy(c => c.DistanceToSquared(pawn.Position)).Take(3).ToList();
                if (candidates.Count < 2)
                    throw new InvalidOperationException("no reachable clear setup cells");
                var fireDef = DefDatabase<ThingDef>.GetNamed("Campfire");
                var woodDef = DefDatabase<ThingDef>.GetNamed("WoodLog");
                var wallDef = DefDatabase<ThingDef>.GetNamed("Wall");
                campfire = GenSpawn.Spawn(ThingMaker.MakeThing(fireDef), candidates[0],
                    map, WipeMode.Vanish);
                fuel = ThingMaker.MakeThing(woodDef);
                fuel.stackCount = Math.Min(woodDef.stackLimit, 75);
                fuel = GenSpawn.Spawn(fuel, candidates[1], map, WipeMode.Vanish);
                refuel = campfire.TryGetComp<CompRefuelable>();
                var lwm = campfire.TryGetComp<Comp_FuelFilter>();
                if (refuel == null || lwm?.filter == null)
                    throw new InvalidOperationException("spawned native campfire lacks refuel/LWM filter comps");
                if (refuel.Fuel > 0f) refuel.ConsumeFuel(refuel.Fuel);
                var selected = lwm.filter;
                selected.SetDisallowAll();
                selected.SetAllow(woodDef, true);
                selected.SetAllow(wallDef, true);
                poisoned = selected.BestThingRequest.group == ThingRequestGroup.Everything;
                MethodInfo best = AccessTools.Method(typeof(RefuelWorkGiverUtility), "FindBestFuel");
                MethodInfo all = AccessTools.Method(typeof(RefuelWorkGiverUtility), "FindAllFuel");
                if (best == null || all == null)
                    throw new InvalidOperationException("native refuel search methods missing");
                Func<Thing> findBest = () =>
                    (Thing)best.Invoke(null, new object[] { pawn, campfire });
                bestFound = findBest() == fuel;
                fuel.SetForbidden(true);
                forbiddenRejected = findBest() == null;
                fuel.SetForbidden(false);
                selected.SetDisallowAll();
                selectionRejected = findBest() == null;
                selected.SetAllow(woodDef, true);
                selected.SetAllow(wallDef, true);
                var enough = (List<Thing>)all.Invoke(null, new object[] { pawn, campfire });
                allFound = enough != null && enough.Count > 0 && enough.All(x => x == fuel);
                var giver = DefDatabase<WorkGiverDef>.AllDefsListForReading
                    .Where(d => d.giverClass != null &&
                        d.giverClass.Name == "WorkGiver_Refuel")
                    .Select(d => d.Worker as WorkGiver_Scanner).FirstOrDefault(w => w != null);
                if (giver == null) throw new InvalidOperationException("native refuel work giver missing");
                Job job = giver.JobOnThing(pawn, campfire);
                jobOffered = job != null;
                if (jobOffered)
                {
                    pawn.jobs.StartJob(job, JobCondition.InterruptForced);
                    jobStarted = pawn.jobs.curJob != null &&
                        pawn.jobs.curJob.def == job.def;
                }
            }
            catch (Exception e)
            {
                failure = e.ToString();
                Log.Error("LWM_FUEL_REFUEL_QUICKSTART_SETUP_FAIL " + failure);
            }
        }

        public override QuickstartVerification Verify()
        {
            var report = new QuickstartVerification();
            report.Assert("actual map, pawn and campfire created",
                () => failure == null && map != null && pawn != null &&
                    campfire != null && campfire.Spawned && fuel != null);
            report.Assert("saved hidden item poisons native LWM search request",
                () => poisoned);
            report.Assert("patched native FindBestFuel locates real map wood",
                () => bestFound);
            report.Assert("native refuel search rejects forbidden wood",
                () => forbiddenRejected);
            report.Assert("native refuel search rejects user-disallowed wood",
                () => selectionRejected);
            report.Assert("native atomic FindAllFuel returns only selected wood",
                () => allFound);
            report.Assert("native refuel WorkGiver offers real refuel Job",
                () => jobOffered);
            report.Assert("real pawn started refuel job",
                () => jobStarted);
            report.Assert("real pawn refueled campfire after game ticks",
                () => refuel != null && refuel.Fuel > 0f);
            return report;
        }
    }
}

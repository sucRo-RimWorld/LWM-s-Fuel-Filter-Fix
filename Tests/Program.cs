using System;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Serialization;
using System.Collections.Generic;
using LWMsFuelFilterFix;
using Verse;

internal static class Program
{
    private static int passed;
    private static int Main(string[] args)
    {
        if (args.Length != 1) throw new ArgumentException("Pass the RimWorld install directory.");
        string game = Path.GetFullPath(args[0]);
        AppDomain.CurrentDomain.AssemblyResolve += (sender, request) =>
        {
            string name = new AssemblyName(request.Name).Name + ".dll";
            string[] roots = {
                Path.Combine(game, "RimWorldWin64_Data", "Managed"),
                Path.GetFullPath(Path.Combine(game, "../../workshop/content/294100/2009463077/1.6/Assemblies")),
                Path.GetFullPath(Path.Combine(game, "../../workshop/content/294100/3288440994/1.6/Assemblies"))
            };
            foreach (string root in roots)
                if (File.Exists(Path.Combine(root, name))) return Assembly.LoadFrom(Path.Combine(root, name));
            return null;
        };
        try { Run(); }
        catch (Exception error)
        {
            while (error != null)
            {
                Console.WriteLine(error.GetType().FullName + ": " + error.Message);
                error = error.InnerException;
            }
            return 1;
        }
        Console.WriteLine($"PASS {passed} assertions (real ThingFilter definition lists; Thing-level conditions bypassed outside Unity)");
        return 0;
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void Run()
    {
        var wood = MakeDef("TestWood", true);
        var coal = MakeDef("TestCoal", true);
        var statue = MakeDef("TestHiddenStatue", false);
        var supported = new DefinitionOnlyFilter();
        supported.SetAllow(wood, true);
        supported.SetAllow(coal, true);
        var selected = new DefinitionOnlyFilter();
        selected.SetAllow(wood, true);
        selected.SetAllow(statue, true);
        Check(selected.BestThingRequest.group == ThingRequestGroup.Everything, "Reproduce poisoned request");
        Check(FuelSearch.Request.group == ThingRequestGroup.HaulableEver, "Search remains bounded");
        Check(FuelSearch.Allows(new Thing { def = wood }, supported, selected), "Allowed fuel survives hidden building");
        Check(!FuelSearch.Allows(new Thing { def = coal }, supported, selected), "User-disabled supported fuel stays disabled");
        Check(!FuelSearch.Allows(new Thing { def = statue }, supported, selected), "Hidden building is rejected");
        supported.SetAllow(wood, false);
        Check(!FuelSearch.Allows(new Thing { def = wood }, supported, selected), "Stale unsupported item is rejected");
        supported.SetAllow(wood, true);
        selected.SetDisallowAll();
        Check(!FuelSearch.Allows(new Thing { def = wood }, supported, selected), "Empty selection burns nothing");
        selected.SetAllow(wood, true);
        Check(FuelSearch.Allows(new Thing { def = wood }, supported, selected), "Clean selection works");
        Check(selected.AllowedDefCount == 1 && supported.AllowedDefCount == 2, "Search does not mutate filters");
    }
    private static void Check(bool success, string name)
    {
        if (!success) throw new Exception(name);
        passed++;
        Console.WriteLine("PASS " + name);
    }
    private static ThingDef MakeDef(string name, bool haulable)
    {
        // ThingDef's constructor loads Unity shaders. These fixtures initialize only
        // fields read by the real managed filter methods, without starting Unity.
        var def = (ThingDef)FormatterServices.GetUninitializedObject(typeof(ThingDef));
        def.defName = name;
        def.category = haulable ? ThingCategory.Item : ThingCategory.Building;
        def.alwaysHaulable = haulable;
        def.virtualDefs = new List<ThingDef>();
        return def;
    }
    private sealed class DefinitionOnlyFilter : ThingFilter
    {
        // The full Allows(Thing) initializes ModsConfig/Unity. Exercise real Def
        // allowances here; HP, quality and special filters require a game test.
        public override bool Allows(Thing thing) => Allows(thing.def);
    }
}

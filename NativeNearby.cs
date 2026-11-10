// Near-entity sampling using GTA natives, not SHVDN.NativeMemory pools.
// The native nearest-object queries are approximate (not full enumeration),
// but avoid Windows-specific memory layout assumptions on iOS ARM64.
using System;
using System.Collections.Generic;
using GTA;
using GTA.Math;
using GTA.Native;

namespace SupermanStandaloneMod
{
    public sealed partial class SupermanStandalone
    {
        // Sample a bounded set of probes around the player. One native may
        // return the same closest entity for multiple probes; deduplicate.
        private static readonly Vector3[] NearbyProbeOffsets =
        {
            new Vector3(0f, 0f, 0f),
            new Vector3(.65f, 0f, 0f), new Vector3(-.65f, 0f, 0f),
            new Vector3(0f, .65f, 0f), new Vector3(0f, -.65f, 0f),
            new Vector3(.48f, .48f, 0f), new Vector3(-.48f, .48f, 0f),
            new Vector3(.48f, -.48f, 0f), new Vector3(-.48f, -.48f, 0f),
        };

        private static Ped[] NearbyPeds(Ped player, float radius)
        {
            var found = new Dictionary<int, Ped>();
            Vector3 center = player.Position;
            float probeRadius = Math.Max(4f, radius * 0.38f);
            foreach (Vector3 offset in NearbyProbeOffsets)
            {
                Vector3 probe = center + offset * radius;
                using (var outPed = new OutputArgument())
                {
                    bool exists = Function.Call<bool>(Hash.GET_CLOSEST_PED,
                        probe.X, probe.Y, probe.Z, probeRadius,
                        true, true, outPed, false, false, -1);
                    if (!exists) continue;
                    int handle = outPed.GetResult<int>();
                    if (handle == 0 || handle == player.Handle || found.ContainsKey(handle))
                        continue;
                    var ped = new Ped(handle);
                    if (ped.Exists() && (ped.Position - center).Length() <= radius)
                        found.Add(handle, ped);
                }
            }
            var result = new Ped[found.Count];
            found.Values.CopyTo(result, 0);
            return result;
        }

        private static Vehicle[] NearbyVehicles(Vector3 center, float radius)
        {
            var found = new Dictionary<int, Vehicle>();
            float probeRadius = Math.Max(4f, radius * 0.38f);
            foreach (Vector3 offset in NearbyProbeOffsets)
            {
                Vector3 probe = center + offset * radius;
                int handle = Function.Call<int>(Hash.GET_CLOSEST_VEHICLE,
                    probe.X, probe.Y, probe.Z, probeRadius, 0, 70);
                if (handle == 0 || found.ContainsKey(handle)) continue;
                var vehicle = new Vehicle(handle);
                if (vehicle.Exists() && (vehicle.Position - center).Length() <= radius)
                    found.Add(handle, vehicle);
            }
            var result = new Vehicle[found.Count];
            found.Values.CopyTo(result, 0);
            return result;
        }
    }
}

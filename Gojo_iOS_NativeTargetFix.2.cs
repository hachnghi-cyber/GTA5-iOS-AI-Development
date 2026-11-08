// Gojo iOS five powers - native entity lookup fallback for ARM64 iOS port.
// Candidate and physics natives must still be verified on a real device.
// SHVDN v2 API: .2.cs makes the required API explicit.
// PC-only System.Media audio is intentionally omitted; sound playback would
// require a separate native iOS audio bridge. Five gameplay powers are here.
// System.Windows.Forms is used only for SHVDN's KeyDown/Keys contract.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using GTA;
using GTA.Math;
using GTA.Native;

namespace GojoIOS
{
    public sealed class GojoPowers : Script
    {
        private readonly List<Entity> infinityFrozen = new List<Entity>();
        private readonly List<Entity> voidFrozen = new List<Entity>();
        private readonly HashSet<int> infinityNativeFrozen = new HashSet<int>();
        private readonly HashSet<int> voidNativeFrozen = new HashSet<int>();
        private static readonly float[] SampleX =
            { 0f, -0.52f, 0.52f, 0f, 0f,
              -0.37f, 0.37f, -0.37f, 0.37f };
        private static readonly float[] SampleY =
            { 0f, 0f, 0f, -0.52f, 0.52f,
              -0.37f, -0.37f, 0.37f, 0.37f };
        private readonly HashSet<int> purpleHitHandles = new HashSet<int>();
        private readonly Dictionary<int, DateTime> physicsExemptUntil =
            new Dictionary<int, DateTime>();
        private bool infinityEnabled;
        private DateTime nextInfinityScan = DateTime.MinValue;
        private DateTime redUntil = DateTime.MinValue;
        private DateTime nextRedPulse = DateTime.MinValue;
        private DateTime blueUntil = DateTime.MinValue;
        private DateTime nextBluePulse = DateTime.MinValue;
        private DateTime purpleUntil = DateTime.MinValue;
        private DateTime purpleStarted = DateTime.MinValue;
        private DateTime nextPurpleScan = DateTime.MinValue;
        private DateTime voidUntil = DateTime.MinValue;
        private DateTime nextVoidScan = DateTime.MinValue;
        private DateTime nextCast = DateTime.MinValue;
        private Vector3 blueCenter;
        private Vector3 purpleOrigin;
        private Vector3 purpleDirection;
        private bool redReported;
        private bool blueReported;
        private bool voidReported;
        private bool purpleReported;
        private int lastScanVehicles;
        private int lastScanPeds;
        private int lastNativeVehicleCount;
        private int lastNativePedCount;
        private float lastRedSpeed;

        public GojoPowers()
        {
            Interval = 50;
            Tick += OnTick;
            KeyDown += OnKeyDown;
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            ActivateKey(e.KeyCode);
        }

        private void ActivateKey(Keys key)
        {
            Ped player = Game.Player.Character;
            if (player == null || !player.Exists() || player.IsDead) return;

            DateTime now = DateTime.UtcNow;
            if (key == Keys.K)
            {
                EmergencyReset();
                UI.ShowSubtitle("Gojo: reset OK");
                return;
            }

            if (key == Keys.H)
            {
                infinityEnabled = !infinityEnabled;
                if (!infinityEnabled)
                {
                    ReleaseAll(infinityFrozen, voidFrozen);
                    ReleaseNativeFrozen(infinityNativeFrozen, voidNativeFrozen);
                }
                nextInfinityScan = DateTime.MinValue;
                UI.ShowSubtitle(infinityEnabled ? "Infinity: ON" : "Infinity: OFF");
                return;
            }

            // Avoid stacking several expensive effects on the same frame.
            if (now < nextCast) return;

            if (key == Keys.J)
            {
                redUntil = now.AddMilliseconds(850);
                nextRedPulse = DateTime.MinValue;
                redReported = false;
                lastRedSpeed = -1f;
                nextCast = now.AddMilliseconds(550);
                UI.ShowSubtitle("Reverse Red: blast away!");
            }
            else if (key == Keys.U)
            {
                // Touch input does not always expose a native GTA aim target.
                // Attract targets to a point in front of Gojo without aiming.
                blueCenter = player.Position + player.ForwardVector * 0.75f;
                blueUntil = now.AddMilliseconds(1100);
                nextBluePulse = DateTime.MinValue;
                blueReported = false;
                nextCast = now.AddMilliseconds(600);
                UI.ShowSubtitle("Lapse Blue: attract!");
            }
            else if (key == Keys.Y)
            {
                purpleHitHandles.Clear();
                purpleOrigin = player.Position;
                purpleDirection = player.ForwardVector;
                purpleStarted = now;
                purpleUntil = now.AddMilliseconds(1200);
                nextPurpleScan = DateTime.MinValue;
                purpleReported = false;
                nextCast = now.AddMilliseconds(1000);
                UI.ShowSubtitle("Hollow Purple: forward wave!");
            }
            else if (key == Keys.I)
            {
                voidUntil = now.AddMilliseconds(4500);
                nextVoidScan = DateTime.MinValue;
                voidReported = false;
                nextCast = now.AddMilliseconds(1000);
                UI.ShowSubtitle("Unlimited Void: 4.5 seconds!");
            }
        }

        private void OnTick(object sender, EventArgs e)
        {
            Ped player = Game.Player.Character;
            if (player == null || !player.Exists() || player.IsDead)
            {
                TouchBridge.SetEnabled(false);
                EmergencyReset();
                return;
            }

            DateTime now = DateTime.UtcNow;
            try
            {
                bool showTouch = !Game.IsPaused && !Game.IsLoading;
                TouchBridge.SetEnabled(showTouch);
                uint taps = showTouch ? TouchBridge.Consume() : 0;
                if ((taps & 1u) != 0) ActivateKey(Keys.H);
                if ((taps & 2u) != 0) ActivateKey(Keys.J);
                if ((taps & 4u) != 0) ActivateKey(Keys.U);
                if ((taps & 8u) != 0) ActivateKey(Keys.Y);
                if ((taps & 16u) != 0) ActivateKey(Keys.I);

                if (infinityEnabled && now >= nextInfinityScan)
                {
                    // Original PC Infinity is a protective outer ring, not
                    // a permanent freeze of everything next to the player.
                    UpdateFreezeArea(player, 12f, 7f,
                        infinityFrozen, voidFrozen, now);
                    nextInfinityScan = now.AddMilliseconds(220);
                }

                if (now < voidUntil)
                {
                    if (now >= nextVoidScan)
                    {
                        UpdateFreezeArea(player, 28f, 0f,
                            voidFrozen, infinityFrozen, now);
                        nextVoidScan = now.AddMilliseconds(250);
                        if (!voidReported)
                        {
                            voidReported = true;
                            UI.ShowSubtitle("Void: managed=" +
                                voidFrozen.Count + " native=" +
                                voidNativeFrozen.Count + " (auto release)");
                        }
                    }
                }
                else if (voidFrozen.Count > 0 || voidNativeFrozen.Count > 0)
                {
                    ReleaseAll(voidFrozen, infinityFrozen);
                    ReleaseNativeFrozen(voidNativeFrozen, infinityNativeFrozen);
                }

                if (now < redUntil)
                {
                    if (now >= nextRedPulse)
                    {
                        nextRedPulse = now.AddMilliseconds(145);
                        int affected, errors;
                        PushRedWithVelocity(player, now, out affected, out errors);
                        if (!redReported)
                        {
                            redReported = true;
                            // Count accepted native calls, not physical proof.
                            UI.ShowSubtitle("Red call=" + affected +
                                " err=" + errors + " pool=" +
                                lastScanVehicles + "/" + lastScanPeds +
                                " native=" + lastNativeVehicleCount +
                                "/" + lastNativePedCount +
                                " speed=" + lastRedSpeed.ToString("0.0"));
                        }
                    }
                    try { World.DrawLightWithRange(player.Position, Color.Red, 45f, 14f); }
                    catch (Exception) { /* visual effect is optional on the port */ }
                }

                if (now < blueUntil)
                {
                    if (now >= nextBluePulse)
                    {
                        nextBluePulse = now.AddMilliseconds(150);
                        int affected, errors;
                        PullBlueWithVelocity(player, blueCenter, now,
                            out affected, out errors);
                        if (!blueReported)
                        {
                            blueReported = true;
                            UI.ShowSubtitle("Blue: " + affected +
                                " targets, " + errors + " errors");
                        }
                    }
                    try { World.DrawLightWithRange(blueCenter, Color.Blue, 30f, 7f); }
                    catch (Exception) { /* visual effect is optional */ }
                }

                if (now < purpleUntil)
                {
                    double elapsed = (now - purpleStarted).TotalMilliseconds;
                    float distance = 5f +
                        (float)Math.Max(0.0, Math.Min(1.0, elapsed / 1050.0)) * 43f;
                    Vector3 impact = purpleOrigin + purpleDirection * distance;
                    // An actual travelling hitbox, rather than one point 12m
                    // ahead (which missed nearly all moving traffic).
                    int hitErrors = 0;
                    if (now >= nextPurpleScan)
                    {
                        nextPurpleScan = now.AddMilliseconds(125);
                        hitErrors = HitPurple(player, impact, now);
                    }
                    if (!purpleReported && (elapsed > 920 || purpleHitHandles.Count > 0))
                    {
                        purpleReported = true;
                        UI.ShowSubtitle("Purple: " + purpleHitHandles.Count +
                            " hits, " + hitErrors + " errors");
                    }
                    try { World.DrawLightWithRange(impact, Color.Purple, 55f, 10f); }
                    catch (Exception) { /* visual effect is optional */ }
                }
                else if (purpleHitHandles.Count > 0)
                {
                    purpleHitHandles.Clear();
                }

                // Do not grow the thaw-exemption dictionary indefinitely.
                if (physicsExemptUntil.Count > 96)
                    physicsExemptUntil.Clear();
            }
            catch (Exception ex)
            {
                // Keep entity positions recoverable after an unsupported native.
                EmergencyReset();
                UI.ShowSubtitle("Gojo error: " + ex.GetType().Name +
                    " (safe reset)");
            }
        }

        private static bool IsAliveEntity(Entity entity)
        {
            return entity != null && entity.Exists();
        }

        private static bool IsValidTarget(Entity entity, Ped player)
        {
            if (!IsAliveEntity(entity) || entity.Handle == player.Handle) return false;
            if (!(entity is Ped) && !(entity is Vehicle)) return false;
            Vehicle riding = player.CurrentVehicle;
            return riding == null || riding.Handle != entity.Handle;
        }

        // GetNearbyEntities can return no useful subclasses when an iOS port's
        // mixed entity-pool enumeration differs from Windows GTA V. Query
        // distinct typed pools instead; both APIs exist in SHVDN v2.
        private static Entity[] GetNearbyActors(Vector3 center, float radius,
            out int vehicleCount, out int pedCount)
        {
            var result = new List<Entity>();
            vehicleCount = 0;
            pedCount = 0;
            try
            {
                Vehicle[] vehicles = World.GetNearbyVehicles(center, radius);
                vehicleCount = vehicles.Length;
                foreach (Vehicle vehicle in vehicles)
                    if (vehicle != null) result.Add(vehicle);
            }
            catch (Exception) { /* the native vehicle pool may be unavailable */ }
            try
            {
                Ped[] peds = World.GetNearbyPeds(center, radius);
                pedCount = peds.Length;
                foreach (Ped ped in peds)
                    if (ped != null) result.Add(ped);
            }
            catch (Exception) { /* the native ped pool may be unavailable */ }
            return result.ToArray();
        }

        private static int GetClosestNativeVehicle(Vector3 center, float radius,
            Ped player)
        {
            // Engine native lookup does not rely on SHVDN's global entity
            // pool and is therefore a fallback for the iOS ARM64 port.
            try
            {
                int handle = Function.Call<int>(Hash.GET_CLOSEST_VEHICLE,
                    center.X, center.Y, center.Z, radius, 0, 70);
                if (handle == 0)
                    handle = Function.Call<int>(Hash.GET_CLOSEST_VEHICLE,
                        center.X, center.Y, center.Z, radius, 0, 127);
                if (handle == 0)
                    handle = Function.Call<int>(Hash.GET_CLOSEST_VEHICLE,
                        center.X, center.Y, center.Z, radius, 0, 0);
                if (handle == 0) return 0;
                Vehicle current = player.CurrentVehicle;
                if (current != null && current.Handle == handle) return 0;
                return handle;
            }
            catch (Exception) { return 0; }
        }

        private struct NativeActor
        {
            public readonly int Handle;
            public readonly bool IsVehicle;
            public readonly Vector3 Position;

            public NativeActor(int handle, bool isVehicle, Vector3 position)
            {
                Handle = handle;
                IsVehicle = isVehicle;
                Position = position;
            }
        }

        // Sample several offset native queries rather than depending on
        // ScriptHook's Windows-specific global entity pools. An individual
        // GET_CLOSEST_VEHICLE call can only return ONE nearby vehicle.
        private static List<NativeActor> GetNearbyNativeActors(Ped player,
            Vector3 center, float radius, int maxTargets)
        {
            var found = new List<NativeActor>();
            var seen = new HashSet<int>();
            float searchRadius = Math.Max(6f, radius * 0.63f);

            for (int i = 0; i < SampleX.Length && found.Count < maxTargets; i++)
            {
                Vector3 position = new Vector3(center.X + radius * SampleX[i],
                    center.Y + radius * SampleY[i], center.Z);
                int vehicle = GetClosestNativeVehicle(position, searchRadius,
                    player);
                TryAddNativeActor(vehicle, true, center, radius,
                    player, found, seen);

                if (found.Count >= maxTargets) break;
                try
                {
                    // GTA V native returns one random ped in this volume.
                    int ped = Function.Call<int>(Hash.GET_RANDOM_PED_AT_COORD,
                        position.X, position.Y, position.Z,
                        searchRadius, searchRadius, 5f, -1);
                    if (ped == 0)
                        ped = Function.Call<int>(Hash.GET_RANDOM_PED_AT_COORD,
                            position.X, position.Y, position.Z,
                            searchRadius, searchRadius, 5f, 0);
                    TryAddNativeActor(ped, false, center, radius,
                        player, found, seen);
                }
                catch (Exception) { /* optional native fallback */ }
            }
            return found;
        }

        private static void TryAddNativeActor(int handle, bool isVehicle,
            Vector3 center, float radius, Ped player,
            List<NativeActor> found, HashSet<int> seen)
        {
            if (handle == 0 || handle == player.Handle || seen.Contains(handle))
                return;
            try
            {
                Vector3 position = Function.Call<Vector3>(
                    Hash.GET_ENTITY_COORDS, handle, true);
                Vector3 offset = position - center;
                float distance = offset.Length();
                if (float.IsNaN(distance) || distance > radius + 1f)
                    return;
                // The producing native already selects the requested type.
                // Some iOS bridges return 0 for GET_ENTITY_TYPE even for a
                // valid handle, so treat it as an optional cross-check.
                try
                {
                    int actualType = Function.Call<int>(
                        Hash.GET_ENTITY_TYPE, handle);
                    if (actualType != 0 &&
                        actualType != (isVehicle ? 2 : 1)) return;
                }
                catch (Exception) { /* trust the producing native */ }
                if (!isVehicle)
                {
                    // The vehicle itself is already considered separately;
                    // do not pull a driver out of the moving car.
                    try
                    {
                        int pedVehicle = Function.Call<int>(
                            Hash.GET_VEHICLE_PED_IS_IN, handle, false);
                        if (pedVehicle != 0) return;
                    }
                    catch (Exception) { /* optional check */ }
                }
                seen.Add(handle);
                found.Add(new NativeActor(handle, isVehicle, position));
            }
            catch (Exception) { /* bad/stale native handle */ }
        }

        private bool TryMoveNativeActor(int handle, Vector3 velocity, DateTime now)
        {
            if (handle == 0) return false;
            try
            {
                // No managed Vehicle wrapper needed; iOS may not enumerate
                // the object even while native RAGE physics knows its handle.
                RemoveHandle(infinityFrozen, handle);
                RemoveHandle(voidFrozen, handle);
                infinityNativeFrozen.Remove(handle);
                voidNativeFrozen.Remove(handle);
                try { Function.Call(Hash.FREEZE_ENTITY_POSITION, handle, false); }
                catch (Exception) { /* optional on this build */ }
                try { Function.Call(Hash.SET_ENTITY_DYNAMIC, handle, true); }
                catch (Exception) { /* optional on this build */ }
                Function.Call(Hash.SET_ENTITY_VELOCITY, handle,
                    velocity.X, velocity.Y, velocity.Z);
                // A one-frame velocity can be damped by vehicle AI; apply a
                // bounded world-space impulse as a secondary physics path.
                try
                {
                    Function.Call(Hash.APPLY_FORCE_TO_ENTITY, handle, 1,
                        velocity.X * 240f, velocity.Y * 240f,
                        velocity.Z * 240f,
                        0f, 0f, 0f, 0,
                        false, false, true, false, true);
                }
                catch (Exception) { /* velocity already submitted */ }
                try { lastRedSpeed = Function.Call<float>(Hash.GET_ENTITY_SPEED, handle); }
                catch (Exception) { /* optional diagnostic */ }
                physicsExemptUntil[handle] = now.AddMilliseconds(1600);
                return true;
            }
            catch (Exception) { return false; }
        }

        private static void TryRagdollPed(int handle)
        {
            try
            {
                Function.Call(Hash.SET_PED_TO_RAGDOLL,
                    handle, 900, 1100, 0, false, false, false);
            }
            catch (Exception) { /* ragdoll is optional on this port */ }
        }

        private static bool ContainsHandle(List<Entity> items, int handle)
        {
            foreach (Entity item in items)
                if (item != null && item.Handle == handle) return true;
            return false;
        }

        private static void RemoveHandle(List<Entity> items, int handle)
        {
            for (int i = items.Count - 1; i >= 0; i--)
            {
                if (items[i] != null && items[i].Handle == handle)
                    items.RemoveAt(i);
            }
        }

        private bool IsTemporarilyThawed(int handle, DateTime now)
        {
            DateTime expires;
            if (!physicsExemptUntil.TryGetValue(handle, out expires))
                return false;
            if (now < expires) return true;
            physicsExemptUntil.Remove(handle);
            return false;
        }

        private void ThawForPower(Entity entity, DateTime now)
        {
            // Red, Blue and Purple must be able to move targets that Infinity
            // or Void has frozen; prohibit re-freeze during the power.
            RemoveHandle(infinityFrozen, entity.Handle);
            RemoveHandle(voidFrozen, entity.Handle);
            infinityNativeFrozen.Remove(entity.Handle);
            voidNativeFrozen.Remove(entity.Handle);
            entity.FreezePosition = false;
            physicsExemptUntil[entity.Handle] = now.AddMilliseconds(1600);
        }

        private void UpdateFreezeArea(Ped player, float radius, float innerRadius,
            List<Entity> current, List<Entity> other, DateTime now)
        {
            Vector3 center = player.Position;
            for (int i = current.Count - 1; i >= 0; i--)
            {
                Entity entity = current[i];
                if (!IsAliveEntity(entity))
                {
                    current.RemoveAt(i);
                    continue;
                }
                bool shouldRelease = true;
                try
                {
                    float distance = (entity.Position - center).Length();
                    shouldRelease = !IsValidTarget(entity, player) ||
                        distance > radius || distance < innerRadius ||
                        IsTemporarilyThawed(entity.Handle, now);
                }
                catch (Exception) { /* the entity may have despawned */ }
                if (shouldRelease)
                {
                    try
                    {
                        if (!ContainsHandle(other, entity.Handle))
                            entity.FreezePosition = false;
                    }
                    catch (Exception) { /* entity despawned */ }
                    current.RemoveAt(i);
                }
            }

            int vehicles, peds;
            Entity[] near = GetNearbyActors(center, radius,
                out vehicles, out peds);
            foreach (Entity entity in near)
            {
                try
                {
                    if (!IsValidTarget(entity, player) ||
                        ContainsHandle(current, entity.Handle) ||
                        IsTemporarilyThawed(entity.Handle, now) ||
                        (entity.Position - center).Length() < innerRadius) continue;
                    if (!ContainsHandle(other, entity.Handle))
                        entity.FreezePosition = true;
                    current.Add(entity);
                    if (current.Count >= 48) break;
                }
                catch (Exception) { /* ignore a single unsupported entity */ }
            }

            // Also freeze entities that RAGE knows by native handle but whose
            // managed SHVDN wrappers were not enumerated on iOS.
            HashSet<int> nativeCurrent = Object.ReferenceEquals(current,
                infinityFrozen) ? infinityNativeFrozen : voidNativeFrozen;
            HashSet<int> nativeOther = Object.ReferenceEquals(current,
                infinityFrozen) ? voidNativeFrozen : infinityNativeFrozen;
            var expired = new List<int>();
            foreach (int handle in nativeCurrent)
            {
                try
                {
                    Vector3 position = Function.Call<Vector3>(
                        Hash.GET_ENTITY_COORDS, handle, true);
                    float distance = (position - center).Length();
                    if (distance > radius || distance < innerRadius ||
                        IsTemporarilyThawed(handle, now))
                    {
                        if (!nativeOther.Contains(handle))
                            Function.Call(Hash.FREEZE_ENTITY_POSITION,
                                handle, false);
                        expired.Add(handle);
                    }
                }
                catch (Exception) { expired.Add(handle); }
            }
            foreach (int handle in expired) nativeCurrent.Remove(handle);

            List<NativeActor> nativeTargets = GetNearbyNativeActors(player,
                center, radius, 20);
            foreach (NativeActor target in nativeTargets)
            {
                try
                {
                    float distance = (target.Position - center).Length();
                    if (distance < innerRadius ||
                        IsTemporarilyThawed(target.Handle, now) ||
                        nativeCurrent.Contains(target.Handle) ||
                        ContainsHandle(current, target.Handle)) continue;
                    Function.Call(Hash.FREEZE_ENTITY_POSITION,
                        target.Handle, true);
                    nativeCurrent.Add(target.Handle);
                    if (nativeCurrent.Count >= 20) break;
                }
                catch (Exception) { /* one entity failure must not reset all */ }
            }
        }

        private static void ReleaseNativeFrozen(HashSet<int> current,
            HashSet<int> other)
        {
            foreach (int handle in current)
            {
                try
                {
                    if (!other.Contains(handle))
                        Function.Call(Hash.FREEZE_ENTITY_POSITION,
                            handle, false);
                }
                catch (Exception) { /* entity despawned */ }
            }
            current.Clear();
        }

        private static void ReleaseAll(List<Entity> current, List<Entity> other)
        {
            foreach (Entity entity in current)
            {
                try
                {
                    if (IsAliveEntity(entity) &&
                        !ContainsHandle(other, entity.Handle))
                        entity.FreezePosition = false;
                }
                catch (Exception) { /* entity might have despawned */ }
            }
            current.Clear();
        }

        private bool TrySetVelocity(Entity entity, Vector3 velocity,
            DateTime now)
        {
            try
            {
                ThawForPower(entity, now);
                Function.Call(Hash.SET_ENTITY_VELOCITY, entity.Handle,
                    velocity.X, velocity.Y, velocity.Z);
                try
                {
                    Function.Call(Hash.APPLY_FORCE_TO_ENTITY,
                        entity.Handle, 1,
                        velocity.X * 240f, velocity.Y * 240f,
                        velocity.Z * 240f,
                        0f, 0f, 0f, 0,
                        false, false, true, false, true);
                }
                catch (Exception) { /* velocity already submitted */ }
                try
                {
                    lastRedSpeed = Function.Call<float>(
                        Hash.GET_ENTITY_SPEED, entity.Handle);
                }
                catch (Exception) { /* optional diagnostic */ }
                return true;
            }
            catch (Exception) { return false; }
        }

        // Red: repeatedly push nearby traffic/peds away from Gojo. A one-frame
        // low-strength APPLY_FORCE_TO_ENTITY is overwritten by traffic AI.
        private void PushRedWithVelocity(Ped player, DateTime now,
            out int applied, out int failed)
        {
            applied = 0;
            failed = 0;
            Vector3 center = player.Position;
            var acted = new HashSet<int>();
            Entity[] nearby = GetNearbyActors(center, 35f,
                out lastScanVehicles, out lastScanPeds);
            foreach (Entity entity in nearby)
            {
                try
                {
                    if (!IsValidTarget(entity, player)) continue;
                    Vector3 delta = entity.Position - center;
                    float length = delta.Length();
                    if (length < 0.6f) delta = player.ForwardVector;
                    else delta /= length;
                    float speed = entity is Vehicle ? 22f : 15f;
                    Vector3 velocity = delta * speed;
                    velocity.Z += entity is Vehicle ? 2.0f : 3.5f;
                    if (entity is Ped) TryRagdollPed(entity.Handle);
                    if (TrySetVelocity(entity, velocity, now))
                    {
                        applied++;
                        acted.Add(entity.Handle);
                    }
                    else failed++;
                }
                catch (Exception) { failed++; }
                if (applied + failed >= 24) break;
            }

            List<NativeActor> nativeTargets = GetNearbyNativeActors(
                player, center, 35f, 24);
            lastNativeVehicleCount = 0;
            lastNativePedCount = 0;
            foreach (NativeActor target in nativeTargets)
            {
                if (target.IsVehicle) lastNativeVehicleCount++;
                else lastNativePedCount++;
                if (acted.Contains(target.Handle) || applied >= 24) continue;
                try
                {
                    Vector3 delta = target.Position - center;
                    float distance = delta.Length();
                    delta = distance > 0.6f ? delta / distance :
                        player.ForwardVector;
                    float speed = target.IsVehicle ? 22f : 15f;
                    Vector3 velocity = new Vector3(delta.X * speed,
                        delta.Y * speed,
                        delta.Z * speed + (target.IsVehicle ? 2f : 3.5f));
                    if (!target.IsVehicle) TryRagdollPed(target.Handle);
                    if (TryMoveNativeActor(target.Handle, velocity, now))
                    {
                        applied++;
                        acted.Add(target.Handle);
                    }
                    else failed++;
                }
                catch (Exception) { failed++; }
            }
        }

        // Blue: pull nearby entities to a stable point slightly ahead of Gojo.
        // This deliberately works without GTA's PC-style aim target support.
        private void PullBlueWithVelocity(Ped player, Vector3 center,
            DateTime now, out int applied, out int failed)
        {
            applied = 0;
            failed = 0;
            var acted = new HashSet<int>();
            int scannedVehicles, scannedPeds;
            Entity[] nearby = GetNearbyActors(player.Position, 35f,
                out scannedVehicles, out scannedPeds);
            foreach (Entity entity in nearby)
            {
                try
                {
                    if (!IsValidTarget(entity, player)) continue;
                    Vector3 delta = center - entity.Position;
                    float distance = delta.Length();
                    if (distance < 0.75f) continue;
                    float speed = entity is Vehicle ? 16f : 14f;
                    Vector3 velocity = delta / distance * speed;
                    velocity.Z += entity is Vehicle ? 0.4f : 1.0f;
                    if (entity is Ped) TryRagdollPed(entity.Handle);
                    if (TrySetVelocity(entity, velocity, now))
                    {
                        applied++;
                        acted.Add(entity.Handle);
                    }
                    else failed++;
                }
                catch (Exception) { failed++; }
                if (applied + failed >= 24) break;
            }

            List<NativeActor> nativeTargets = GetNearbyNativeActors(
                player, player.Position, 35f, 24);
            foreach (NativeActor target in nativeTargets)
            {
                if (acted.Contains(target.Handle) || applied >= 24) continue;
                try
                {
                    Vector3 delta = center - target.Position;
                    float distance = delta.Length();
                    if (distance > 0.75f)
                    {
                        float speed = target.IsVehicle ? 16f : 14f;
                        Vector3 velocity = delta / distance * speed;
                        velocity.Z += target.IsVehicle ? 0.4f : 1f;
                        if (!target.IsVehicle) TryRagdollPed(target.Handle);
                        if (TryMoveNativeActor(target.Handle, velocity, now))
                        {
                            applied++;
                            acted.Add(target.Handle);
                        }
                        else failed++;
                    }
                }
                catch (Exception) { failed++; }
            }
        }

        // Purple: travelling forward attack. Each handle is affected only once
        // during a cast; never delete game entities, which broke some iOS builds.
        private int HitPurple(Ped player, Vector3 point, DateTime now)
        {
            int failed = 0;
            int scannedVehicles, scannedPeds;
            Entity[] nearby = GetNearbyActors(point, 9f,
                out scannedVehicles, out scannedPeds);
            foreach (Entity entity in nearby)
            {
                try
                {
                    if (!IsValidTarget(entity, player) ||
                        !purpleHitHandles.Add(entity.Handle)) continue;
                    ThawForPower(entity, now);
                    if (entity is Vehicle)
                    {
                        // ScriptHook v2's Vehicle type does not reliably expose
                        // Explode(). Use the known GTA native instead.
                        try
                        {
                            Vector3 position = entity.Position;
                            if ((position - player.Position).Length() < 7f)
                            {
                                Vector3 away = new Vector3(
                                    purpleDirection.X * 27f,
                                    purpleDirection.Y * 27f, 6f);
                                TrySetVelocity(entity, away, now);
                            }
                            else
                                Function.Call(Hash.ADD_EXPLOSION, position.X,
                                    position.Y, position.Z, 2, 1.2f,
                                    true, false, 0.35f);
                        }
                        catch (Exception)
                        {
                            Vector3 wave = new Vector3(purpleDirection.X * 27f,
                                purpleDirection.Y * 27f, 6f);
                            if (!TrySetVelocity(entity, wave, now)) failed++;
                        }
                    }
                    else if (entity is Ped)
                    {
                        Ped victim = (Ped)entity;
                        victim.Health = Math.Max(0, victim.Health - 200);
                        Vector3 wave = new Vector3(purpleDirection.X * 17f,
                            purpleDirection.Y * 17f, 6f);
                        TrySetVelocity(entity, wave, now);
                    }
                }
                catch (Exception) { failed++; }
                if (purpleHitHandles.Count >= 16) break;
            }
            List<NativeActor> nativeTargets = GetNearbyNativeActors(
                player, point, 9f, 16);
            foreach (NativeActor target in nativeTargets)
            {
                if (purpleHitHandles.Count >= 16) break;
                if (!purpleHitHandles.Add(target.Handle)) continue;
                try
                {
                    infinityNativeFrozen.Remove(target.Handle);
                    voidNativeFrozen.Remove(target.Handle);
                    Function.Call(Hash.FREEZE_ENTITY_POSITION,
                        target.Handle, false);
                    physicsExemptUntil[target.Handle] = now.AddMilliseconds(1600);

                    if (target.IsVehicle)
                    {
                        if ((target.Position - player.Position).Length() < 7f)
                        {
                            Vector3 away = new Vector3(
                                purpleDirection.X * 27f,
                                purpleDirection.Y * 27f, 6f);
                            TryMoveNativeActor(target.Handle, away, now);
                        }
                        else
                            Function.Call(Hash.ADD_EXPLOSION,
                                target.Position.X, target.Position.Y,
                                target.Position.Z,
                                2, 1.2f, true, false, 0.35f);
                    }
                    else
                    {
                        int health = Function.Call<int>(Hash.GET_ENTITY_HEALTH,
                            target.Handle);
                        Function.Call(Hash.SET_ENTITY_HEALTH, target.Handle,
                            Math.Max(0, health - 200));
                        Vector3 velocity = new Vector3(purpleDirection.X * 17f,
                            purpleDirection.Y * 17f, 6f);
                        TryMoveNativeActor(target.Handle, velocity, now);
                    }
                }
                catch (Exception) { failed++; }
            }
            return failed;
        }

        private void EmergencyReset()
        {
            infinityEnabled = false;
            redUntil = DateTime.MinValue;
            blueUntil = DateTime.MinValue;
            purpleUntil = DateTime.MinValue;
            voidUntil = DateTime.MinValue;
            nextInfinityScan = DateTime.MinValue;
            nextVoidScan = DateTime.MinValue;
            nextRedPulse = DateTime.MinValue;
            nextBluePulse = DateTime.MinValue;
            nextPurpleScan = DateTime.MinValue;
            nextCast = DateTime.MinValue;
            redReported = false;
            blueReported = false;
            voidReported = false;
            purpleReported = false;
            purpleHitHandles.Clear();
            ReleaseAll(voidFrozen, infinityFrozen);
            ReleaseAll(infinityFrozen, voidFrozen);
            ReleaseNativeFrozen(voidNativeFrozen, infinityNativeFrozen);
            ReleaseNativeFrozen(infinityNativeFrozen, voidNativeFrozen);
            physicsExemptUntil.Clear();
        }

        // Optional native button bridge. Without the injected dylib the
        // original keyboard bindings remain available and the mod still loads.
        private static class TouchBridge
        {
            private static bool unavailable;
            private static bool enabled;

            [DllImport("GojoTouchBridge", EntryPoint = "gojo_touch_consume")]
            private static extern uint NativeConsume();

            [DllImport("GojoTouchBridge", EntryPoint = "gojo_touch_set_enabled")]
            private static extern void NativeSetEnabled(int value);

            public static uint Consume()
            {
                if (unavailable) return 0;
                try { return NativeConsume(); }
                catch (DllNotFoundException) { unavailable = true; }
                catch (EntryPointNotFoundException) { unavailable = true; }
                catch (BadImageFormatException) { unavailable = true; }
                catch (Exception) { unavailable = true; }
                return 0;
            }

            public static void SetEnabled(bool next)
            {
                if (unavailable || next == enabled) return;
                try
                {
                    NativeSetEnabled(next ? 1 : 0);
                    enabled = next;
                }
                catch (DllNotFoundException) { unavailable = true; }
                catch (EntryPointNotFoundException) { unavailable = true; }
                catch (BadImageFormatException) { unavailable = true; }
                catch (Exception) { unavailable = true; }
            }
        }
    }
}

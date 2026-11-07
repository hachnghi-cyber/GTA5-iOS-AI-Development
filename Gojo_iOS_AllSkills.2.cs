// Gojo iOS five-ability test port, based on the user-provided Class1.cs.
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
                if (!infinityEnabled) ReleaseAll(infinityFrozen, voidFrozen);
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
                nextCast = now.AddMilliseconds(550);
                UI.ShowSubtitle("Reverse Red: blast away!");
            }
            else if (key == Keys.U)
            {
                // Touch input does not always expose a native GTA aim target.
                // Attract targets to a point in front of Gojo without aiming.
                blueCenter = player.Position + player.ForwardVector * 4f;
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
                            UI.ShowSubtitle("Void: " + voidFrozen.Count +
                                " entities frozen; automatic release");
                        }
                    }
                }
                else if (voidFrozen.Count > 0)
                {
                    ReleaseAll(voidFrozen, infinityFrozen);
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
                            UI.ShowSubtitle("Red: " + affected +
                                " targets, " + errors + " errors");
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
                    int hitErrors = HitPurple(player, impact, now);
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

            Entity[] near = World.GetNearbyEntities(center, radius);
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
            foreach (Entity entity in World.GetNearbyEntities(center, 35f))
            {
                try
                {
                    if (!IsValidTarget(entity, player)) continue;
                    Vector3 delta = entity.Position - center;
                    float length = delta.Length();
                    if (length < 1f) continue;
                    float speed = entity is Vehicle ? 22f : 15f;
                    Vector3 velocity = delta / length * speed;
                    velocity.Z += entity is Vehicle ? 2.0f : 3.5f;
                    if (TrySetVelocity(entity, velocity, now)) applied++;
                    else failed++;
                }
                catch (Exception) { failed++; }
                if (applied + failed >= 24) break;
            }
        }

        // Blue: pull nearby entities to a stable point slightly ahead of Gojo.
        // This deliberately works without GTA's PC-style aim target support.
        private void PullBlueWithVelocity(Ped player, Vector3 center,
            DateTime now, out int applied, out int failed)
        {
            applied = 0;
            failed = 0;
            foreach (Entity entity in World.GetNearbyEntities(player.Position, 35f))
            {
                try
                {
                    if (!IsValidTarget(entity, player)) continue;
                    Vector3 delta = center - entity.Position;
                    float distance = delta.Length();
                    if (distance < 5f) continue;
                    float speed = entity is Vehicle ? 16f : 14f;
                    Vector3 velocity = delta / distance * speed;
                    velocity.Z += entity is Vehicle ? 0.4f : 1.0f;
                    if (TrySetVelocity(entity, velocity, now)) applied++;
                    else failed++;
                }
                catch (Exception) { failed++; }
                if (applied + failed >= 24) break;
            }
        }

        // Purple: travelling forward attack. Each handle is affected only once
        // during a cast; never delete game entities, which broke some iOS builds.
        private int HitPurple(Ped player, Vector3 point, DateTime now)
        {
            int failed = 0;
            foreach (Entity entity in World.GetNearbyEntities(point, 9f))
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
            nextCast = DateTime.MinValue;
            redReported = false;
            blueReported = false;
            voidReported = false;
            purpleReported = false;
            purpleHitHandles.Clear();
            ReleaseAll(voidFrozen, infinityFrozen);
            ReleaseAll(infinityFrozen, voidFrozen);
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

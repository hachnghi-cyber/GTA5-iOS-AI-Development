// Gojo iOS test port, based on the user-provided Class1.cs.
// SHVDN v2 API: .2.cs makes the required API explicit.
// No System.Media, file I/O, DLL imports, or Windows desktop UI calls.
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
        private bool infinityEnabled;
        private DateTime nextInfinityScan = DateTime.MinValue;
        private DateTime redUntil = DateTime.MinValue;
        private DateTime blueUntil = DateTime.MinValue;
        private DateTime purpleUntil = DateTime.MinValue;
        private DateTime voidUntil = DateTime.MinValue;
        private DateTime nextVoidScan = DateTime.MinValue;
        private DateTime nextCast = DateTime.MinValue;
        private Vector3 blueCenter;
        private bool redFired;

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
                UI.ShowSubtitle(infinityEnabled ? "Infinity: ON" : "Infinity: OFF");
                return;
            }

            // Avoid stacking several expensive effects on the same frame.
            if (now < nextCast) return;

            if (key == Keys.J)
            {
                redUntil = now.AddMilliseconds(1200);
                redFired = false;
                nextCast = now.AddMilliseconds(500);
                UI.ShowSubtitle("Reverse Red!");
            }
            else if (key == Keys.U)
            {
                if (!Game.Player.IsAiming)
                {
                    UI.ShowSubtitle("Blue: aim at a target first");
                    return;
                }
                Entity target = Game.Player.GetTargetedEntity();
                if (!IsAliveEntity(target))
                {
                    UI.ShowSubtitle("Blue: no target");
                    return;
                }
                blueCenter = target.Position;
                blueUntil = now.AddMilliseconds(850);
                PullToTarget(player, blueCenter);
                nextCast = now.AddMilliseconds(450);
                UI.ShowSubtitle("Blue!");
            }
            else if (key == Keys.Y)
            {
                purpleHitHandles.Clear();
                purpleUntil = now.AddMilliseconds(1300);
                nextCast = now.AddMilliseconds(950);
                UI.ShowSubtitle("Hollow Purple!");
            }
            else if (key == Keys.I)
            {
                voidUntil = now.AddMilliseconds(3000);
                nextVoidScan = DateTime.MinValue;
                nextCast = now.AddMilliseconds(1000);
                UI.ShowSubtitle("Unlimited Void!");
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
                    UpdateFreezeArea(player, 12f, infinityFrozen, voidFrozen);
                    nextInfinityScan = now.AddMilliseconds(180);
                }

                if (now < voidUntil)
                {
                    if (now >= nextVoidScan)
                    {
                        UpdateFreezeArea(player, 28f, voidFrozen, infinityFrozen);
                        nextVoidScan = now.AddMilliseconds(250);
                    }
                }
                else if (voidFrozen.Count > 0)
                {
                    ReleaseAll(voidFrozen, infinityFrozen);
                }

                if (now < redUntil)
                {
                    World.DrawLightWithRange(player.Position, Color.Red, 45f, 14f);
                    if (!redFired)
                    {
                        PushAround(player, player.Position, 18f, 90f, false);
                        redFired = true;
                    }
                }

                if (now < blueUntil)
                {
                    World.DrawLightWithRange(blueCenter, Color.Blue, 30f, 7f);
                }

                if (now < purpleUntil)
                {
                    DateTime start = purpleUntil.AddMilliseconds(-1300);
                    double elapsed = (now - start).TotalMilliseconds;
                    Vector3 forward = player.ForwardVector;
                    Vector3 impact = player.Position + forward * 12f;
                    World.DrawLightWithRange(impact, Color.Purple, 55f, 10f);
                    if (elapsed > 430)
                    {
                        HitPurple(player, impact);
                    }
                }
                else if (purpleHitHandles.Count > 0)
                {
                    purpleHitHandles.Clear();
                }
            }
            catch (Exception)
            {
                // Keep entity positions recoverable after an unsupported native.
                EmergencyReset();
                UI.ShowSubtitle("Gojo: script error (reset)");
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

        private void UpdateFreezeArea(Ped player, float radius,
            List<Entity> current, List<Entity> other)
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
                if (!IsValidTarget(entity, player) ||
                    (entity.Position - center).Length() > radius)
                {
                    if (!other.Contains(entity)) entity.FreezePosition = false;
                    current.RemoveAt(i);
                }
            }

            Entity[] near = World.GetNearbyEntities(center, radius);
            foreach (Entity entity in near)
            {
                if (!IsValidTarget(entity, player) || current.Contains(entity)) continue;
                // Track each entity independently in the two overlapping effects.
                // Do not unfreeze it until the last Gojo effect is finished.
                if (!other.Contains(entity)) entity.FreezePosition = true;
                current.Add(entity);
            }
        }

        private static void ReleaseAll(List<Entity> current, List<Entity> other)
        {
            foreach (Entity entity in current)
            {
                try
                {
                    if (IsAliveEntity(entity) && !other.Contains(entity))
                        entity.FreezePosition = false;
                }
                catch (Exception) { /* entity might have despawned */ }
            }
            current.Clear();
        }

        private static void PushAround(Ped player, Vector3 center, float radius,
            float strength, bool pull)
        {
            foreach (Entity entity in World.GetNearbyEntities(center, radius))
            {
                if (!IsValidTarget(entity, player)) continue;
                Vector3 delta = entity.Position - center;
                float length = delta.Length();
                if (length < 0.75f) continue;
                float direction = pull ? -1f : 1f;
                ApplyForce(entity, delta / length * (direction * strength));
            }
        }

        private static void ApplyForce(Entity entity, Vector3 force)
        {
            Function.Call(Hash.APPLY_FORCE_TO_ENTITY, entity.Handle, 1,
                force.X, force.Y, force.Z + 8f,
                0f, 0f, 0f, 0, false, false, true, false, true);
        }

        private static void PullToTarget(Ped player, Vector3 center)
        {
            PushAround(player, center, 22f, 55f, true);
        }

        private void HitPurple(Ped player, Vector3 point)
        {
            foreach (Entity entity in World.GetNearbyEntities(point, 8f))
            {
                if (!IsValidTarget(entity, player) ||
                    !purpleHitHandles.Add(entity.Handle)) continue;

                if (entity is Vehicle)
                {
                    // Do not delete vehicles: some iOS builds crash on deletion.
                    ((Vehicle)entity).Explode();
                }
                else if (entity is Ped)
                {
                    Ped victim = (Ped)entity;
                    victim.Health = Math.Max(0, victim.Health - 200);
                    Vector3 delta = victim.Position - point;
                    if (delta.Length() > 0.5f)
                        ApplyForce(victim, delta / delta.Length() * 110f);
                }
            }
        }

        private void EmergencyReset()
        {
            infinityEnabled = false;
            redUntil = DateTime.MinValue;
            blueUntil = DateTime.MinValue;
            purpleUntil = DateTime.MinValue;
            voidUntil = DateTime.MinValue;
            purpleHitHandles.Clear();
            ReleaseAll(voidFrozen, infinityFrozen);
            ReleaseAll(infinityFrozen, voidFrozen);
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

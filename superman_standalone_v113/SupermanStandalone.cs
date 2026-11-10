// Independent ScriptHookVDotNet 3 mod for GTA V iOS v11.3 (experimental).
// Does not contain or load TamedMods' Windows-only Superman.asi.
// Requires the port's ScriptHookV .NET runtime and its GTA API bridge.
using System;
using Keys = System.Windows.Forms.Keys;
using GTA;
using GTA.Math;
using GTA.Native;

namespace SupermanStandaloneMod
{
    public sealed class SupermanStandalone : Script
    {
        private const ulong HNetworkIsSessionActive = 0xD83C2B94E7508980UL;
        private const ulong HSetEntityHasGravity = 0x4A4722448F18EEF5UL;
        private const ulong HSetEntityVelocity = 0x1C99BB7B6E96D16FUL;
        private const ulong HDrawLine = 0x6B7256074AE34680UL;
        private const ulong HApplyForce = 0xC5F68BE9613E2D18UL;
        private const ulong HRequestWeaponAsset = 0x5443438F033E29C3UL;
        private const ulong HHasWeaponAssetLoaded = 0x36E353271F0E90EEUL;
        private const ulong HShootSingleBullet = 0x867654CBC7606F2CUL;
        private const uint WeaponPistol = 0x1B06D571U;

        private const float CruiseSpeed = 28.0f;
        private const float BoostSpeed = 48.0f;
        private const float VerticalSpeed = 11.0f;
        private const float ShockRadius = 11.0f;
        private const int MaxShockEntities = 24;

        private bool _enabled;
        private bool _flying;
        private int _gravityPed;
        private bool _previousJ;
        private bool _previousK;
        private bool _previousM;
        private int _lastShockMs = -3000;
        private int _lastHeatMs = -400;
        private bool _assetRequested;
        private bool _failed;

        public SupermanStandalone()
        {
            Interval = 0;
            Tick += OnTick;
            Aborted += OnAborted;
        }

        private static void Notify(string text)
        {
            GTA.UI.Screen.ShowSubtitle(text, 2300);
        }

        private static bool Down(Keys key)
        {
            return Game.IsKeyPressed(key);
        }

        private static bool ControlDown(Control control)
        {
            return Game.IsControlPressed(control);
        }

        private static bool Online()
        {
            return Function.Call<bool>((Hash)HNetworkIsSessionActive);
        }

        private void RestoreGravity()
        {
            if (_gravityPed != 0 && Function.Call<bool>(Hash.DOES_ENTITY_EXIST, _gravityPed))
                Function.Call((Hash)HSetEntityHasGravity, _gravityPed, true);
            _gravityPed = 0;
            _flying = false;
        }

        private void Stop()
        {
            RestoreGravity();
            _enabled = false;
        }

        private void OnAborted(object sender, EventArgs e)
        {
            try { Stop(); } catch { /* no native calls after runtime unload */ }
        }

        private void OnTick(object sender, EventArgs e)
        {
            if (_failed) return;
            try { TickSafe(); }
            catch (Exception ex)
            {
                try { Stop(); } catch { }
                _failed = true; // fail closed; avoid repeatedly crashing gameplay
                try { Console.WriteLine("[SupermanStandalone] " + ex); } catch { }
                try { Notify("Superman tam dung: " + ex.GetType().Name); } catch { }
            }
        }

        private void TickSafe()
        {
            bool j = Down(Keys.J), k = Down(Keys.K), m = Down(Keys.M);

            if (Online())
            {
                // Do not touch remote players, remote vehicles, or online game rules.
                if (_enabled || _flying) Stop();
                UpdateEdges(j, k, m);
                return;
            }

            Ped ped = Game.Player.Character;
            if (ped == null || !ped.Exists() || ped.IsDead)
            {
                if (_enabled || _flying) Stop();
                UpdateEdges(j, k, m);
                return;
            }

            if (j && !_previousJ)
            {
                _enabled = !_enabled;
                if (!_enabled) Stop();
                else { _assetRequested = false; Notify("Superman: BAT | K bay, L laser, M song"); }
            }

            if (!_enabled)
            {
                UpdateEdges(j, k, m);
                return;
            }

            if (_flying && _gravityPed != ped.Handle) RestoreGravity();
            if (k && !_previousK)
            {
                if (_flying) { RestoreGravity(); Notify("Superman: ha canh"); }
                else if (!ped.IsInVehicle())
                {
                    _flying = true;
                    _gravityPed = ped.Handle;
                    Function.Call((Hash)HSetEntityHasGravity, _gravityPed, false);
                    Notify("Superman: dang bay");
                }
            }

            if (ped.IsInVehicle() && _flying) RestoreGravity();
            if (_flying) Fly(ped);
            if (Down(Keys.L)) HeatVision(ped);
            if (m && !_previousM && Game.GameTime - _lastShockMs >= 2400)
            {
                _lastShockMs = Game.GameTime;
                Shockwave(ped);
            }
            UpdateEdges(j, k, m);
        }

        private void UpdateEdges(bool j, bool k, bool m)
        {
            _previousJ = j;
            _previousK = k;
            _previousM = m;
        }

        private static Vector3 Unit(Vector3 value)
        {
            float length = (float)Math.Sqrt(value.X * value.X + value.Y * value.Y + value.Z * value.Z);
            return length > 0.001f ? value / length : new Vector3(0f, 1f, 0f);
        }

        private void Fly(Ped ped)
        {
            Vector3 forward = Unit(GameplayCamera.Direction);
            Vector3 right = Unit(new Vector3(forward.Y, -forward.X, 0f));
            float forwards = (ControlDown(Control.MoveUpOnly) ? 1f : 0f)
                           - (ControlDown(Control.MoveDownOnly) ? 1f : 0f);
            float sideways = (ControlDown(Control.MoveRightOnly) ? 1f : 0f)
                           - (ControlDown(Control.MoveLeftOnly) ? 1f : 0f);
            float up = (ControlDown(Control.Jump) || Down(Keys.Space) ? 1f : 0f)
                     - (ControlDown(Control.Duck) ? 1f : 0f);
            Vector3 planar = forward * forwards + right * sideways;
            if (planar.Length() > 1f) planar = Unit(planar);
            float speed = Down(Keys.ShiftKey) ? BoostSpeed : CruiseSpeed;
            Vector3 velocity = planar * speed + new Vector3(0f, 0f, VerticalSpeed * up);
            Function.Call((Hash)HSetEntityVelocity, ped.Handle, velocity.X, velocity.Y, velocity.Z);
        }

        private void HeatVision(Ped ped)
        {
            Vector3 eye = ped.Position + new Vector3(0f, 0f, 1.6f);
            Vector3 target = GameplayCamera.Position + Unit(GameplayCamera.Direction) * 80f;
            Function.Call((Hash)HDrawLine, eye.X, eye.Y, eye.Z,
                target.X, target.Y, target.Z, 255, 28, 10, 235);
            Function.Call((Hash)HDrawLine, eye.X + 0.10f, eye.Y, eye.Z,
                target.X, target.Y, target.Z, 255, 186, 32, 175);

            if (Game.GameTime - _lastHeatMs < 220) return;
            _lastHeatMs = Game.GameTime;
            if (!_assetRequested)
            {
                Function.Call((Hash)HRequestWeaponAsset, WeaponPistol, 31, false);
                _assetRequested = true;
            }
            if (!Function.Call<bool>((Hash)HHasWeaponAssetLoaded, WeaponPistol)) return;
            Function.Call((Hash)HShootSingleBullet,
                eye.X, eye.Y, eye.Z, target.X, target.Y, target.Z,
                8, true, WeaponPistol, ped.Handle, false, true, 500f);
        }

        private static void ApplyShock(Entity entity, Vector3 origin)
        {
            if (entity == null || !entity.Exists()) return;
            Vector3 delta = entity.Position - origin;
            float distance = delta.Length();
            if (distance < 0.35f || distance > ShockRadius) return;
            Vector3 force = Unit(delta) * (18f * (1f - distance / ShockRadius)) + new Vector3(0, 0, 6f);
            Function.Call((Hash)HApplyForce, entity.Handle, 1,
                force.X, force.Y, force.Z, 0f, 0f, 0f, 0,
                false, true, true, false, true);
        }

        private static void Shockwave(Ped ped)
        {
            Vector3 center = ped.Position;
            Ped[] nearbyPeds = World.GetNearbyPeds(ped, ShockRadius);
            for (int i = 0; i < nearbyPeds.Length && i < MaxShockEntities; i++)
                if (nearbyPeds[i] != ped) ApplyShock(nearbyPeds[i], center);

            Vehicle[] nearbyVehicles = World.GetNearbyVehicles(center, ShockRadius);
            for (int i = 0; i < nearbyVehicles.Length && i < MaxShockEntities; i++)
                ApplyShock(nearbyVehicles[i], center);
        }
    }
}

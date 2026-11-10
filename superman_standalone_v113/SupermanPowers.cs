// Experimental clean-room powers inspired by Superman-style gameplay.
// Uses the game's own native API, not code or assets from Superman.asi.
// Each feature must be accepted on the target iOS ScriptHook bridge.
using System;
using System.Collections.Generic;
using Keys = System.Windows.Forms.Keys;
using GTA;
using GTA.Math;
using GTA.Native;

namespace SupermanStandaloneMod
{
    public sealed partial class SupermanStandalone
    {
        private enum BeamKind { HeatVision, PlasmaArc, SolarFlare, PulseCannon, CryoBeam }

        private readonly Dictionary<Keys, bool> _extraPressed = new Dictionary<Keys, bool>();
        private readonly Dictionary<int, int> _frozenUntil = new Dictionary<int, int>();
        private readonly Dictionary<int, int> _empUntil = new Dictionary<int, int>();
        private BeamKind _beam = BeamKind.HeatVision;
        private Vehicle _heldVehicle;
        private bool _bulletTime;
        private bool _thermalVision;
        private bool _combatMode;
        private bool _extrasInitialized;
        private bool _extrasFaulted;
        private bool _previousPlayerInvincible;
        private bool _appliedInvincibility;
        private bool _appliedRagdoll;
        private int _lastUltimate = -30000;
        private int _lastBeamSpecial = -3000;
        private int _lastBreath = -300;
        private int _lastCombat = -3000;
        private int _lastAimScanAt = -1000;
        private Entity _aimCache;

        private bool Pressed(Keys key)
        {
            bool now = Down(key);
            bool before;
            _extraPressed.TryGetValue(key, out before);
            _extraPressed[key] = now;
            return now && !before;
        }

        private static float Dot(Vector3 a, Vector3 b)
        {
            return a.X * b.X + a.Y * b.Y + a.Z * b.Z;
        }

        private static void Push(Entity e, Vector3 from, float strength, float vertical)
        {
            if (e == null || !e.Exists()) return;
            Vector3 away = Unit(e.Position - from);
            Vector3 force = away * strength + new Vector3(0, 0, vertical);
            Function.Call((Hash)HApplyForce, e.Handle, 1,
                force.X, force.Y, force.Z, 0f, 0f, 0f, 0,
                false, true, true, false, true);
        }

        // Camera-cone selection avoids native memory access and keeps the
        // cost bounded for iPhones. It is not a true raycast with occlusion.
        private Entity FindAimTarget(Ped player, float range, float radius)
        {
            // Keep the frequently-held R key from enumerating the entire
            // game world every render frame on lower-memory iPhones.
            int now = Game.GameTime;
            if (now - _lastAimScanAt < 65)
                return _aimCache != null && _aimCache.Exists() ? _aimCache : null;
            _lastAimScanAt = now;
            Vector3 origin = GameplayCamera.Position;
            Vector3 direction = Unit(GameplayCamera.Direction);
            float nearest = range;
            Entity selected = null;

            Ped[] peds = NearbyPeds(player, range);
            for (int i = 0; i < peds.Length && i < 48; i++)
            {
                Ped p = peds[i];
                if (p == null || p == player || !p.Exists() || p.IsDead) continue;
                Vector3 delta = p.Position + new Vector3(0, 0, 1f) - origin;
                float along = Dot(delta, direction);
                if (along <= 2f || along >= nearest) continue;
                if ((delta - direction * along).Length() > radius) continue;
                nearest = along;
                selected = p;
            }

            Vehicle[] vehicles = NearbyVehicles(player.Position, range);
            for (int i = 0; i < vehicles.Length && i < 48; i++)
            {
                Vehicle v = vehicles[i];
                if (v == null || !v.Exists()) continue;
                Vector3 delta = v.Position - origin;
                float along = Dot(delta, direction);
                if (along <= 2f || along >= nearest) continue;
                if ((delta - direction * along).Length() > radius + 1.4f) continue;
                nearest = along;
                selected = v;
            }
            _aimCache = selected;
            return selected;
        }

        private void SetBeam(BeamKind beam)
        {
            if (_beam == beam) return;
            _beam = beam;
            Notify("Superman | Tia: " + beam);
        }

        private void NextBeam()
        {
            SetBeam((BeamKind)(((int)_beam + 1) % 5));
        }

        private void DrawBeam(Ped player, Vector3 target, int r, int g, int b)
        {
            Vector3 eye = player.Position + new Vector3(0f, 0f, 1.6f);
            Function.Call((Hash)HDrawLine, eye.X, eye.Y, eye.Z,
                target.X, target.Y, target.Z, r, g, b, 245);
            Function.Call((Hash)HDrawLine, eye.X + .10f, eye.Y, eye.Z,
                target.X, target.Y, target.Z, r, g, b, 170);
        }

        private void FireSelectedBeam(Ped player)
        {
            if (_beam == BeamKind.HeatVision)
            {
                HeatVision(player); // Baseline tested API surface, now using original R key.
                return;
            }

            Entity targetEntity = FindAimTarget(player, 85f, 2.2f);
            Vector3 target = targetEntity != null
                ? targetEntity.Position + new Vector3(0, 0, 1.0f)
                : GameplayCamera.Position + Unit(GameplayCamera.Direction) * 85f;

            switch (_beam)
            {
                case BeamKind.PlasmaArc: DrawBeam(player, target, 72, 180, 255); break;
                case BeamKind.SolarFlare: DrawBeam(player, target, 255, 231, 95); break;
                case BeamKind.PulseCannon: DrawBeam(player, target, 255, 115, 35); break;
                case BeamKind.CryoBeam: DrawBeam(player, target, 112, 230, 255); break;
            }

            int now = Game.GameTime;
            if (now - _lastBeamSpecial < 370) return;
            _lastBeamSpecial = now;

            if (_beam == BeamKind.PlasmaArc)
            {
                if (targetEntity != null) Push(targetEntity, player.Position, 17f, 2f);
                Ped[] chain = NearbyPeds(player, 88f);
                int hits = 0;
                for (int i = 0; i < chain.Length && i < 40 && hits < 3; i++)
                {
                    Ped p = chain[i];
                    if (p == null || p == player || !p.Exists() || p.IsDead) continue;
                    if ((p.Position - target).Length() > 8f) continue;
                    Function.Call((Hash)HDrawLine, target.X, target.Y, target.Z,
                        p.Position.X, p.Position.Y, p.Position.Z + 1f,
                        90, 210, 255, 240);
                    Push(p, target, 12f, 2f);
                    hits++;
                }
            }
            else if (_beam == BeamKind.SolarFlare)
                Emp(target, 13f, now + 3500);
            else if (_beam == BeamKind.PulseCannon)
                Function.Call(Hash.ADD_EXPLOSION, target.X, target.Y, target.Z,
                    18, 0.65f, true, false, 0f);
            else if (_beam == BeamKind.CryoBeam && targetEntity != null)
            {
                Function.Call(Hash.FREEZE_ENTITY_POSITION, targetEntity.Handle, true);
                _frozenUntil[targetEntity.Handle] = now + 3500;
            }
        }

        private void Emp(Vector3 position, float radius, int until)
        {
            Vehicle[] vehicles = NearbyVehicles(position, radius);
            for (int i = 0; i < vehicles.Length && i < 30; i++)
            {
                Vehicle v = vehicles[i];
                if (v == null || !v.Exists()) continue;
                Function.Call(Hash.SET_VEHICLE_UNDRIVEABLE, v.Handle, true);
                _empUntil[v.Handle] = until;
            }
        }

        private void ExpireEffects()
        {
            int now = Game.GameTime;
            List<int> expired = new List<int>();
            foreach (KeyValuePair<int, int> entry in _frozenUntil)
            {
                if (entry.Value > now) continue;
                if (Function.Call<bool>(Hash.DOES_ENTITY_EXIST, entry.Key))
                    Function.Call(Hash.FREEZE_ENTITY_POSITION, entry.Key, false);
                expired.Add(entry.Key);
            }
            foreach (int handle in expired) _frozenUntil.Remove(handle);
            expired.Clear();
            foreach (KeyValuePair<int, int> entry in _empUntil)
            {
                if (entry.Value > now) continue;
                if (Function.Call<bool>(Hash.DOES_ENTITY_EXIST, entry.Key))
                    Function.Call(Hash.SET_VEHICLE_UNDRIVEABLE, entry.Key, false);
                expired.Add(entry.Key);
            }
            foreach (int handle in expired) _empUntil.Remove(handle);
        }

        private void LiftOrThrow(Ped player)
        {
            if (_heldVehicle != null)
            {
                if (_heldVehicle.Exists())
                {
                    Vector3 direction = Unit(GameplayCamera.Direction) * 60f;
                    Function.Call((Hash)HSetEntityHasGravity, _heldVehicle.Handle, true);
                    Function.Call((Hash)HSetEntityVelocity, _heldVehicle.Handle,
                        direction.X, direction.Y, direction.Z + 8f);
                }
                _heldVehicle = null;
                Notify("Superman: nem xe");
                return;
            }

            int currentVehicle = Function.Call<int>(Hash.GET_VEHICLE_PED_IS_IN, player.Handle, false);
            Vehicle[] vehicles = NearbyVehicles(player.Position, 5.5f);
            float distance = 5.5f;
            for (int i = 0; i < vehicles.Length && i < 16; i++)
            {
                Vehicle v = vehicles[i];
                if (v == null || !v.Exists() || v.Handle == currentVehicle) continue;
                float d = (v.Position - player.Position).Length();
                if (d < distance) { distance = d; _heldVehicle = v; }
            }
            if (_heldVehicle != null)
            {
                Function.Call((Hash)HSetEntityHasGravity, _heldVehicle.Handle, false);
                Notify("Superman: nhac xe | F nem");
            }
        }

        private void MaintainLift(Ped player)
        {
            if (_heldVehicle == null) return;
            if (!_heldVehicle.Exists() || (player.Position - _heldVehicle.Position).Length() > 22f)
            {
                if (_heldVehicle.Exists())
                    Function.Call((Hash)HSetEntityHasGravity, _heldVehicle.Handle, true);
                _heldVehicle = null;
                return;
            }
            Vector3 desired = player.Position + Unit(GameplayCamera.Direction) * 3.5f
                            + new Vector3(0, 0, 2.0f);
            Vector3 velocity = (desired - _heldVehicle.Position) * 5.0f;
            if (velocity.Length() > 18f) velocity = Unit(velocity) * 18f;
            Function.Call((Hash)HSetEntityVelocity, _heldVehicle.Handle,
                velocity.X, velocity.Y, velocity.Z);
        }

        private void Gust(Ped player, float radius, float strength, bool tornado)
        {
            Vector3 origin = player.Position;
            Vector3 front = Unit(GameplayCamera.Direction);
            int currentVehicle = Function.Call<int>(Hash.GET_VEHICLE_PED_IS_IN, player.Handle, false);
            Ped[] peds = NearbyPeds(player, radius);
            for (int i = 0; i < peds.Length && i < 30; i++)
            {
                Ped p = peds[i];
                if (p == null || p == player || !p.Exists() || p.IsDead) continue;
                if (!tornado && Dot(Unit(p.Position - origin), front) < 0.45f) continue;
                if (tornado) Push(p, origin, strength, 22f);
                else Push(p, origin, strength, 4f);
            }
            Vehicle[] vehicles = NearbyVehicles(origin, radius);
            for (int i = 0; i < vehicles.Length && i < 20; i++)
            {
                Vehicle v = vehicles[i];
                if (v == null || !v.Exists() || v.Handle == currentVehicle) continue;
                if (!tornado && Dot(Unit(v.Position - origin), front) < 0.45f) continue;
                Push(v, origin, strength * 1.4f, tornado ? 16f : 3f);
            }
        }

        private void ResetExtraPowers()
        {
            // Restore independent resources even when one iOS native is
            // unsupported. Otherwise a failed unfreeze can strand time scale.
            foreach (int handle in _frozenUntil.Keys)
            {
                int savedHandle = handle;
                TryRestore(() =>
                {
                    if (Function.Call<bool>(Hash.DOES_ENTITY_EXIST, savedHandle))
                        Function.Call(Hash.FREEZE_ENTITY_POSITION, savedHandle, false);
                });
            }
            foreach (int handle in _empUntil.Keys)
            {
                int savedHandle = handle;
                TryRestore(() =>
                {
                    if (Function.Call<bool>(Hash.DOES_ENTITY_EXIST, savedHandle))
                        Function.Call(Hash.SET_VEHICLE_UNDRIVEABLE, savedHandle, false);
                });
            }
            TryRestore(() =>
            {
                if (_heldVehicle != null && _heldVehicle.Exists())
                    Function.Call((Hash)HSetEntityHasGravity, _heldVehicle.Handle, true);
            });
            if (_bulletTime) TryRestore(() => Function.Call(Hash.SET_TIME_SCALE, 1.0f));
            if (_thermalVision) TryRestore(() => Function.Call(Hash.SET_SEETHROUGH, false));
            if (_appliedInvincibility)
                TryRestore(() => Function.Call(Hash.SET_PLAYER_INVINCIBLE,
                    Game.Player.Handle, _previousPlayerInvincible));
            if (_appliedRagdoll)
                TryRestore(() => Function.Call(Hash.SET_PED_CAN_RAGDOLL,
                    Game.Player.Character.Handle, true));
            _frozenUntil.Clear(); _empUntil.Clear(); _extraPressed.Clear();
            _heldVehicle = null;
            _aimCache = null;
            _lastAimScanAt = -1000;
            _extrasInitialized = false;
            _appliedInvincibility = false;
            _appliedRagdoll = false;
            _bulletTime = false;
            _thermalVision = false;
            _combatMode = false;
            _extrasFaulted = false;
        }

        private static void TryRestore(Action operation)
        {
            try { operation(); }
            catch (Exception ex)
            {
                try { Console.WriteLine("[SupermanExtra cleanup] " + ex); } catch { }
            }
        }

        private void TickExtraPowers(Ped player)
        {
            if (!_extrasInitialized)
            {
                _extrasInitialized = true;
                // Do not disable the entire mod if the iOS bridge lacks one
                // optional native. Restoration only runs for applied flags.
                try
                {
                    _previousPlayerInvincible = Function.Call<bool>(Hash.GET_PLAYER_INVINCIBLE, Game.Player.Handle);
                    Function.Call(Hash.SET_PLAYER_INVINCIBLE, Game.Player.Handle, true);
                    _appliedInvincibility = true;
                }
                catch (Exception ex) { Console.WriteLine("[Superman] invincible unsupported: " + ex); }
                try
                {
                    Function.Call(Hash.SET_PED_CAN_RAGDOLL, player.Handle, false);
                    _appliedRagdoll = true;
                }
                catch (Exception ex) { Console.WriteLine("[Superman] ragdoll unsupported: " + ex); }
            }
            ExpireEffects();
            MaintainLift(player);

            if (Pressed(Keys.NumPad1)) SetBeam(BeamKind.HeatVision);
            if (Pressed(Keys.NumPad2)) SetBeam(BeamKind.PlasmaArc);
            if (Pressed(Keys.NumPad3)) SetBeam(BeamKind.SolarFlare);
            if (Pressed(Keys.NumPad4)) SetBeam(BeamKind.PulseCannon);
            if (Pressed(Keys.NumPad5)) SetBeam(BeamKind.CryoBeam);

            if (Pressed(Keys.F) && !player.IsInVehicle()) LiftOrThrow(player);
            if (Pressed(Keys.Y))
            {
                _bulletTime = !_bulletTime;
                Function.Call(Hash.SET_TIME_SCALE, _bulletTime ? 0.32f : 1f);
                Notify(_bulletTime ? "Superman: bullet time" : "Superman: toc do thuong");
            }
            if (Pressed(Keys.N))
            {
                _thermalVision = !_thermalVision;
                Function.Call(Hash.SET_SEETHROUGH, _thermalVision);
                Notify(_thermalVision ? "Superman: nhin nhiet" : "Superman: nhin thuong");
            }
            if (Pressed(Keys.K))
            {
                _combatMode = !_combatMode;
                Notify(_combatMode ? "Superman: combat BAT" : "Superman: combat TAT");
            }
            if (Pressed(Keys.P))
                Notify("Super hearing: " + NearbyPeds(player, 120f).Length + " NPC tim duoc (xap xi)");

            int now = Game.GameTime;
            if (Down(Keys.H) && now - _lastBreath >= 320)
            {
                _lastBreath = now;
                Gust(player, 24f, 24f, false);
            }
            if (Down(Keys.T) && now - _lastBreath >= 320)
            {
                _lastBreath = now;
                Gust(player, 14f, 18f, true);
            }
            if (Down(Keys.G) && now - _lastBreath >= 420)
            {
                _lastBreath = now;
                Entity target = FindAimTarget(player, 17f, 5f);
                if (target != null)
                {
                    Function.Call(Hash.FREEZE_ENTITY_POSITION, target.Handle, true);
                    _frozenUntil[target.Handle] = now + 2900;
                }
            }
            if (Pressed(Keys.F8) && now - _lastUltimate >= 25000)
            {
                _lastUltimate = now;
                Vector3 center = player.Position;
                Function.Call(Hash.ADD_EXPLOSION, center.X, center.Y, center.Z,
                    19, 0.8f, true, false, 0.5f);
                Emp(center, 38f, now + 9000);
                Gust(player, 38f, 45f, true);
                Notify("Superman: Solar Flare!");
            }

            // These are simplified physics moves; synced takedown animations,
            // target AI and ragdoll choreography remain separate port work.
            bool combatU = Pressed(Keys.U);
            bool combatZ = Pressed(Keys.Z);
            bool combatL = Pressed(Keys.L);
            if (_combatMode && now - _lastCombat >= 1100 &&
                (combatU || combatZ || combatL))
            {
                Entity target = FindAimTarget(player, 14f, 2.3f);
                if (target != null)
                {
                    _lastCombat = now;
                    Push(target, player.Position, 38f, 13f);
                }
            }
        }
    }
}

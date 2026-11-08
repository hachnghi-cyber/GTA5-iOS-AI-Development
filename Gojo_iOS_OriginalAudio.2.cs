// Gojo iOS five powers + GTA native VFX + ORIGINAL MOD WAV audio, iOS TEST.
// Preserve NativeTargetFix physics and native entity lookup unchanged.
// SHVDN v2 API: .2.cs makes the required API explicit.
// On iOS, effects use RAGE DRAW_MARKER and optional stock particle assets.
// Audio uses the mod's original WAV files via AudioToolbox/CoreFoundation;
// this never substitutes GTA's standard frontend sound effects.
// Unsupported graphics/audio natives are isolated: gameplay must keep working.
// System.Windows.Forms is used only for SHVDN's KeyDown/Keys contract.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
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
        private DateTime redStarted = DateTime.MinValue;
        private DateTime nextInfinityFx = DateTime.MinValue;
        private DateTime nextRedFx = DateTime.MinValue;
        private DateTime nextBlueFx = DateTime.MinValue;
        private DateTime nextPurpleFx = DateTime.MinValue;
        private DateTime nextVoidFx = DateTime.MinValue;
        private DateTime nextParticleProbe = DateTime.MinValue;
        private bool coreParticleReady;
        private int particleEmissionCount;
        private int particleErrorCount;

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
                nextInfinityFx = DateTime.MinValue;
                UI.ShowSubtitle(infinityEnabled ? "Infinity: ON" : "Infinity: OFF");
                if (infinityEnabled) PlayOriginalSound("MU_short.wav");
                return;
            }

            // Avoid stacking several expensive effects on the same frame.
            if (now < nextCast) return;

            if (key == Keys.J)
            {
                redStarted = now;
                redUntil = now.AddMilliseconds(850);
                nextRedPulse = DateTime.MinValue;
                nextRedFx = DateTime.MinValue;
                redReported = false;
                lastRedSpeed = -1f;
                nextCast = now.AddMilliseconds(550);
                UI.ShowSubtitle("Reverse Red: blast away!");
                PlayOriginalSound("RR.wav");
            }
            else if (key == Keys.U)
            {
                // Touch input does not always expose a native GTA aim target.
                // Attract targets to a point in front of Gojo without aiming.
                blueCenter = player.Position + player.ForwardVector * 0.75f;
                blueUntil = now.AddMilliseconds(1100);
                nextBluePulse = DateTime.MinValue;
                nextBlueFx = DateTime.MinValue;
                blueReported = false;
                nextCast = now.AddMilliseconds(600);
                UI.ShowSubtitle("Lapse Blue: attract!");
                PlayOriginalSound("Bl.wav");
            }
            else if (key == Keys.Y)
            {
                purpleHitHandles.Clear();
                purpleOrigin = player.Position;
                purpleDirection = player.ForwardVector;
                purpleStarted = now;
                purpleUntil = now.AddMilliseconds(1200);
                nextPurpleScan = DateTime.MinValue;
                nextPurpleFx = DateTime.MinValue;
                purpleReported = false;
                nextCast = now.AddMilliseconds(1000);
                UI.ShowSubtitle("Hollow Purple: forward wave!");
                PlayOriginalSound("HP.wav");
            }
            else if (key == Keys.I)
            {
                voidUntil = now.AddMilliseconds(4500);
                nextVoidScan = DateTime.MinValue;
                nextVoidFx = DateTime.MinValue;
                voidReported = false;
                nextCast = now.AddMilliseconds(1000);
                UI.ShowSubtitle("Unlimited Void: 4.5 seconds!");
                PlayOriginalSound("UV.wav");
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
                // Issue at most one stock-particle asset request per two
                // seconds; no synchronous load or wait on the game thread.
                UpdateParticleAvailability(now);
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
                if (infinityEnabled)
                {
                    RenderInfinity(player, now);
                }

                if (now < voidUntil)
                {
                    RenderVoid(player, now);
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
                    RenderRed(player, now);
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
                    RenderBlue(blueCenter, now);
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
                    RenderPurple(impact, now);
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

        private void PlayOriginalSound(string fileName)
        {
            // No substitute stock GTA sound: only WAVs from the supplied
            // 2022 Gojo mod are accepted. Failure must never abort a power.
            if (!ModWavPlayer.TryPlay(fileName))
                UI.ShowSubtitle("Gojo WAV " + fileName + ": " +
                    ModWavPlayer.LastError);
        }

        // SHVDN's Windows System.Media.SoundPlayer cannot play on iOS.
        // AudioServices plays short (<= 30-second) PCM WAV sounds via Apple's
        // C ABI. MU.wav lasts ~50.6 s, so this build uses a 5-second excerpt
        // MU_short.wav generated from the user's ORIGINAL sound file.
        private static class ModWavPlayer
        {
            private const uint CfUtf8 = 0x08000100u;
            private const int PosixPath = 0;
            private static readonly Dictionary<string, uint> SoundIds =
                new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);
            private static bool apiUnavailable;
            public static string LastError { get; private set; }

            [DllImport("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
                EntryPoint = "CFStringCreateWithCString")]
            private static extern IntPtr CfStringCreate(IntPtr allocator,
                [MarshalAs(UnmanagedType.LPUTF8Str)] string text, uint encoding);

            [DllImport("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
                EntryPoint = "CFURLCreateWithFileSystemPath")]
            private static extern IntPtr CfUrlCreate(IntPtr allocator,
                IntPtr cfString, int pathStyle,
                [MarshalAs(UnmanagedType.I1)] bool isDirectory);

            [DllImport("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
                EntryPoint = "CFRelease")]
            private static extern void CfRelease(IntPtr handle);

            [DllImport("/System/Library/Frameworks/AudioToolbox.framework/AudioToolbox",
                EntryPoint = "AudioServicesCreateSystemSoundID")]
            private static extern int AudioCreateSound(IntPtr fileUrl,
                out uint soundId);

            [DllImport("/System/Library/Frameworks/AudioToolbox.framework/AudioToolbox",
                EntryPoint = "AudioServicesPlaySystemSound")]
            private static extern void AudioPlaySound(uint soundId);

            public static bool TryPlay(string fileName)
            {
                if (apiUnavailable)
                {
                    LastError = "iOS audio API unavailable";
                    return false;
                }

                string path = FindModAudio(fileName);
                if (path == null)
                {
                    LastError = "file not found in scripts/gojomusic";
                    return false;
                }

                try
                {
                    uint soundId;
                    if (!SoundIds.TryGetValue(path, out soundId))
                    {
                        IntPtr cfPath = IntPtr.Zero;
                        IntPtr cfUrl = IntPtr.Zero;
                        try
                        {
                            cfPath = CfStringCreate(IntPtr.Zero,
                                path, CfUtf8);
                            if (cfPath == IntPtr.Zero)
                            {
                                LastError = "CFString failed";
                                return false;
                            }
                            cfUrl = CfUrlCreate(IntPtr.Zero, cfPath,
                                PosixPath, false);
                            if (cfUrl == IntPtr.Zero)
                            {
                                LastError = "CFURL failed";
                                return false;
                            }
                            int status = AudioCreateSound(cfUrl,
                                out soundId);
                            if (status != 0 || soundId == 0)
                            {
                                LastError = "AudioToolbox status " + status;
                                return false;
                            }
                            SoundIds.Add(path, soundId);
                        }
                        finally
                        {
                            if (cfUrl != IntPtr.Zero) CfRelease(cfUrl);
                            if (cfPath != IntPtr.Zero) CfRelease(cfPath);
                        }
                    }

                    AudioPlaySound(soundId);
                    LastError = "OK";
                    return true;
                }
                catch (DllNotFoundException)
                {
                    apiUnavailable = true;
                    LastError = "AudioToolbox DLL not found";
                }
                catch (EntryPointNotFoundException)
                {
                    apiUnavailable = true;
                    LastError = "AudioToolbox symbol not found";
                }
                catch (BadImageFormatException)
                {
                    apiUnavailable = true;
                    LastError = "AudioToolbox ABI unsupported";
                }
                catch (Exception ex)
                {
                    LastError = ex.GetType().Name;
                }
                return false;
            }

            private static string FindModAudio(string fileName)
            {
                // Only fixed built-in filenames; never scan arbitrary paths.
                var roots = new List<string>();
                try { roots.Add(Directory.GetCurrentDirectory()); }
                catch (Exception) { }
                try { roots.Add(AppDomain.CurrentDomain.BaseDirectory); }
                catch (Exception) { }
                try
                {
                    string assembly = typeof(GojoPowers).Assembly.Location;
                    if (!String.IsNullOrEmpty(assembly))
                        roots.Add(Path.GetDirectoryName(assembly));
                }
                catch (Exception) { }
                try
                {
                    roots.Add(Environment.GetFolderPath(
                        Environment.SpecialFolder.Personal));
                }
                catch (Exception) { }

                foreach (string root in roots)
                {
                    if (String.IsNullOrEmpty(root)) continue;
                    string[] candidates = {
                        Path.Combine(root, "scripts", "gojomusic", fileName),
                        Path.Combine(root, "gojomusic", fileName),
                        Path.Combine(root, "Documents", "scripts", "gojomusic", fileName),
                        Path.Combine(root, "mods", "scripts", "gojomusic", fileName)
                    };
                    foreach (string candidate in candidates)
                    {
                        try
                        {
                            if (File.Exists(candidate))
                                return Path.GetFullPath(candidate);
                        }
                        catch (Exception) { }
                    }
                }
                return null;
            }
        }

        // The stock 'core' dictionary normally exists in GTA V. Only one
        // lightweight particle dictionary is requested; if the iOS port
        // doesn't stream it, colored DRAW_MARKER effects remain visible.
        private void UpdateParticleAvailability(DateTime now)
        {
            if (coreParticleReady || now < nextParticleProbe) return;
            nextParticleProbe = now.AddSeconds(2);
            try
            {
                coreParticleReady = Function.Call<bool>(
                    Hash.HAS_NAMED_PTFX_ASSET_LOADED, "core");
                if (!coreParticleReady)
                    Function.Call(Hash.REQUEST_NAMED_PTFX_ASSET, "core");
            }
            catch (Exception)
            {
                coreParticleReady = false;
            }
        }

        // Marker 28 is GTA V's debug sphere. A fallback cylinder marker
        // provides a colored ground shockwave. Native color channels are
        // integers, unlike System.Drawing.Color; alpha is capped deliberately.
        private static void DrawOrb(Vector3 position, float size,
            int red, int green, int blue, int alpha)
        {
            DrawNativeMarker(28, position, size, size, size,
                red, green, blue, alpha);
        }

        private static void DrawGroundPulse(Vector3 position, float radius,
            int red, int green, int blue, int alpha)
        {
            DrawNativeMarker(1,
                new Vector3(position.X, position.Y, position.Z - 0.88f),
                radius * 2f, radius * 2f, 0.05f,
                red, green, blue, alpha);
        }

        private static void DrawNativeMarker(int markerType,
            Vector3 position, float sizeX, float sizeY, float sizeZ,
            int red, int green, int blue, int alpha)
        {
            try
            {
                Function.Call(Hash.DRAW_MARKER,
                    markerType, position.X, position.Y, position.Z,
                    0f, 0f, 0f, 0f, 0f, 0f,
                    sizeX, sizeY, sizeZ,
                    red, green, blue, alpha,
                    false, false, 2, false, "", "", false);
            }
            catch (Exception) { /* unsupported marker never blocks physics */ }
        }

        // Non-looped sparks are rate-limited to protect iPhones already
        // running GTA V around 30 FPS. Reuse one stock FX rather than adding
        // a native resource bundle or external sound files to the IPA.
        private void EmitEnergy(Vector3 position, float scale,
            float red, float green, float blue)
        {
            if (!coreParticleReady) return;
            try
            {
                Function.Call(Hash._SET_PTFX_ASSET_NEXT_CALL, "core");
                try
                {
                    Function.Call(Hash.SET_PARTICLE_FX_NON_LOOPED_COLOUR,
                        red, green, blue);
                }
                catch (Exception) { /* tinted particles are optional */ }
                bool spawned = Function.Call<bool>(
                    Hash.START_PARTICLE_FX_NON_LOOPED_AT_COORD,
                    "ent_sht_electrical_box",
                    position.X, position.Y, position.Z,
                    0f, 0f, 0f, scale,
                    false, false, false);
                if (spawned) particleEmissionCount++;
                else particleErrorCount++;
            }
            catch (Exception) { particleErrorCount++; }
        }

        private void RenderInfinity(Ped player, DateTime now)
        {
            Vector3 center = player.Position;
            double phase = (now.TimeOfDay.TotalMilliseconds % 2000.0) / 2000.0;
            float pulse = 0.88f + (float)(0.12 * Math.Sin(phase * Math.PI * 2));
            DrawOrb(new Vector3(center.X, center.Y, center.Z + 0.9f),
                3.2f * pulse, 60, 210, 255, 52);
            DrawGroundPulse(center, 3.0f * pulse, 75, 205, 255, 38);
            if (now >= nextInfinityFx)
            {
                nextInfinityFx = now.AddMilliseconds(1300);
                EmitEnergy(new Vector3(center.X, center.Y, center.Z + 1.0f),
                    0.35f, 0.3f, 0.8f, 1f);
            }
        }

        private void RenderRed(Ped player, DateTime now)
        {
            Vector3 center = player.Position;
            Vector3 orb = center + player.ForwardVector * 1.7f;
            orb.Z += 1.1f;
            float progress = (float)Math.Max(0.0,
                Math.Min(1.0, (now - redStarted).TotalMilliseconds / 850.0));
            DrawOrb(orb, 1.35f + progress * 0.8f,
                255, 35, 42, 205);
            DrawGroundPulse(center, 1.2f + progress * 8.0f,
                255, 45, 45, 90);
            if (now >= nextRedFx)
            {
                nextRedFx = now.AddMilliseconds(280);
                EmitEnergy(orb, 1.15f, 1f, 0.08f, 0.08f);
            }
            try { World.DrawLightWithRange(orb, Color.Red, 25f, 9f); }
            catch (Exception) { /* optional extra light */ }
        }

        private void RenderBlue(Vector3 center, DateTime now)
        {
            Vector3 orb = new Vector3(center.X, center.Y, center.Z + 1.0f);
            double phase = now.TimeOfDay.TotalMilliseconds / 200.0;
            DrawOrb(orb, 1.85f, 25, 75, 255, 195);
            Vector3 satellite = orb + new Vector3(
                (float)Math.Cos(phase) * 1.0f,
                (float)Math.Sin(phase) * 1.0f, 0f);
            DrawOrb(satellite, 0.55f, 60, 205, 255, 130);
            DrawGroundPulse(center, 2.0f, 25, 80, 255, 45);
            if (now >= nextBlueFx)
            {
                nextBlueFx = now.AddMilliseconds(340);
                EmitEnergy(orb, 0.7f, 0.12f, 0.3f, 1f);
            }
            try { World.DrawLightWithRange(orb, Color.Blue, 28f, 9f); }
            catch (Exception) { /* optional extra light */ }
        }

        private void RenderPurple(Vector3 impact, DateTime now)
        {
            Vector3 orb = new Vector3(impact.X, impact.Y, impact.Z + 1.1f);
            DrawOrb(orb, 2.25f, 170, 55, 255, 200);
            Vector3 trail = orb - purpleDirection * 3.0f;
            DrawOrb(trail, 1.2f, 125, 70, 255, 92);
            if (now >= nextPurpleFx)
            {
                nextPurpleFx = now.AddMilliseconds(320);
                EmitEnergy(orb, 1.2f, 0.65f, 0.15f, 1f);
            }
            try { World.DrawLightWithRange(orb, Color.Purple, 35f, 12f); }
            catch (Exception) { /* optional extra light */ }
        }

        private void RenderVoid(Ped player, DateTime now)
        {
            Vector3 center = player.Position;
            double phase = now.TimeOfDay.TotalMilliseconds / 420.0;
            float size = 6.0f + (float)Math.Sin(phase) * 0.5f;
            DrawGroundPulse(center, size, 105, 90, 255, 48);
            DrawOrb(new Vector3(center.X, center.Y, center.Z + 0.8f),
                4.4f, 85, 75, 230, 48);
            if (now >= nextVoidFx)
            {
                nextVoidFx = now.AddMilliseconds(850);
                EmitEnergy(new Vector3(center.X, center.Y, center.Z + 1.2f),
                    0.65f, 0.3f, 0.25f, 1f);
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
            nextInfinityFx = DateTime.MinValue;
            nextRedFx = DateTime.MinValue;
            nextBlueFx = DateTime.MinValue;
            nextPurpleFx = DateTime.MinValue;
            nextVoidFx = DateTime.MinValue;
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

// Independent iOS camera implementation. Not a derivative of ikt's Windows ASI.
// Targets ScriptHookVDotNet 2 API as hosted by GTA V iOS v11.1/posthook 3.4.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Windows.Forms;
using GTA;
using GTA.Math;
using GTA.Native;

namespace DynamicVehicleFirstPersonIOS
{
    public sealed class VehicleCockpitCamera : Script
    {
        private sealed class CameraPreset
        {
            public string Name;
            public float Fov;
            public float ForwardOffset;
            public float HeightOffset;
            public float LateralOffset;
            public float YawOffset;
            public float PitchOffset;
            public float RollOffset;
            public float HorizonLock;
            public float Inertia;
            public float Responsiveness;
            public float Shake;
            public bool Dof;
            public int LookMode;

            public CameraPreset(string name, float fov, float forward, float height,
                float horizon, float inertia, float responsiveness)
            {
                Name = name;
                Fov = fov;
                ForwardOffset = forward;
                HeightOffset = height;
                HorizonLock = horizon;
                Inertia = inertia;
                Responsiveness = responsiveness;
            }

            public CameraPreset Copy()
            {
                return (CameraPreset)MemberwiseClone();
            }
        }

        private static readonly CameraPreset[] Presets = {
            new CameraPreset("Can bang", 100f, 0.10f, -0.08f, 0.85f, 0.45f, 16f),
            new CameraPreset("Goc rong", 115f, 0.03f, -0.10f, 0.92f, 0.60f, 14f),
            new CameraPreset("The thao", 92f, 0.14f, -0.05f, 0.55f, 1.00f, 18f)
        };

        private Camera _camera;
        private readonly Dictionary<string, CameraPreset[]> _savedProfiles =
            new Dictionary<string, CameraPreset[]>(StringComparer.OrdinalIgnoreCase);
        private CameraPreset[] _activePresets = Presets;
        private string _vehicleKey = "";
        private string _configPath;
        private bool _menuOpen;
        private int _menuIndex;
        private DateTime _menuLastDrawUtc = DateTime.MinValue;
        private bool _pauseRecenter;
        private bool _dofFailed;
        private bool _dofActive;
        private bool _firstPersonFlagFailed;
        private int _vehicleHandle;
        private int _selectedVehicleHandle;
        private bool _enabled = true;
        private bool _forceFirstPerson;
        private int _preset;
        private int _errorCount;
        private DateTime _lastTickUtc = DateTime.MinValue;
        private DateTime _lastLookUtc = DateTime.MinValue;
        private Vector3 _previousVelocity;
        // The inertial translation is in VEHICLE-LOCAL coordinates. The camera
        // itself is attached to the vehicle by the engine's native transform;
        // smoothing a world position, even every script tick, can lag metres
        // behind when the physics/render phases run at different times.
        private Vector3 _smoothedRelativeOffset;
        private bool _vehicleCameraAttached;
        private Vector3 _vehicleSeatLocalOrigin;
        private Vector3 _lastAttachedLocalOffset;
        private float _yawLook;
        private float _pitchLook;
        private float _currentRoll;
        private float _currentPitch;
        private float _lastYaw;

        public VehicleCockpitCamera()
        {
            Interval = 0;
            Tick += OnTick;
            KeyDown += OnKeyDown;
            Aborted += OnAborted;
            LoadProfiles();
        }

        private void OnKeyDown(object sender, KeyEventArgs args)
        {
            switch (args.KeyCode)
            {
                case Keys.F6:
                    ToggleEnabled();
                    break;
                case Keys.F7:
                    _forceFirstPerson = !_forceFirstPerson;
                    if (!_forceFirstPerson) ReleaseCamera();
                    Announce(_forceFirstPerson ? "Camera thu cong: BAT" : "Camera thu cong: TAT");
                    break;
                case Keys.F8:
                    NextPreset();
                    break;
                case Keys.F10:
                    _menuOpen = !_menuOpen;
                    break;
                case Keys.F11:
                    CycleLookMode();
                    break;
                case Keys.N:
                    NextPreset();
                    break;
                case Keys.B:
                    _pauseRecenter = !_pauseRecenter;
                    Announce(_pauseRecenter ? "Recenter: DUNG" : "Recenter: BAT");
                    break;
                case Keys.F9:
                    _enabled = false;
                    _forceFirstPerson = false;
                    _menuOpen = false;
                    ReleaseCamera();
                    Announce("Camera da tat / reset");
                    break;
            }
        }

        private void OnAborted(object sender, EventArgs e)
        {
            ReleaseCamera();
        }

        private void OnTick(object sender, EventArgs e)
        {
            try
            {
                // Never replace the game's first-person view outside driving.
                if (Game.IsLoading || Game.IsPaused ||
                    Function.Call<bool>(Hash.IS_SCREEN_FADED_OUT) ||
                    Function.Call<bool>(Hash.IS_CUTSCENE_ACTIVE))
                {
                    ReleaseCamera();
                    return;
                }

                ReadGamepadShortcuts();

                Ped player = Game.Player.Character;
                Vehicle car = player == null ? null : player.CurrentVehicle;
                if (!_enabled || player == null || !player.Exists() || player.IsDead ||
                    car == null || !car.Exists() || IsOnline())
                {
                    ReleaseCamera();
                    return;
                }
                if (!Function.Call<bool>(Hash.IS_PED_SITTING_IN_ANY_VEHICLE, player.Handle))
                {
                    ReleaseCamera();
                    return;
                }

                if (Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 0, 25))
                {
                    // Yield to the vanilla aim camera to preserve drive-by aiming.
                    ReleaseCamera();
                    return;
                }

                if (_selectedVehicleHandle != car.Handle)
                {
                    SelectVehicleSettings(car);
                    _selectedVehicleHandle = car.Handle;
                }

                // The native first-person mode is 4 on GTA V vehicle cameras.
                // An explicit F7 / gamepad override is available if touch controls
                // do not expose that view mode on a particular iOS device.
                int followMode = Function.Call<int>(Hash.GET_FOLLOW_VEHICLE_CAM_VIEW_MODE);
                if (!_forceFirstPerson && followMode != 4)
                {
                    ReleaseCamera();
                    return;
                }

                int currentHandle = car.Handle;
                if (_camera == null)
                {
                    // GET_RENDERING_CAM is implemented by this port; do not
                    // assume IS_SCRIPTED_CAM_RENDERING is present in v11.1.
                    if (Function.Call<int>(Hash.GET_RENDERING_CAM) > 0) return;
                    StartCamera(player, car);
                }
                else if (_vehicleHandle != currentHandle)
                {
                    ReleaseCamera();
                    StartCamera(player, car);
                }

                // A different script (for example Menyoo's Freecam) owns the camera.
                // Do not turn it off when yielding our camera.
                if (_camera == null) return;
                int rendering = Function.Call<int>(Hash.GET_RENDERING_CAM);
                if (rendering > 0 && rendering != _camera.Handle)
                {
                    ReleaseCamera();
                    return;
                }

                UpdateCamera(player, car);
                _errorCount = 0;
            }
            catch (Exception)
            {
                ReleaseCamera();
                if (++_errorCount >= 3)
                {
                    _enabled = false;
                    _forceFirstPerson = false;
                    Announce("Camera: loi API, da tu dong tat. F6 de thu lai.");
                }
            }
        }

        private static bool IsOnline()
        {
            // By default the prototype is disabled in network sessions. This
            // avoids interfering with online camera ownership and other scripts.
            try { return Function.Call<bool>(Hash.NETWORK_IS_SESSION_STARTED); }
            catch (Exception) { return true; }
        }

        private void ReadGamepadShortcuts()
        {
            if (_menuOpen)
            {
                ReadMenuInput();
                return;
            }
            // Avoid RB + D-pad LEFT, already used for Menyoo on this port.
            // LB combinations are deliberately separate from the Menyoo key.
            if (!Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 2, 205)) return;
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 203))
            {
                _menuOpen = true;
                _menuIndex = 0;
                return;
            }
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 190)) ToggleEnabled();
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 188)) NextPreset();
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 189))
            {
                _forceFirstPerson = !_forceFirstPerson;
                _enabled = true;
                if (!_forceFirstPerson) ReleaseCamera();
                Announce(_forceFirstPerson ? "Camera thu cong: BAT" : "Camera thu cong: TAT");
            }
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 187))
            {
                _enabled = false;
                _forceFirstPerson = false;
                ReleaseCamera();
                Announce("Camera iOS: reset an toan");
            }
        }

        private void ToggleEnabled()
        {
            _enabled = !_enabled;
            if (!_enabled) ReleaseCamera();
            Announce(_enabled ? "Camera iOS: BAT" : "Camera iOS: TAT");
        }

        private void NextPreset()
        {
            _preset = (_preset + 1) % _activePresets.Length;
            if (_camera != null) _camera.FieldOfView = _activePresets[_preset].Fov;
            Announce("Camera: " + _activePresets[_preset].Name + " / FOV " + _activePresets[_preset].Fov);
        }

        private void CycleLookMode()
        {
            MakeEditable();
            CameraPreset p = _activePresets[_preset];
            p.LookMode = (p.LookMode + 1) % 3;
            Announce("Look mode: " + new[] { "Direct", "Classic", "Directional" }[p.LookMode]);
        }

        private void SelectVehicleSettings(Vehicle car)
        {
            string key = GetVehicleKey(car);
            if (key == _vehicleKey) return;
            _vehicleKey = key;
            CameraPreset[] saved;
            string modelKey = car.Model.Hash.ToString("X8", CultureInfo.InvariantCulture);
            if (_savedProfiles.TryGetValue(key, out saved) ||
                _savedProfiles.TryGetValue(modelKey, out saved))
                _activePresets = saved;
            else
                _activePresets = Presets;
            _preset = Math.Min(_preset, _activePresets.Length - 1);
        }

        private static string GetVehicleKey(Vehicle car)
        {
            string model = car.Model.Hash.ToString("X8", CultureInfo.InvariantCulture);
            try
            {
                string plate = Function.Call<string>(Hash.GET_VEHICLE_NUMBER_PLATE_TEXT, car.Handle);
                if (!string.IsNullOrWhiteSpace(plate))
                {
                    plate = plate.Trim().ToUpperInvariant().Replace("|", "");
                    return model + "@" + plate;
                }
            }
            catch (Exception) { /* model-only fallback */ }
            return model;
        }

        private void MakeEditable()
        {
            // Never mutate the global defaults or another vehicle's presets.
            CameraPreset[] found;
            if (_savedProfiles.TryGetValue(_vehicleKey, out found))
            {
                _activePresets = found;
                return;
            }
            CameraPreset[] clone = new CameraPreset[_activePresets.Length];
            for (int i = 0; i < clone.Length; i++) clone[i] = _activePresets[i].Copy();
            _activePresets = clone;
            if (!string.IsNullOrEmpty(_vehicleKey)) _savedProfiles[_vehicleKey] = clone;
        }

        private const int MenuItemCount = 20;

        private void ReadMenuInput()
        {
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 202))
            {
                _menuOpen = false;
                Announce("Camera: dong menu");
                return;
            }
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 187))
                _menuIndex = (_menuIndex + 1) % MenuItemCount;
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 188))
                _menuIndex = (_menuIndex + MenuItemCount - 1) % MenuItemCount;

            int change = 0;
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 189)) change = -1;
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 190)) change = 1;
            if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 201)) change = 1;
            if (change != 0) ChangeMenuOption(change);

            DateTime now = DateTime.UtcNow;
            if ((now - _menuLastDrawUtc).TotalMilliseconds >= 350)
            {
                _menuLastDrawUtc = now;
                CameraPreset p = _activePresets[_preset];
                Announce("FPV iOS [" + (_menuIndex + 1) + "/" + MenuItemCount + "] ~n~" +
                    MenuOptionLabel(p) + " ~n~Dpad: di chuyen/chinh | A: chon | B: thoat");
            }
        }

        private string MenuOptionLabel(CameraPreset p)
        {
            switch (_menuIndex)
            {
                case 0: return "Bat camera: " + (_enabled ? "CO" : "KHONG");
                case 1: return "Ep goc 1: " + (_forceFirstPerson ? "CO" : "KHONG");
                case 2: return "Vi tri camera: " + (_preset + 1) + "/" + _activePresets.Length;
                case 3: return "FOV: " + p.Fov.ToString("0", CultureInfo.InvariantCulture);
                case 4: return "Tien/lui (m): " + Format(p.ForwardOffset);
                case 5: return "Cao/thap (m): " + Format(p.HeightOffset);
                case 6: return "Trai/phai (m): " + Format(p.LateralOffset);
                case 7: return "Horizon lock: " + Format(p.HorizonLock);
                case 8: return "Do quan tinh: " + Format(p.Inertia);
                case 9: return "Rung nhe: " + p.Shake.ToString("0.000", CultureInfo.InvariantCulture);
                case 10: return "Kieu nhin: " + new[] { "Direct", "Classic", "Directional" }[p.LookMode];
                case 11: return "Depth of field: " + (p.Dof ? "BAT" : "TAT");
                case 12: return "Lech Yaw: " + Format(p.YawOffset);
                case 13: return "Lech Pitch: " + Format(p.PitchOffset);
                case 14: return "Lech Roll: " + Format(p.RollOffset);
                case 15: return "Sao chep camera (max 10)";
                case 16: return "Xoa camera hien tai";
                case 17: return "Dung re-center: " + (_pauseRecenter ? "CO" : "KHONG");
                case 18: return "Luu config cho xe";
                default: return "Khoi phuc mac dinh cho xe";
            }
        }

        private static string Format(float value)
        {
            return value.ToString("0.00", CultureInfo.InvariantCulture);
        }

        private void ChangeMenuOption(int step)
        {
            if (_menuIndex == 0) { ToggleEnabled(); return; }
            if (_menuIndex == 1) { _forceFirstPerson = !_forceFirstPerson; return; }
            if (_menuIndex == 2)
            {
                _preset = (_preset + step + _activePresets.Length) % _activePresets.Length;
                if (_camera != null) _camera.FieldOfView = _activePresets[_preset].Fov;
                return;
            }
            if (_menuIndex == 17) { _pauseRecenter = !_pauseRecenter; return; }
            if (_menuIndex == 18) { SaveProfiles(); return; }
            if (_menuIndex == 19)
            {
                _savedProfiles.Remove(_vehicleKey);
                _activePresets = Presets;
                _preset = 0;
                SaveProfiles();
                return;
            }
            if (_menuIndex == 16)
            {
                if (_activePresets.Length <= 1) return;
                MakeEditable();
                var next = new List<CameraPreset>(_activePresets);
                next.RemoveAt(_preset);
                _activePresets = next.ToArray();
                _savedProfiles[_vehicleKey] = _activePresets;
                _preset = Math.Min(_preset, _activePresets.Length - 1);
                return;
            }
            if (_menuIndex == 15)
            {
                if (_activePresets.Length >= 10) { Announce("Gioi han 10 camera"); return; }
                MakeEditable();
                var next = new List<CameraPreset>(_activePresets);
                CameraPreset copy = _activePresets[_preset].Copy();
                copy.Name = "Camera " + (next.Count + 1);
                next.Insert(_preset + 1, copy);
                _activePresets = next.ToArray();
                _savedProfiles[_vehicleKey] = _activePresets;
                _preset++;
                return;
            }

            MakeEditable();
            CameraPreset p = _activePresets[_preset];
            switch (_menuIndex)
            {
                case 3: p.Fov = Clamp(p.Fov + step * 5f, 50f, 130f); break;
                case 4: p.ForwardOffset = Clamp(p.ForwardOffset + step * 0.025f, -0.6f, 0.8f); break;
                case 5: p.HeightOffset = Clamp(p.HeightOffset + step * 0.025f, -0.5f, 0.5f); break;
                case 6: p.LateralOffset = Clamp(p.LateralOffset + step * 0.025f, -0.35f, 0.35f); break;
                case 7: p.HorizonLock = Clamp(p.HorizonLock + step * 0.1f, 0f, 1f); break;
                case 8: p.Inertia = Clamp(p.Inertia + step * 0.1f, 0f, 2f); break;
                case 9: p.Shake = Clamp(p.Shake + step * 0.002f, 0f, 0.05f); break;
                case 10: p.LookMode = (p.LookMode + step + 3) % 3; break;
                case 11: p.Dof = !p.Dof; break;
                case 12: p.YawOffset = Clamp(p.YawOffset + step, -40f, 40f); break;
                case 13: p.PitchOffset = Clamp(p.PitchOffset + step, -35f, 35f); break;
                case 14: p.RollOffset = Clamp(p.RollOffset + step, -35f, 35f); break;
            }
            if (_camera != null) _camera.FieldOfView = p.Fov;
        }

        private void UpdateDof(float speedKph)
        {
            try
            {
                float speedBlend = Clamp((speedKph - 40f) / 120f, 0f, 1f);
                Function.Call(Hash.SET_CAM_USE_SHALLOW_DOF_MODE, _camera.Handle, true);
                _camera.NearDepthOfField = 0.10f + 0.40f * speedBlend;
                _camera.FarDepthOfField = 200f - 120f * speedBlend;
                _camera.DepthOfFieldStrength = 0.07f + 0.38f * speedBlend;
                _dofActive = true;
            }
            catch (Exception)
            {
                _dofFailed = true;
                StopDof();
                Announce("iOS khong ho tro DoF; da tu tat hieu ung");
            }
        }

        private void StopDof()
        {
            if (_camera != null)
            {
                try
                {
                    _camera.DepthOfFieldStrength = 0f;
                    Function.Call(Hash.SET_CAM_USE_SHALLOW_DOF_MODE, _camera.Handle, false);
                }
                catch (Exception) { /* optional graphics feature */ }
            }
            _dofActive = false;
        }

        private string[] ConfigPaths()
        {
            string besideScript = null;
            try
            {
                string folder = Path.GetDirectoryName(Filename);
                if (!string.IsNullOrEmpty(folder))
                    besideScript = Path.Combine(folder, "DFPV_iOS.ini");
            }
            catch (Exception) { }
            return new[] {
                _configPath, besideScript,
                Path.Combine("mods", "scripthook", "scripts", "DFPV_iOS.ini"),
                Path.Combine("scripts", "DFPV_iOS.ini"),
                "DFPV_iOS.ini"
            };
        }

        private void LoadProfiles()
        {
            // Only relative paths: the port remaps game/ScriptHook file access.
            foreach (string path in ConfigPaths())
            {
                try
                {
                    if (string.IsNullOrEmpty(path) || !File.Exists(path) ||
                        new FileInfo(path).Length > 131072) continue;
                    foreach (string line in File.ReadAllLines(path))
                    {
                        if (line.StartsWith("#", StringComparison.Ordinal) ||
                            string.IsNullOrWhiteSpace(line)) continue;
                        string[] fields = line.Split('|');
                        if (fields.Length != 17 || fields[0].Length > 40) continue;
                        int slot;
                        if (!int.TryParse(fields[1], out slot) || slot < 0 || slot >= 10) continue;
                        CameraPreset preset;
                        if (!TryParsePreset(fields, out preset)) continue;
                        CameraPreset[] list;
                        if (!_savedProfiles.TryGetValue(fields[0], out list))
                        {
                            list = new CameraPreset[10];
                            _savedProfiles.Add(fields[0], list);
                        }
                        list[slot] = preset;
                    }
                    // Reject gaps to prevent a null profile reaching a camera tick.
                    var keys = new List<string>(_savedProfiles.Keys);
                    foreach (string key in keys)
                    {
                        CameraPreset[] list = _savedProfiles[key];
                        var compact = new List<CameraPreset>();
                        foreach (CameraPreset entry in list)
                            if (entry != null) compact.Add(entry);
                        if (compact.Count == 0) _savedProfiles.Remove(key);
                        else _savedProfiles[key] = compact.ToArray();
                    }
                    _configPath = path;
                    return;
                }
                catch (Exception) { /* optional file: fall back to defaults */ }
            }
        }

        private static bool TryParsePreset(string[] f, out CameraPreset p)
        {
            p = null;
            var values = new float[12];
            for (int i = 0; i < values.Length; i++)
                if (!float.TryParse(f[i + 3], NumberStyles.Float, CultureInfo.InvariantCulture, out values[i]) ||
                    float.IsNaN(values[i]) || float.IsInfinity(values[i])) return false;
            int lookMode;
            if (!int.TryParse(f[15], out lookMode)) return false;
            p = new CameraPreset(f[2].Replace("~", ""), Clamp(values[0], 50f, 130f),
                Clamp(values[1], -0.6f, 0.8f), Clamp(values[2], -0.5f, 0.5f),
                Clamp(values[6], 0f, 1f), Clamp(values[7], 0f, 2f), Clamp(values[8], 4f, 35f));
            p.LateralOffset = Clamp(values[3], -0.35f, 0.35f);
            p.YawOffset = Clamp(values[4], -40f, 40f);
            p.PitchOffset = Clamp(values[5], -35f, 35f);
            p.RollOffset = Clamp(values[9], -35f, 35f);
            p.Shake = Clamp(values[10], 0f, 0.05f);
            p.LookMode = Math.Max(0, Math.Min(lookMode, 2));
            p.Dof = f[16] == "1";
            return true;
        }

        private void SaveProfiles()
        {
            var lines = new List<string> { "# DFPV iOS 2 - Model@plate | slot | name | numeric values..." };
            foreach (KeyValuePair<string, CameraPreset[]> pair in _savedProfiles)
            {
                for (int i = 0; i < pair.Value.Length && i < 10; i++)
                {
                    CameraPreset p = pair.Value[i];
                    string[] fields = {
                        pair.Key, i.ToString(CultureInfo.InvariantCulture), p.Name.Replace("|", ""),
                        Format(p.Fov), Format(p.ForwardOffset), Format(p.HeightOffset),
                        Format(p.LateralOffset), Format(p.YawOffset), Format(p.PitchOffset),
                        Format(p.HorizonLock), Format(p.Inertia), Format(p.Responsiveness),
                        Format(p.RollOffset), p.Shake.ToString("0.0000", CultureInfo.InvariantCulture), "0",
                        p.LookMode.ToString(CultureInfo.InvariantCulture), p.Dof ? "1" : "0"
                    };
                    lines.Add(string.Join("|", fields));
                }
            }
            foreach (string path in ConfigPaths())
            {
                if (string.IsNullOrEmpty(path)) continue;
                try
                {
                    string folder = Path.GetDirectoryName(path);
                    if (!string.IsNullOrEmpty(folder) && !Directory.Exists(folder)) continue;
                    File.WriteAllLines(path, lines.ToArray());
                    _configPath = path;
                    Announce("Da luu config: " + path);
                    return;
                }
                catch (Exception) { /* try another mapped path */ }
            }
            Announce("Khong the luu config; du lieu con trong RAM");
        }

        private void StartCamera(Ped player, Vehicle car)
        {
            CameraPreset p = _activePresets[_preset];
            Vector3 pos = SafeHeadPosition(player, car, p);
            _camera = World.CreateCamera(pos, new Vector3(0f, 0f, car.Heading), p.Fov);
            if (_camera == null) throw new InvalidOperationException("CREATE_CAM failed");
            _camera.NearClip = 0.045f;
            _camera.IsActive = true;
            World.RenderingCamera = _camera;
            // Calibrate eye position ONCE while entering the vehicle camera.
            // Never recalculate seat position from an animated head bone while
            // accelerating: on iOS that bone can be a frame behind the car.
            _vehicleCameraAttached = false;
            try
            {
                Vector3 localEye = Function.Call<Vector3>(Hash.GET_OFFSET_FROM_ENTITY_GIVEN_WORLD_COORDS,
                    car.Handle, pos.X, pos.Y, pos.Z);
                if (IsFiniteVector(localEye) && localEye.Length() > 0.05f &&
                    localEye.Length() < 15f)
                {
                    _camera.AttachTo(car, localEye);
                    _vehicleSeatLocalOrigin = localEye -
                        new Vector3(p.LateralOffset, p.ForwardOffset, p.HeightOffset);
                    _lastAttachedLocalOffset = localEye;
                    _vehicleCameraAttached = true;
                }
            }
            catch (Exception)
            {
                // Keep a safe R3 world-coordinate fallback if an iOS port
                // does not implement the native attachment API.
                try { Function.Call(Hash.DETACH_CAM, _camera.Handle); }
                catch (Exception) { }
            }
            Announce(_vehicleCameraAttached ? "DFPV R4: bam camera vao xe" :
                "DFPV R4: attach loi, dung camera du phong");
            // Vehicle cabin context may improve interior acoustic/rendering flags.
            // Failing this optional call must not disable the camera itself.
            // SHVDN v2's Hash enum omits this native. The stable GTA V native
            // hash works with Function.Call even when the enum name is absent.
            try { Function.Call((Hash)0xA2767257A320FC82UL, _camera.Handle, true); }
            catch (Exception) { }
            _dofActive = false;
            _vehicleHandle = car.Handle;
            _smoothedRelativeOffset = new Vector3(0f, 0f, 0f);
            _previousVelocity = car.Velocity;
            _yawLook = 0f;
            _pitchLook = 0f;
            _currentPitch = 0f;
            _currentRoll = 0f;
            _lastYaw = car.Heading;
            _lastTickUtc = DateTime.UtcNow;
            _lastLookUtc = _lastTickUtc;
        }

        private void UpdateCamera(Ped player, Vehicle car)
        {
            DateTime now = DateTime.UtcNow;
            float dt = (float)(now - _lastTickUtc).TotalSeconds;
            dt = Clamp(dt, 0.001f, 0.08f);
            _lastTickUtc = now;
            CameraPreset p = _activePresets[_preset];

            float stickX = Clamp(Function.Call<float>(Hash.GET_CONTROL_NORMAL, 0, 1), -1f, 1f);
            float stickY = Clamp(Function.Call<float>(Hash.GET_CONTROL_NORMAL, 0, 2), -1f, 1f);
            if (Math.Abs(stickX) > 0.03f || Math.Abs(stickY) > 0.03f)
            {
                if (p.LookMode == 0) // Direct: analog magnitude maps to view angle.
                {
                    _yawLook = Clamp(-stickX * 145f, -145f, 145f);
                    _pitchLook = Clamp(stickY * 48f, -38f, 48f);
                }
                else if (p.LookMode == 1) // Classic: analog controls turn speed.
                {
                    _yawLook = Clamp(_yawLook - stickX * 160f * dt, -145f, 145f);
                    _pitchLook = Clamp(_pitchLook + stickY * 110f * dt, -38f, 48f);
                }
                else // Directional: stick points camera towards a direction.
                {
                    _yawLook = Clamp((float)(Math.Atan2(-stickX, -stickY) * 180.0 / Math.PI), -170f, 170f);
                    _pitchLook = 0f;
                }
                _lastLookUtc = now;
            }
            else if (!_pauseRecenter && (now - _lastLookUtc).TotalMilliseconds > 1100)
            {
                float recenter = SmoothFactor(1.8f, dt);
                _yawLook += (0f - _yawLook) * recenter;
                _pitchLook += (0f - _pitchLook) * recenter;
            }

            bool lookBack = Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 0, 79);
            float targetLookYaw = lookBack ? 170f : _yawLook;

            Vector3 velocity = car.Velocity;
            Vector3 accel = (velocity - _previousVelocity) * (1f / dt);
            _previousVelocity = velocity;
            float heading = car.Heading * (float)Math.PI / 180f;
            float rightAcceleration = accel.X * (float)Math.Cos(heading) +
                accel.Y * (float)Math.Sin(heading);
            float forwardAcceleration = -accel.X * (float)Math.Sin(heading) +
                accel.Y * (float)Math.Cos(heading);
            // Bound physical reactions to avoid camera jumps from collisions,
            // sudden spawns, low frame rates, and network interpolation.
            rightAcceleration = Clamp(rightAcceleration, -16f, 16f);
            forwardAcceleration = Clamp(forwardAcceleration, -16f, 16f);

            Vector3 rotation = car.Rotation;
            float targetRoll = rotation.Y * (1f - p.HorizonLock) -
                p.Inertia * rightAcceleration * 0.23f;
            float targetPitch = rotation.X * (1f - p.HorizonLock) +
                p.Inertia * forwardAcceleration * 0.12f;
            float smooth = SmoothFactor(p.Responsiveness, dt);
            _currentRoll += (Clamp(targetRoll, -15f, 15f) - _currentRoll) * smooth;
            _currentPitch += (Clamp(targetPitch, -12f, 12f) - _currentPitch) * smooth;

            // Filter only centimetre-scale local movements. The engine owns
            // the large position changes from driving and car rotation.
            float lateralShift = -rightAcceleration * p.Inertia * 0.0015f;
            float longitudinalShift = -forwardAcceleration * p.Inertia * 0.0013f;
            // Subtle bounded vehicle vibration, independent of frame rate.
            float kph = velocity.Length() * 3.6f;
            float amplitude = Clamp((kph - 70f) / 120f, 0f, 1f) * p.Shake;
            Vector3 desiredLocalMotion = new Vector3(lateralShift, longitudinalShift,
                -Clamp(accel.Z, -12f, 12f) * p.Inertia * 0.001f +
                (float)Math.Sin(now.Ticks / 10000000.0 * 23.0) * amplitude);
            _smoothedRelativeOffset +=
                (desiredLocalMotion - _smoothedRelativeOffset) * smooth;

            float targetYaw = WrapAngle(car.Heading + targetLookYaw + p.YawOffset);
            _lastYaw = WrapAngle(_lastYaw + WrapAngle(targetYaw - _lastYaw) * smooth);
            if (_vehicleCameraAttached)
            {
                // Only change the native attachment offset for cabin-position
                // settings and small inertia, NEVER for the car's world travel.
                Vector3 desiredLocal = _vehicleSeatLocalOrigin +
                    new Vector3(p.LateralOffset, p.ForwardOffset, p.HeightOffset) +
                    _smoothedRelativeOffset;
                if ((desiredLocal - _lastAttachedLocalOffset).Length() > 0.002f)
                {
                    try
                    {
                        _camera.AttachTo(car, desiredLocal);
                        _lastAttachedLocalOffset = desiredLocal;
                    }
                    catch (Exception)
                    {
                        _vehicleCameraAttached = false;
                        try { Function.Call(Hash.DETACH_CAM, _camera.Handle); }
                        catch (Exception) { }
                        Announce("DFPV R4: attach loi, da chuyen camera du phong");
                    }
                }
            }
            if (!_vehicleCameraAttached)
            {
                // Explicit fallback uses R3's no-smoothing head tracking.
                Vector3 fallback = SafeHeadPosition(player, car, p);
                fallback.X += (float)Math.Cos(heading) * _smoothedRelativeOffset.X -
                    (float)Math.Sin(heading) * _smoothedRelativeOffset.Y;
                fallback.Y += (float)Math.Sin(heading) * _smoothedRelativeOffset.X +
                    (float)Math.Cos(heading) * _smoothedRelativeOffset.Y;
                fallback.Z += _smoothedRelativeOffset.Z;
                _camera.Position = fallback;
            }
            _camera.Rotation = new Vector3(_currentPitch + _pitchLook + p.PitchOffset,
                _currentRoll + p.RollOffset, _lastYaw);
            if (p.Dof && !_dofFailed) UpdateDof(kph);
            else if (_dofActive) StopDof();
            // Inform the game of the cockpit camera context if supported.
            // Do not make camera rendering depend on this optional native.
            if (!_firstPersonFlagFailed)
            {
                // Keep the cockpit/first-person context without relying on a
                // symbol missing from the older SHVDN v2 Hash enum.
                try { Function.Call((Hash)0x469F2ECDEC046337UL, true); }
                catch (Exception) { _firstPersonFlagFailed = true; }
            }
        }

        private static Vector3 SafeHeadPosition(Ped player, Vehicle car, CameraPreset preset)
        {
            // Head bone follows left/right driver's seat and works on bikes.
            // Moving slightly ahead reduces clipping without changing ped parts.
            Vector3 head = Function.Call<Vector3>(Hash.GET_PED_BONE_COORDS,
                player.Handle, 31086, 0f, 0.17f, 0f);
            Vector3 playerPos = player.Position;
            float delta = (head - playerPos).Length();
            if (delta < 0.15f || delta > 2.2f ||
                float.IsNaN(head.X) || float.IsNaN(head.Y) || float.IsNaN(head.Z) ||
                float.IsInfinity(head.X) || float.IsInfinity(head.Y) || float.IsInfinity(head.Z))
            {
                head = playerPos + new Vector3(0f, 0f, 0.53f);
            }

            float heading = car.Heading * (float)Math.PI / 180f;
            head.X -= (float)Math.Sin(heading) * preset.ForwardOffset;
            head.Y += (float)Math.Cos(heading) * preset.ForwardOffset;
            head.X += (float)Math.Cos(heading) * preset.LateralOffset;
            head.Y += (float)Math.Sin(heading) * preset.LateralOffset;
            // A modest global eye-level correction for low vehicle cabins.
            // The regular HeightOffset slider still adjusts around this base.
            head.Z += 0.14f + preset.HeightOffset;
            return head;
        }

        private void ReleaseCamera()
        {
            if (_camera != null)
            {
                if (_dofActive) StopDof();
                try
                {
                    int rendering = Function.Call<int>(Hash.GET_RENDERING_CAM);
                    if (rendering == _camera.Handle)
                        World.RenderingCamera = null;
                }
                catch (Exception) { /* cleanup continues */ }

                if (_vehicleCameraAttached)
                {
                    try { Function.Call(Hash.DETACH_CAM, _camera.Handle); }
                    catch (Exception) { }
                }
                try { _camera.IsActive = false; }
                catch (Exception) { }
                try { _camera.Destroy(); }
                catch (Exception) { }
                _camera = null;
            }
            _vehicleCameraAttached = false;
            _vehicleHandle = 0;
            _lastTickUtc = DateTime.MinValue;
        }

        private static bool IsFiniteVector(Vector3 value)
        {
            return !float.IsNaN(value.X) && !float.IsNaN(value.Y) &&
                !float.IsNaN(value.Z) && !float.IsInfinity(value.X) &&
                !float.IsInfinity(value.Y) && !float.IsInfinity(value.Z);
        }

        private static float SmoothFactor(float responsiveness, float dt)
        {
            return Clamp(1f - (float)Math.Exp(-responsiveness * dt), 0f, 1f);
        }

        private static float Clamp(float value, float min, float max)
        {
            if (float.IsNaN(value) || float.IsInfinity(value))
                value = 0f;
            return Math.Max(min, Math.Min(value, max));
        }

        private static float WrapAngle(float value)
        {
            if (float.IsNaN(value) || float.IsInfinity(value)) return 0f;
            value %= 360f;
            while (value > 180f) value -= 360f;
            while (value < -180f) value += 360f;
            return value;
        }

        private static void Announce(string message)
        {
            try { UI.ShowSubtitle(message); }
            catch (Exception) { }
        }
    }
}

// Clean, independent ScriptHookVDotNet2 implementation for GTA V iOS v11.1.
// Recreated from the user's gameplay reference: not the Windows x86 .asi code.
using System;
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
        private sealed class Profile
        {
            public float Fov, Forward, Height, Side, Pitch, Yaw, Roll, NearClip;

            public Profile(float fov, float forward, float height, float side,
                float pitch, float yaw, float roll, float nearClip)
            {
                Fov = fov; Forward = forward; Height = height; Side = side;
                Pitch = pitch; Yaw = yaw; Roll = roll; NearClip = nearClip;
            }
        }

        private const int CameraButton = 0;         // INPUT_NEXT_CAMERA
        private const int BrakeButton = 72;         // INPUT_VEH_BRAKE (LT)
        private const int StockFirstPersonView = 4; // standard interior view
        private const int HeadBone = 31086;

        // Video shows FOV 120, vehicle attachment and -40.30 pitch on bikes.
        // Cars need a shallower pitch to avoid staring down at the dashboard.
        // Both presets can be calibrated in game and saved independently.
        private readonly Profile _carProfile = new Profile(
            120f, 0.04f, -0.04f, 0f, -14f, 0f, 0f, 0.16f);
        private readonly Profile _bikeProfile = new Profile(
            120f, 0.05f, -0.09f, 0f, -40.30f, 0f, 0f, 0.16f);

        private Camera _camera;
        private Vehicle _currentVehicle;
        // Enter vehicles in the game's own interior view. The user may switch
        // to exactly one custom interior view, then back to the original.
        private bool _customSelected;
        private bool _enabled = true;
        private bool _menuOpen;
        private bool _cameraControlAvailable = true;
        private bool _stockCameraAvailable = true;
        private bool _nativeHeadAvailable = true;
        private DateTime _lastSwitch = DateTime.MinValue;
        private int _errorCount;
        private int _menuIndex;
        private Profile _currentProfile;
        private string _configPath;
        private Vector3 _seatEyeLocal;
        private int _stockCamPrimeTicks = 2;
        private DateTime _lastMenuDrawUtc = DateTime.MinValue;

        // Outfit must be restored after switching to the stock view, exiting
        // the vehicle or disabling this script, even when an API call fails.
        private int _styledPedHandle;
        private int _styledPedModel;
        private bool _styleCaptured;
        private bool _hairChanged;
        private int _hairDrawable, _hairTexture, _hairPalette;
        private readonly int[] _originalProp = { -1, -1 };
        private readonly int[] _originalPropTexture = { 0, 0 };

        public VehicleCockpitCamera()
        {
            Interval = 0;
            Tick += OnTick;
            KeyDown += OnKeyDown;
            Aborted += OnAborted;
            LoadProfiles();
        }

        private void OnAborted(object sender, EventArgs e)
        {
            StopCamera();
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.F6)
            {
                _enabled = !_enabled;
                if (!_enabled) StopCamera();
                else
                {
                    _currentVehicle = null;
                    _stockCamPrimeTicks = 2;
                }
                Announce(_enabled ? "DFPV: bat" : "DFPV: tat");
                return;
            }
            if (e.KeyCode == Keys.F10)
            {
                _menuOpen = !_menuOpen;
                if (!_menuOpen) SaveProfiles();
                return;
            }
            if (_menuOpen)
            {
                if (e.KeyCode == Keys.Up) ChangeMenuIndex(-1);
                else if (e.KeyCode == Keys.Down) ChangeMenuIndex(1);
                else if (e.KeyCode == Keys.Left) Adjust(-1);
                else if (e.KeyCode == Keys.Right) Adjust(1);
                else if (e.KeyCode == Keys.Enter) SaveProfiles();
                else if (e.KeyCode == Keys.Escape) _menuOpen = false;
            }
            else if (e.KeyCode == Keys.N) ToggleView();
        }

        private void OnTick(object sender, EventArgs e)
        {
            try
            {
                Ped ped = Game.Player.Character;
                Vehicle vehicle = ped == null ? null : ped.CurrentVehicle;
                if (!_enabled || Game.IsLoading || Game.IsPaused || ped == null ||
                    !ped.Exists() || ped.IsDead || vehicle == null || !vehicle.Exists() ||
                    Function.Call<bool>(Hash.NETWORK_IS_SESSION_STARTED) ||
                    !SupportedVehicle(vehicle) ||
                    !Function.Call<bool>(Hash.IS_PED_SITTING_IN_ANY_VEHICLE, ped.Handle))
                {
                    StopCamera();
                    _currentVehicle = null;
                    _menuOpen = false;
                    return;
                }

                if (_currentVehicle == null || _currentVehicle.Handle != vehicle.Handle)
                {
                    StopCamera();
                    _currentVehicle = vehicle;
                    _currentProfile = IsBike(vehicle) ? _bikeProfile : _carProfile;
                    _stockCamPrimeTicks = 2;
                }

                if (_menuOpen)
                {
                    ReadMenuControls();
                    DrawMenu();
                }
                else
                {
                    ReadCameraButton();
                }

                if (!_customSelected)
                {
                    StopCamera();
                    SetStockCamera();
                    _stockCamPrimeTicks = 2;
                    return;
                }

                if (_camera == null)
                {
                    // Yield to a different script camera (for example Menyoo).
                    if (Function.Call<int>(Hash.GET_RENDERING_CAM) > 0) return;
                    // Let the unmodified gameplay camera settle in mode 4.
                    // We will use its cockpit eye as our attachment origin.
                    if (_stockCamPrimeTicks > 0)
                    {
                        SetStockCamera();
                        --_stockCamPrimeTicks;
                        return;
                    }
                    StartCamera(ped, vehicle);
                }
                if (_camera == null) return;
                int rendering = Function.Call<int>(Hash.GET_RENDERING_CAM);
                if (rendering > 0 && rendering != _camera.Handle)
                {
                    StopCamera();
                    return;
                }
                if (rendering == 0)
                    World.RenderingCamera = _camera;

                HideDriverHead(ped);
                // Position is attached to vehicle-local coordinates ONCE.
                // Only car rotation changes every frame, never its speed.
                _camera.Rotation = new Vector3(_currentProfile.Pitch,
                    _currentProfile.Roll,
                    vehicle.Heading + _currentProfile.Yaw);
                _camera.FieldOfView = _currentProfile.Fov;
                _errorCount = 0;
            }
            catch (Exception)
            {
                StopCamera();
                if (++_errorCount >= 3)
                {
                    _enabled = false;
                    Announce("DFPV: loi native. Mod da tat an toan.");
                }
            }
        }

        private static bool IsBike(Vehicle vehicle)
        {
            return Function.Call<bool>(Hash.IS_THIS_MODEL_A_BIKE, vehicle.Model.Hash);
        }

        private static bool SupportedVehicle(Vehicle vehicle)
        {
            return IsBike(vehicle) ||
                Function.Call<bool>(Hash.IS_THIS_MODEL_A_CAR, vehicle.Model.Hash);
        }

        private void ToggleView()
        {
            if ((DateTime.UtcNow - _lastSwitch).TotalMilliseconds < 300) return;
            _lastSwitch = DateTime.UtcNow;
            _customSelected = !_customSelected;
            if (!_customSelected)
            {
                StopCamera();
                SetStockCamera();
            }
            else
            {
                _stockCamPrimeTicks = 1;
            }
            Announce(_customSelected ? "DFPV: goc rong trong xe" :
                "DFPV: goc mac dinh trong xe");
        }

        private void ReadCameraButton()
        {
            // Do not disable stock input if iOS lacks the interception native.
            bool tapped = false;
            bool openEditor = false;
            if (_cameraControlAvailable)
            {
                try
                {
                    Function.Call(Hash.DISABLE_CONTROL_ACTION, 0, CameraButton, true);
                    tapped = Function.Call<bool>(Hash.IS_DISABLED_CONTROL_JUST_PRESSED,
                        0, CameraButton);
                }
                catch (Exception)
                {
                    _cameraControlAvailable = false;
                    Announce("DFPV: dung phim N de chuyen goc");
                }
            }
            // LB + D-pad LEFT: extra fallback for iOS on-screen controllers.
            try
            {
                if (Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 2, 205) &&
                    Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 189))
                    tapped = true;
                if (Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 2, 205) &&
                    Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 188))
                    openEditor = true;
                // Do not interpret an LT brake press as a view change.
                if (Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 0, BrakeButton))
                    tapped = false;
            }
            catch (Exception) { /* keyboard N is still available */ }
            if (openEditor)
            {
                _menuOpen = true;
                Announce("DFPV: mo chinh camera. LB + UP de dong");
                return;
            }
            if (tapped) ToggleView();
        }

        private void SetStockCamera()
        {
            if (!_stockCameraAvailable) return;
            try
            {
                if (Function.Call<int>(Hash.GET_RENDERING_CAM) > 0) return;
                if (Function.Call<int>(Hash.GET_FOLLOW_VEHICLE_CAM_VIEW_MODE) !=
                    StockFirstPersonView)
                    Function.Call(Hash.SET_FOLLOW_VEHICLE_CAM_VIEW_MODE,
                        StockFirstPersonView);
            }
            catch (Exception)
            {
                _stockCameraAvailable = false;
                // Fail open: do not repeatedly fight vanilla camera controls.
                Announce("DFPV: khong ep duoc goc mac dinh tren iOS nay");
            }
        }

        private void StartCamera(Ped ped, Vehicle vehicle)
        {
            // Calibrate against GTA's TRUE interior gameplay camera. This is
            // crucial: animated/custom ped head bones can be behind the roof,
            // behind the window or outside the cabin on nonstandard vehicles.
            Vector3 eye = Function.Call<Vector3>(Hash.GET_GAMEPLAY_CAM_COORD);
            if (!Finite(eye) || (eye - ped.Position).Length() > 3.5f)
            {
                // Bone fallback if this port cannot report a native eye.
                eye = Function.Call<Vector3>(Hash.GET_PED_BONE_COORDS,
                    ped.Handle, HeadBone, 0f, 0f, 0f);
            }
            Vector3 local = Function.Call<Vector3>(
                Hash.GET_OFFSET_FROM_ENTITY_GIVEN_WORLD_COORDS,
                vehicle.Handle, eye.X, eye.Y, eye.Z);
            if (!Finite(local) || local.Length() > 15f || local.Length() < 0.05f)
                throw new InvalidOperationException("Camera seat position invalid");

            _seatEyeLocal = local;
            _camera = World.CreateCamera(eye,
                new Vector3(_currentProfile.Pitch, 0f, vehicle.Heading),
                _currentProfile.Fov);
            if (_camera == null) throw new InvalidOperationException("CREATE_CAM failed");
            _camera.NearClip = _currentProfile.NearClip;
            // No world-space smoothing: native attachment follows every frame.
            _camera.AttachTo(vehicle, _seatEyeLocal + CameraOffsets());
            _camera.IsActive = true;
            World.RenderingCamera = _camera;
        }

        private void RepositionCamera()
        {
            if (_camera == null || _currentVehicle == null) return;
            // Keep the same calibrated seat eye while adjusting in the menu.
            // Destroying the camera here would remeasure a hidden head and
            // cause abrupt roof/door clipping when a setting is changed.
            _camera.AttachTo(_currentVehicle, _seatEyeLocal + CameraOffsets());
            _camera.NearClip = _currentProfile.NearClip;
            _camera.FieldOfView = _currentProfile.Fov;
        }

        private Vector3 CameraOffsets()
        {
            return new Vector3(_currentProfile.Side, _currentProfile.Forward,
                _currentProfile.Height);
        }

        private void HideDriverHead(Ped ped)
        {
            if (_nativeHeadAvailable)
                try { Function.Call(Hash.SET_PED_RESET_FLAG, ped.Handle, 166, true); }
                catch (Exception) { _nativeHeadAvailable = false; }

            if (_styleCaptured) return;
            try
            {
                _styledPedHandle = ped.Handle;
                _styledPedModel = ped.Model.Hash;
                _hairDrawable = Function.Call<int>(Hash.GET_PED_DRAWABLE_VARIATION,
                    ped.Handle, 2);
                _hairTexture = Function.Call<int>(Hash.GET_PED_TEXTURE_VARIATION,
                    ped.Handle, 2);
                _hairPalette = Function.Call<int>(Hash.GET_PED_PALETTE_VARIATION,
                    ped.Handle, 2);
                for (int i = 0; i < 2; i++)
                {
                    _originalProp[i] = Function.Call<int>(Hash.GET_PED_PROP_INDEX,
                        ped.Handle, i);
                    if (_originalProp[i] >= 0)
                        _originalPropTexture[i] = Function.Call<int>(
                            Hash.GET_PED_PROP_TEXTURE_INDEX, ped.Handle, i);
                }
                _styleCaptured = true;
                // This hides standard hair, not arbitrary modded ped meshes.
                if (_hairDrawable > 0 && Function.Call<int>(
                    Hash.GET_NUMBER_OF_PED_DRAWABLE_VARIATIONS, ped.Handle, 2) > 1)
                {
                    _hairChanged = true;
                    Function.Call(Hash.SET_PED_COMPONENT_VARIATION, ped.Handle,
                        2, 0, 0, 0);
                }
                for (int i = 0; i < 2; i++)
                    if (_originalProp[i] >= 0)
                        Function.Call(Hash.CLEAR_PED_PROP, ped.Handle, i);
            }
            catch (Exception) { RestoreAppearance(); }
        }

        private void RestoreAppearance()
        {
            if (!_styleCaptured) return;
            try
            {
                Ped ped = Game.Player.Character;
                if (ped != null && ped.Exists() &&
                    ped.Handle == _styledPedHandle &&
                    ped.Model.Hash == _styledPedModel)
                {
                    if (_hairChanged)
                        Function.Call(Hash.SET_PED_COMPONENT_VARIATION,
                            ped.Handle, 2, _hairDrawable, _hairTexture, _hairPalette);
                    for (int i = 0; i < 2; i++)
                        if (_originalProp[i] >= 0)
                            Function.Call(Hash.SET_PED_PROP_INDEX, ped.Handle, i,
                                _originalProp[i], _originalPropTexture[i], true);
                }
            }
            catch (Exception) { /* camera still must be released */ }
            finally
            {
                _styleCaptured = false;
                _styledPedHandle = 0;
                _hairChanged = false;
                _originalProp[0] = _originalProp[1] = -1;
            }
        }

        private void StopCamera()
        {
            RestoreAppearance();
            if (_camera == null) return;
            try
            {
                if (Function.Call<int>(Hash.GET_RENDERING_CAM) == _camera.Handle)
                    World.RenderingCamera = null;
            }
            catch (Exception) { }
            try { _camera.IsActive = false; }
            catch (Exception) { }
            try { _camera.Destroy(); }
            catch (Exception) { }
            _camera = null;
        }

        private void ReadMenuControls()
        {
            // Prevent the native GTA cycle while the in-game settings are open.
            if (_cameraControlAvailable)
                try { Function.Call(Hash.DISABLE_CONTROL_ACTION, 0, CameraButton, true); }
                catch (Exception) { _cameraControlAvailable = false; }
            try
            {
                // LB+UP closes the editor without Menyoo's RB bind.
                if (Function.Call<bool>(Hash.IS_CONTROL_PRESSED, 2, 205) &&
                    Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 188))
                {
                    _menuOpen = false;
                    SaveProfiles();
                    return;
                }
                if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 188))
                    ChangeMenuIndex(-1);
                if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 187))
                    ChangeMenuIndex(1);
                if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 189))
                    Adjust(-1);
                if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 190))
                    Adjust(1);
                if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 201))
                    SaveProfiles();
                if (Function.Call<bool>(Hash.IS_CONTROL_JUST_PRESSED, 2, 202))
                    _menuOpen = false;
            }
            catch (Exception) { }
        }

        private void ChangeMenuIndex(int delta)
        {
            _menuIndex = (_menuIndex + 5 + delta) % 5;
        }

        private void Adjust(int direction)
        {
            if (_currentProfile == null) return;
            switch (_menuIndex)
            {
                case 0: _currentProfile.Fov = Clamp(_currentProfile.Fov + 2f * direction, 60f, 130f); break;
                case 1: _currentProfile.Forward = Clamp(_currentProfile.Forward + 0.02f * direction, -0.35f, 0.35f); break;
                case 2: _currentProfile.Height = Clamp(_currentProfile.Height + 0.02f * direction, -0.35f, 0.35f); break;
                case 3: _currentProfile.Pitch = Clamp(_currentProfile.Pitch + 2f * direction, -70f, 35f); break;
                case 4: _currentProfile.NearClip = Clamp(_currentProfile.NearClip + 0.01f * direction, 0.05f, 0.30f); break;
            }
            RepositionCamera();
        }

        private void DrawMenu()
        {
            if (_currentProfile == null) return;
            if ((DateTime.UtcNow - _lastMenuDrawUtc).TotalMilliseconds < 240) return;
            _lastMenuDrawUtc = DateTime.UtcNow;
            string[] names = { "FOV", "Tien/lui", "Cao/thap", "Goc cui", "NearClip" };
            float[] values = { _currentProfile.Fov, _currentProfile.Forward,
                _currentProfile.Height, _currentProfile.Pitch, _currentProfile.NearClip };
            Announce("DFPV " + (IsBike(_currentVehicle) ? "XE MAY" : "O TO") +
                " | " + names[_menuIndex] + ": " +
                values[_menuIndex].ToString("0.00", CultureInfo.InvariantCulture) +
                " | UP/DOWN chon, LEFT/RIGHT chinh, A luu, B thoat");
        }

        private void LoadProfiles()
        {
            foreach (string path in ConfigPaths())
            {
                try
                {
                    if (!File.Exists(path)) continue;
                    string section = "";
                    foreach (string original in File.ReadAllLines(path))
                    {
                        string line = original.Trim();
                        if (line.StartsWith("[") && line.EndsWith("]"))
                        {
                            section = line.Substring(1, line.Length - 2);
                            continue;
                        }
                        string[] kv = line.Split(new[] { '=' }, 2);
                        if (kv.Length != 2) continue;
                        Profile p = section == "Car" ? _carProfile :
                            section == "Bike" ? _bikeProfile : null;
                        if (p == null) continue;
                        float value;
                        if (!float.TryParse(kv[1].Trim(), NumberStyles.Float,
                            CultureInfo.InvariantCulture, out value) ||
                            float.IsNaN(value) || float.IsInfinity(value)) continue;
                        switch (kv[0].Trim())
                        {
                            case "Fov": p.Fov = Clamp(value, 60f, 130f); break;
                            case "Forward": p.Forward = Clamp(value, -0.35f, 0.35f); break;
                            case "Height": p.Height = Clamp(value, -0.35f, 0.35f); break;
                            case "Pitch": p.Pitch = Clamp(value, -70f, 35f); break;
                            case "NearClip": p.NearClip = Clamp(value, 0.05f, 0.30f); break;
                        }
                    }
                    _configPath = path;
                    return;
                }
                catch (Exception) { }
            }
        }

        private void SaveProfiles()
        {
            string[] content = {
                "# DFPV clean rebuild; distances in metres; pitch in degrees",
                "[Car]", "Fov=" + F(_carProfile.Fov),
                "Forward=" + F(_carProfile.Forward), "Height=" + F(_carProfile.Height),
                "Pitch=" + F(_carProfile.Pitch), "NearClip=" + F(_carProfile.NearClip),
                "[Bike]", "Fov=" + F(_bikeProfile.Fov),
                "Forward=" + F(_bikeProfile.Forward), "Height=" + F(_bikeProfile.Height),
                "Pitch=" + F(_bikeProfile.Pitch), "NearClip=" + F(_bikeProfile.NearClip)
            };
            foreach (string path in ConfigPaths())
            {
                try
                {
                    string directory = Path.GetDirectoryName(path);
                    if (string.IsNullOrEmpty(directory) || !Directory.Exists(directory)) continue;
                    File.WriteAllLines(path, content);
                    _configPath = path;
                    Announce("DFPV: da luu thong so camera");
                    return;
                }
                catch (Exception) { }
            }
            Announce("DFPV: khong co quyen ghi INI tren duong dan script");
        }

        private string[] ConfigPaths()
        {
            string asmDir = "";
            try { asmDir = Path.GetDirectoryName(GetType().Assembly.Location); }
            catch (Exception) { }
            return new[] {
                _configPath,
                string.IsNullOrEmpty(asmDir) ? null : Path.Combine(asmDir, "DFPV_Camera.ini"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "scripts", "DFPV_Camera.ini"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "DFPV_Camera.ini")
            };
        }

        private static string F(float v)
        {
            return v.ToString("0.0000", CultureInfo.InvariantCulture);
        }

        private static bool Finite(Vector3 v)
        {
            return !float.IsNaN(v.X) && !float.IsNaN(v.Y) && !float.IsNaN(v.Z) &&
                !float.IsInfinity(v.X) && !float.IsInfinity(v.Y) && !float.IsInfinity(v.Z);
        }

        private static float Clamp(float value, float min, float max)
        {
            return Math.Max(min, Math.Min(max, value));
        }

        private static void Announce(string text)
        {
            try { UI.ShowSubtitle(text); }
            catch (Exception) { }
        }
    }
}

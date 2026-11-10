// Independent Superman-style powers for the GTA V iOS ARM64 ScriptHookV port.
// Experimental prototype, NOT a binary translation of TamedMods' Superman.asi.
// Gameplay natives are from alloc8or's public GTA V NativeDB (Legacy hashes).
#include "shv_api.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

extern "C" void supermanPlaySound(const char* soundName, bool loop);
extern "C" void supermanStopSound(const char* soundName);

namespace {
using namespace shv;
constexpr float kPi = 3.14159265358979323846f;
constexpr float kDeg = kPi / 180.0f;

enum Key : int {
    MOUSE_LEFT = 1, MOUSE_RIGHT = 2, SPACE = 32, SHIFT = 16, CTRL = 17,
    F8 = 119, F10 = 121, NP0 = 96, NP1 = 97, NP5 = 101,
    A = 'A', B = 'B', D = 'D', F = 'F', G = 'G', H = 'H', K = 'K',
    L = 'L', N = 'N', O = 'O', P = 'P', R = 'R', S = 'S', T = 'T',
    U = 'U', V = 'V', W = 'W', Y = 'Y', Z = 'Z'
};

enum class PowerAnim : std::size_t {
    ThunderClap, Tornado, Breath, HeatVision, GroundPound, SuperJump,
    Takeoff, Landing, Lift, CarryIdle, CarryWalk, CarryRun, Throw, Count
};

struct Animation {
    std::string dict;
    std::string clip;
    std::uint32_t impactMs = 0;
};

struct LaserSpec {
    int r, g, b;
    float range;
    float damagePerSecond;
    float particleScale;
    int explosionType;
    std::uint32_t pulseMs;
    std::string particleName;
    int spokes = 8;
    int layers = 4;
    float spread = 0.02f;
    float coreWidth = 0.00625f;
    float eyeSeparation = 0.13f;
    float eyeForward = 0.10f;
    float glowScale = 0.078f;
    float impactGlowScale = 0.22f;
    float muzzleGlowScale = 0.0f;
    int glowAlpha = 38;
    bool glow = true;
};

struct Config {
    float cruiseSpeed = 45.0f;
    float supersonicSpeed = 170.0f;
    float verticalSpeed = 22.0f;
    float acceleration = 0.06f;
    float jumpPower = 26.0f;
    float jumpForward = 6.0f;
    float shockRadius = 14.0f;
    float landingShockwaveMinSpeed = 18.0f;
    float beamRange = 160.0f;
    float beamDamage = 18.0f;
    float slowTimeScale = 0.25f;
    float hoverDrag = 0.12f;
    float stickDeadzone = 0.17f;
    float autoLandingSpeed = 24.0f;
    float bankAngle = 35.0f;
    float pitchScale = 1.0f;
    // A pitch-follow rotation can make the mobile camera stare into the sky.
    bool flightBodyTilt = false;
    bool supersonicTrail = true;
    bool actionChargeGlow = true;
    bool volumetricBeams = true;
    bool shockwaveMeshes = true;
    float sprintMultiplier = 1.49f;
    float groundSpeedBoost = 34.0f;
    float clapRadius = 18.0f, clapForce = 60.0f, clapLift = 35.0f;
    float tornadoRadius = 14.0f, tornadoForce = 35.0f, tornadoLift = 20.0f;
    float landingForce = 28.0f, landingLift = 12.0f;
    float solarRadius = 60.0f, solarPedForce = 30.0f;
    float freezeRange = 16.0f, superBreathRange = 25.0f;
    float superBreathPedForce = 50.0f, superBreathVehicleForce = 150.0f;
    std::uint32_t freezeDurationMs = 12000;
    std::string freezeFx = "ent_sht_extinguisher";
    bool cooldownsEnabled = true, overheatEnabled = true;
    std::uint32_t clapCooldownMs = 6000, groundCooldownMs = 4000;
    std::uint32_t solarCooldownMs = 25000, bulletTimeCooldownMs = 15000;
    std::uint32_t takedownCooldownMs = 2500, uppercutCooldownMs = 3000;
    std::uint32_t laserMaxMs = 5000, laserCooldownMs = 4000;
    std::uint32_t breathMaxMs = 6000, breathCooldownMs = 3500;
    bool invincible = true;
    bool noRagdoll = true;
    bool noWantedLevel = false;
    bool notifications = true;
    bool sonicBoom = true;
    bool sonicCameraShake = true;
    std::string hoverDict = "skydive@parachute@";
    std::string hoverAnim = "chute_idle";
    std::string flyDict = "skydive@freefall";
    std::string flyAnim = "free_forward";
    std::string supersonicDict = "skydive@freefall";
    std::string supersonicAnim = "free_forward";
    std::string supersonicPostFx = "RaceTurbo";
    // Original Laser1-Laser5 core colours, ranges, hit FX and pulse intervals.
    std::array<LaserSpec, 5> lasers{{
        {255, 40, 20, 400.0f, 1600.0f, 0.5f, -1, 0, "bul_carmetal"},
        {40, 210, 255, 300.0f, 250.0f, 2.5f, 18, 0, "bul_carmetal"},
        {255, 200, 50, 250.0f, 900.0f, 2.0f, 3, 0, "exp_grd_flare"},
        {200, 70, 255, 500.0f, 0.0f, 1.0f, 5, 320, "ent_dst_gen_gobstop"},
        {190, 235, 255, 200.0f, 0.0f, 0.7f, -1, 0, "exp_grd_bzgas_smoke"}
    }};

    // Defaults transcribed from the user's original TamedMods Superman.ini.
    std::array<Animation, static_cast<std::size_t>(PowerAnim::Count)> animations{{
        {"anim@arena@celeb@flat@solo@no_props@", "angry_clap_a_player_a", 520},
        {"missminuteman_1ig_2", "handsup_base", 0},
        {"amb@world_human_muscle_flex@arms_in_front@base", "base", 0},
        {"amb@world_human_muscle_flex@arms_at_side@base", "base", 0},
        {"melee@unarmed@streamed_core", "ground_attack_on_spot", 380},
        {"move_jump", "jump_launch_high_r", 0},
        {"move_jump", "jump_launch_l_to_skydive", 0},
        {"skydive@parachute@", "land_bend_knees", 0},
        {"anim@heists@load_box", "lift_box", 700},
        {"anim@heists@box_carry@", "idle", 0},
        {"anim@heists@box_carry@", "walk", 0},
        {"anim@heists@box_carry@", "run", 0},
        {"missfbi4prepp1", "_bag_throw_garbage_man", 450}
    }};

    const Animation& anim(PowerAnim what) const {
        return animations[static_cast<std::size_t>(what)];
    }

    std::array<int, 5> beamKeys{{97, 98, 99, 100, 101}};
    int toggle = 121, fly = 32, descend = 162, boost = 160;
    int laser = 82, cycle = 96, freezeBreath = 71, superBreath = 72;
    int clap = 86, tornado = 84, groundPound = 66, lift = 70;
    int xray = 78, slowMotion = 89, combat = 75;
    int uppercut = 85, takedown = 90, piledrive = 76;
    int solarFlare = 119, lock = 2, attack = 1;
    int telescope = 79, superHearing = 80;
    int tapHoldMs = 250;
    bool startEnabled = false;

    // Load the user's own Superman.ini (from Documents or the imported mod).
    // Unrecognised fields are deliberately ignored rather than changing them.
    void load(const char* explicitPath = nullptr) {
        std::string location;
        if (explicitPath && *explicitPath) location = explicitPath;
        const char* homeDir = std::getenv("HOME");
        if (location.empty() && homeDir && *homeDir) {
            const std::string root(homeDir);
            for (const char* suffix : {"/Documents/Superman.ini",
                                       "/Documents/mods/Superman.ini",
                                       "/Documents/mods/scripthook/scripts/Superman.ini",
                                       "/Documents/mods/scripthook/Superman.ini"}) {
                std::ifstream test(root + suffix);
                if (test.good()) { location = root + suffix; break; }
            }
        }
        std::ifstream in;
        if (!location.empty()) in.open(location);
        if (!in.good()) in.open("Superman.ini");
        if (!in.good()) return;
        auto trim = [](std::string s) {
            auto valid = [](unsigned char c) { return !std::isspace(c); };
            s.erase(s.begin(), std::find_if(s.begin(), s.end(), valid));
            s.erase(std::find_if(s.rbegin(), s.rend(), valid).base(), s.end());
            return s;
        };
        std::string section, line;
        while (std::getline(in, line)) {
            const auto comment = line.find_first_of(";#");
            if (comment != std::string::npos) line.erase(comment);
            line = trim(line);
            if (line.empty()) continue;
            if (line.front() == '[' && line.back() == ']') {
                section = line.substr(1, line.size() - 2); continue;
            }
            const auto delimiter = line.find('=');
            if (delimiter == std::string::npos) continue;
            const std::string key = trim(line.substr(0, delimiter));
            const std::string value = trim(line.substr(delimiter + 1));
            if (value.empty()) continue;
            char* end = nullptr;
            const float number = std::strtof(value.c_str(), &end);
            const bool numeric = end && end != value.c_str() &&
                                 std::isfinite(number);
            auto setFloat = [&](const char* name, float& field) {
                if (numeric && key == name) field = number;
            };
            auto setKey = [&](const char* name, int& field) {
                if (numeric && key == name && number >= 1 && number < 255)
                    field = static_cast<int>(number);
            };
            auto setDuration = [&](const char* name, std::uint32_t& field) {
                if (numeric && key == name && number >= 0.0f)
                    field = static_cast<std::uint32_t>(std::clamp(number, 0.0f, 60000.0f));
            };
            if (section == "General") {
                if (key == "Invincible") invincible = value == "true" || value == "1";
                if (key == "NoRagdoll") noRagdoll = value == "true" || value == "1";
                if (key == "NoWantedLevel") noWantedLevel = value == "true" || value == "1";
                if (key == "StartEnabled") startEnabled = value == "true" || value == "1";
                if (key == "Notifications") notifications = value == "true" || value == "1";
            } else if (section == "Flight") {
                setFloat("CruiseSpeed", cruiseSpeed);
                setFloat("SupersonicSpeed", supersonicSpeed);
                setFloat("VerticalSpeed", verticalSpeed);
                setFloat("Acceleration", acceleration);
                setFloat("HoverDrag", hoverDrag);
                setFloat("StickDeadzone", stickDeadzone);
                setFloat("AutoLandingSpeed", autoLandingSpeed);
                setFloat("BankAngle", bankAngle);
                setFloat("PitchScale", pitchScale);
                if (key == "HoverDict") hoverDict = value;
                if (key == "HoverAnim") hoverAnim = value;
                if (key == "FlyDict") flyDict = value;
                if (key == "FlyAnim") flyAnim = value;
                if (key == "SupersonicDict") supersonicDict = value;
                if (key == "SupersonicAnim") supersonicAnim = value;
                if (key == "SupersonicPostFx") supersonicPostFx = value;
                if (key == "SonicBoom") sonicBoom = value == "true" || value == "1";
                if (key == "SonicCameraShake") sonicCameraShake = value == "true" || value == "1";
            } else if (section == "Animations") {
                static constexpr const char* names[] = {
                    "ThunderClap", "Tornado", "Breath", "HeatVision", "GroundPound",
                    "SuperJump", "Takeoff", "Landing", "Lift", "CarryIdle",
                    "CarryWalk", "CarryRun", "Throw"
                };
                for (std::size_t i = 0; i < animations.size(); ++i) {
                    if (key != names[i]) continue;
                    const auto first = value.find('|');
                    const auto second = value.find('|', first == std::string::npos ? 0 : first + 1);
                    if (first == std::string::npos || second == std::string::npos) break;
                    const auto dict = trim(value.substr(0, first));
                    const auto clip = trim(value.substr(first + 1, second - first - 1));
                    const auto delay = trim(value.substr(second + 1));
                    char* delayEnd = nullptr;
                    const unsigned long parsed = std::strtoul(delay.c_str(), &delayEnd, 10);
                    if (!dict.empty() && !clip.empty() && delayEnd && *delayEnd == '\0' &&
                        parsed <= 5000UL) animations[i] = {dict, clip, static_cast<std::uint32_t>(parsed)};
                    break;
                }
            } else if (section == "Landing") {
                setFloat("ShockRadius", shockRadius);
                setFloat("ShockForce", landingForce);
                setFloat("ShockLift", landingLift);
                setFloat("ShockwaveMinSpeed", landingShockwaveMinSpeed);
            } else if (section == "SuperSpeed") {
                setFloat("SprintMultiplier", sprintMultiplier);
                setFloat("SpeedBoost", groundSpeedBoost);
            } else if (section == "FreezeBreath") {
                setFloat("Range", freezeRange);
                setDuration("FreezeDurationMs", freezeDurationMs);
                if (key == "PtfxName" && value.size() < 96) freezeFx = value;
            } else if (section == "SuperBreath") {
                setFloat("Range", superBreathRange);
                setFloat("PedForce", superBreathPedForce);
                setFloat("VehicleForce", superBreathVehicleForce);
            } else if (section == "ThunderClap") {
                setFloat("Radius", clapRadius);
                setFloat("Force", clapForce);
                setFloat("Lift", clapLift);
            } else if (section == "Tornado") {
                setFloat("Radius", tornadoRadius);
                setFloat("Force", tornadoForce);
                setFloat("Lift", tornadoLift);
            } else if (section == "SolarFlare") {
                setFloat("Radius", solarRadius);
                setFloat("PedForce", solarPedForce);
            } else if (section == "Cooldowns") {
                if (key == "Enabled") cooldownsEnabled = value == "true" || value == "1";
                setDuration("ThunderClapMs", clapCooldownMs);
                setDuration("GroundPoundMs", groundCooldownMs);
                setDuration("SolarFlareMs", solarCooldownMs);
                setDuration("BulletTimeMs", bulletTimeCooldownMs);
                setDuration("TakedownMs", takedownCooldownMs);
                setDuration("UppercutMs", uppercutCooldownMs);
            } else if (section == "Overheat") {
                if (key == "Enabled") overheatEnabled = value == "true" || value == "1";
                setDuration("LaserMaxMs", laserMaxMs);
                setDuration("LaserCooldownMs", laserCooldownMs);
                setDuration("BreathMaxMs", breathMaxMs);
                setDuration("BreathCooldownMs", breathCooldownMs);
            } else if (section == "Jump") {
                setFloat("JumpPower", jumpPower);
                setFloat("JumpForward", jumpForward);
            } else if (section.size() == 6 && section.compare(0, 5, "Laser") == 0 &&
                       section[5] >= '1' && section[5] <= '5') {
                auto& laserSpec = lasers[static_cast<std::size_t>(section[5] - '1')];
                setFloat("Range", laserSpec.range);
                setFloat("PedDamagePerSecond", laserSpec.damagePerSecond);
                setFloat("PtfxScale", laserSpec.particleScale);
                if (key == "PtfxName" && value.size() < 96) laserSpec.particleName = value;
                if (key == "ColorR" && numeric) laserSpec.r = static_cast<int>(std::clamp(number, 0.0f, 255.0f));
                if (key == "ColorG" && numeric) laserSpec.g = static_cast<int>(std::clamp(number, 0.0f, 255.0f));
                if (key == "ColorB" && numeric) laserSpec.b = static_cast<int>(std::clamp(number, 0.0f, 255.0f));
                if (key == "Spokes" && numeric) laserSpec.spokes = static_cast<int>(std::clamp(number, 4.0f, 12.0f));
                if (key == "Layers" && numeric) laserSpec.layers = static_cast<int>(std::clamp(number, 1.0f, 8.0f));
                setFloat("Spread", laserSpec.spread);
                setFloat("CoreWidth", laserSpec.coreWidth);
                setFloat("EyeSeparation", laserSpec.eyeSeparation);
                setFloat("EyeForward", laserSpec.eyeForward);
                setFloat("GlowScale", laserSpec.glowScale);
                setFloat("ImpactGlowScale", laserSpec.impactGlowScale);
                setFloat("MuzzleGlowScale", laserSpec.muzzleGlowScale);
                if (key == "GlowAlpha" && numeric)
                    laserSpec.glowAlpha = static_cast<int>(std::clamp(number, 0.0f, 100.0f));
                if (key == "Glow") laserSpec.glow = value == "true" || value == "1";
                if (key == "ExplosionType" && numeric)
                    laserSpec.explosionType = static_cast<int>(std::clamp(number, -1.0f, 60.0f));
                if (key == "PulseMs" && numeric)
                    laserSpec.pulseMs = static_cast<std::uint32_t>(std::clamp(number, 0.0f, 1500.0f));
                if (section == "Laser1") {
                    setFloat("Range", beamRange);
                    setFloat("Damage", beamDamage);
                }
            } else if (section == "BulletTime") {
                setFloat("TimeScale", slowTimeScale);
            } else if (section == "VisualsIOS") {
                if (key == "FlightBodyTilt") flightBodyTilt = value == "true" || value == "1";
                if (key == "SupersonicTrail") supersonicTrail = value == "true" || value == "1";
                if (key == "ActionChargeGlow") actionChargeGlow = value == "true" || value == "1";
                if (key == "VolumetricBeams") volumetricBeams = value == "true" || value == "1";
                if (key == "ShockwaveMeshes") shockwaveMeshes = value == "true" || value == "1";
            } else if (section == "Keys") {
                setKey("Toggle", toggle);
                setKey("Fly", fly);
                if (key == "TapHoldMs" && numeric)
                    tapHoldMs = std::clamp(static_cast<int>(number), 100, 1000);
                setKey("Descend", descend);
                setKey("Supersonic", boost);
                setKey("HeatVision", laser);
                setKey("LaserCycle", cycle);
                setKey("FreezeBreath", freezeBreath);
                setKey("SuperBreath", superBreath);
                setKey("ThunderClap", clap);
                setKey("TornadoSpin", tornado);
                setKey("GroundPound", groundPound);
                setKey("LiftThrow", lift);
                setKey("XRayVision", xray);
                setKey("BulletTime", slowMotion);
                setKey("CombatMode", combat);
                setKey("UppercutLaunch", uppercut);
                setKey("Takedown", takedown);
                setKey("Piledrive", piledrive);
                setKey("SolarFlare", solarFlare);
                setKey("LockTarget", lock);
                setKey("Telescope", telescope);
                setKey("SuperHearing", superHearing);
                for (int i = 0; i < 5; ++i) {
                    const std::string label = "Laser" + std::to_string(i + 1);
                    if (numeric && key == label && number >= 1 && number < 255)
                        beamKeys[i] = static_cast<int>(number);
                }
            }
        }
        cruiseSpeed = std::clamp(cruiseSpeed, 2.0f, 200.0f);
        supersonicSpeed = std::clamp(supersonicSpeed, cruiseSpeed, 300.0f);
        hoverDrag = std::clamp(hoverDrag, 0.02f, 1.0f);
        stickDeadzone = std::clamp(stickDeadzone, 0.08f, 0.35f);
        autoLandingSpeed = std::clamp(autoLandingSpeed, 8.0f, 40.0f);
        bankAngle = std::clamp(bankAngle, 0.0f, 35.0f);
        pitchScale = std::clamp(pitchScale, 0.0f, 1.0f);
        beamRange = std::clamp(beamRange, 5.0f, 450.0f);
        for (auto& laserSpec : lasers) {
            laserSpec.range = std::clamp(laserSpec.range, 5.0f, 550.0f);
            laserSpec.damagePerSecond = std::clamp(laserSpec.damagePerSecond, 0.0f, 4000.0f);
            laserSpec.particleScale = std::clamp(laserSpec.particleScale, 0.01f, 5.0f);
            laserSpec.spread = std::clamp(laserSpec.spread, 0.005f, 0.15f);
            laserSpec.coreWidth = std::clamp(laserSpec.coreWidth, 0.001f, 0.025f);
            laserSpec.eyeSeparation = std::clamp(laserSpec.eyeSeparation, 0.04f, 0.22f);
            laserSpec.eyeForward = std::clamp(laserSpec.eyeForward, 0.0f, 0.3f);
            laserSpec.glowScale = std::clamp(laserSpec.glowScale, 0.0f, 0.30f);
            laserSpec.impactGlowScale = std::clamp(laserSpec.impactGlowScale, 0.0f, 1.0f);
            laserSpec.muzzleGlowScale = std::clamp(laserSpec.muzzleGlowScale, 0.0f, 0.5f);
        }
        slowTimeScale = std::clamp(slowTimeScale, 0.05f, 1.0f);
        jumpPower = std::clamp(jumpPower, 3.0f, 75.0f);
        jumpForward = std::clamp(jumpForward, 0.0f, 30.0f);
        sprintMultiplier = std::clamp(sprintMultiplier, 1.0f, 1.49f);
        groundSpeedBoost = std::clamp(groundSpeedBoost, 1.0f, 45.0f);
        clapRadius = std::clamp(clapRadius, 1.0f, 35.0f);
        clapForce = std::clamp(clapForce, 0.0f, 180.0f);
        clapLift = std::clamp(clapLift, 0.0f, 120.0f);
        tornadoRadius = std::clamp(tornadoRadius, 1.0f, 30.0f);
        tornadoForce = std::clamp(tornadoForce, 0.0f, 150.0f);
        tornadoLift = std::clamp(tornadoLift, 0.0f, 120.0f);
        shockRadius = std::clamp(shockRadius, 1.0f, 45.0f);
        landingShockwaveMinSpeed = std::clamp(landingShockwaveMinSpeed, 1.0f, 70.0f);
        landingForce = std::clamp(landingForce, 0.0f, 150.0f);
        landingLift = std::clamp(landingLift, 0.0f, 100.0f);
        solarRadius = std::clamp(solarRadius, 1.0f, 70.0f);
        solarPedForce = std::clamp(solarPedForce, 0.0f, 150.0f);
        freezeRange = std::clamp(freezeRange, 2.0f, 35.0f);
        superBreathRange = std::clamp(superBreathRange, 2.0f, 40.0f);
        superBreathPedForce = std::clamp(superBreathPedForce, 0.0f, 150.0f);
        superBreathVehicleForce = std::clamp(superBreathVehicleForce, 0.0f, 250.0f);
    }
};

struct Input {
    std::array<std::uint8_t, 256> was{};
    std::array<std::uint8_t, 256> now{};

    void sample() {
        was = now;
        for (int vk = 1; vk < 255; ++vk) now[vk] = iosKeyIsDown(vk) ? 1 : 0;
    }
    bool down(int vk) const { return vk > 0 && vk < 256 && now[vk] != 0; }
    bool pressed(int vk) const { return down(vk) && !was[vk]; }
    bool released(int vk) const { return !down(vk) && was[vk]; }
};

struct FlightStick {
    float right = 0.0f;
    float forward = 0.0f;
    float magnitude = 0.0f;
};

FlightStick readFlightStick(const Input& keys, float deadzone) {
    // GTA V analog player input: 30 = left/right, 31 = forward/back.
    // Left-stick up reports negative INPUT_MOVE_UD on a controller.
    auto axis = [](int control) {
        float value = call<float>(hash::GET_CONTROL_NORMAL, 0, control);
        if (std::fabs(value) <= 0.001f)
            value = call<float>(hash::GET_CONTROL_NORMAL, 2, control);
        if (std::fabs(value) <= 0.001f)
            value = call<float>(hash::GET_DISABLED_CONTROL_NORMAL, 0, control);
        if (std::fabs(value) <= 0.001f)
            value = call<float>(hash::GET_DISABLED_CONTROL_NORMAL, 2, control);
        return std::isfinite(value) ? std::clamp(value, -1.0f, 1.0f) : 0.0f;
    };
    float right = axis(30), forward = -axis(31);
    // Preserve the Mac keyboard controls if the port emits WASD key events.
    if (keys.down(A)) right = -1.0f;
    if (keys.down(D)) right = 1.0f;
    if (keys.down(W)) forward = 1.0f;
    if (keys.down(S)) forward = -1.0f;
    const float norm = std::sqrt(right * right + forward * forward);
    if (norm <= deadzone) return {};
    const float strength = (std::min(norm, 1.0f) - deadzone) / (1.0f - deadzone);
    return {right / norm * strength, forward / norm * strength, strength};
}

bool padPressed(int control) {
    return call<bool>(hash::IS_CONTROL_PRESSED, 0, control) ||
           call<bool>(hash::IS_CONTROL_PRESSED, 2, control) ||
           call<bool>(hash::IS_DISABLED_CONTROL_PRESSED, 0, control) ||
           call<bool>(hash::IS_DISABLED_CONTROL_PRESSED, 2, control);
}

float length(Point3 p) { return std::sqrt(p.x * p.x + p.y * p.y + p.z * p.z); }
Point3 normalized(Point3 p) { const float d = length(p); return d > 0.001f ? scale(p, 1.0f / d) : Point3{}; }
Point3 cross(Point3 a, Point3 b) {
    return {a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x};
}

Point3 viewDirection() {
    const Vec3 rot = call<Vec3>(hash::GET_GAMEPLAY_CAM_ROT, 2);
    const float pitch = rot.x * kDeg;
    const float yaw = rot.z * kDeg;
    return normalized({-std::sin(yaw) * std::cos(pitch),
                       std::cos(yaw) * std::cos(pitch),
                       std::sin(pitch)});
}

Point3 cameraPosition() { return point(call<Vec3>(hash::GET_GAMEPLAY_CAM_COORD)); }
Point3 entityPosition(int entity) { return point(call<Vec3>(hash::GET_ENTITY_COORDS, entity, true)); }
Point3 entityVelocity(int entity) { return point(call<Vec3>(hash::GET_ENTITY_VELOCITY, entity)); }

float groundDistance(int ped) {
    const float height = call<float>(hash::GET_ENTITY_HEIGHT_ABOVE_GROUND, ped);
    if (std::isfinite(height) && height >= 0.0f && height < 1200.0f) return height;
    const Point3 p = entityPosition(ped);
    float groundZ = 0.0f;
    // Some iOS script builds report -1 while the ped's gravity is disabled.
    // A failed terrain query is NOT a landing; avoid an airborne explosion.
    if (call<bool>(hash::GET_GROUND_Z_FOR_3D_COORD,
                   p.x, p.y, p.z + 45.0f, &groundZ, false) &&
        std::isfinite(groundZ) && groundZ <= p.z + 1.0f)
        return std::max(0.0f, p.z - groundZ);
    return -1.0f;
}

Point3 groundImpactPoint(int ped) {
    Point3 result = entityPosition(ped);
    const float altitude = groundDistance(ped);
    // Keep dust and expanding rings on the road instead of hovering around
    // the ped's torso while GTA is resolving the last metre of descent.
    if (altitude >= 0.0f && altitude <= 3.0f)
        result.z -= altitude;
    return result;
}

void setVelocity(int entity, Point3 v) {
    call<>(hash::SET_ENTITY_VELOCITY, entity, v.x, v.y, v.z);
}

void explosion(Point3 p, int kind, float scaleFactor = 0.4f) {
    // No ownership attribution: single-player only; this is a gameplay-native call.
    call<>(hash::ADD_EXPLOSION, p.x, p.y, p.z, kind, scaleFactor, false, true, 0.0f, false);
}

void shake(float magnitude) {
    call<>(hash::SHAKE_GAMEPLAY_CAM, "SMALL_EXPLOSION_SHAKE", magnitude);
}

struct RayHit {
    bool hit = false;
    int entity = 0;
    Point3 point{};
};

RayHit traceRay(int ignorePed, float range) {
    static int pendingShape = 0;
    const Point3 from = cameraPosition();
    const Point3 to = add(from, scale(viewDirection(), range));
    int hit = 0, entity = 0;
    Vec3 end{}, normal{};
    int result = 0;
    if (pendingShape) {
        result = call<int>(hash::GET_SHAPE_TEST_RESULT, pendingShape, &hit, &end, &normal, &entity);
        // A result of 1 means the asynchronous ray is still in progress.
        // Starting a new ray here would discard its handle every frame,
        // causing missing hits and unnecessary native work on slower phones.
        if (result == 1) return {false, 0, to};
    }
    pendingShape = 0;
    pendingShape = call<int>(hash::START_SHAPE_TEST_LOS_PROBE,
        from.x, from.y, from.z, to.x, to.y, to.z, -1, ignorePed, 7);
    return {result == 2 && hit != 0, entity, result == 2 && hit ? point(end) : to};
}

void drawTriangle(Point3 a, Point3 b, Point3 c, int r, int g, int blue, int alpha) {
    call<>(hash::DRAW_POLY,
           a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z,
           r, g, blue, alpha);
}

// Real world-space geometry with a coloured translucent cylindrical shell and
// a brighter inner core. Unlike R13's screen-thin line bundle, its volume
// stays oriented correctly at any camera yaw/pitch without a custom shader.
// No user-supplied BeamModel is silently substituted; matching a proprietary
// GTA 3D beam mesh still requires that actual installed model resource.
void drawBeam(Point3 start, Point3 end, const LaserSpec& laser, bool volumetric) {
    const Point3 axis = sub(end, start);
    if (length(axis) < 0.10f) return;
    const Point3 tangent = normalized(axis);
    const Point3 upRef = std::fabs(tangent.z) < 0.91f ?
        Point3{0.0f, 0.0f, 1.0f} : Point3{0.0f, 1.0f, 0.0f};
    const Point3 sideA = normalized(cross(tangent, upRef));
    const Point3 sideB = normalized(cross(tangent, sideA));
    const int r = laser.r, g = laser.g, b = laser.b;
    const int spokes = std::min(laser.spokes, 8); // <=32 translucent triangles/eye
    const float radius = laser.spread * std::clamp(laser.layers / 4.0f, 0.5f, 1.7f);
    const float core = std::min(radius * 0.65f, laser.coreWidth);
    if (volumetric) {
        for (int i = 0; i < spokes; ++i) {
            const float a = (2.0f * kPi * static_cast<float>(i)) / spokes;
            const float z = (2.0f * kPi * static_cast<float>(i + 1)) / spokes;
            const Point3 offsetA = add(scale(sideA, std::cos(a) * radius),
                                       scale(sideB, std::sin(a) * radius));
            const Point3 offsetB = add(scale(sideA, std::cos(z) * radius),
                                       scale(sideB, std::sin(z) * radius));
            const Point3 p0 = add(start, offsetA), p1 = add(start, offsetB);
            const Point3 q0 = add(end, offsetA), q1 = add(end, offsetB);
            const int alpha = std::clamp(laser.glowAlpha + 13, 12, 95);
            drawTriangle(p0, q0, q1, r, g, b, alpha);
            drawTriangle(p0, q1, p1, r, g, b, alpha);
            // GTA's DRAW_POLY is one-sided. Draw the opposite face too so the
            // eye beam doesn't vanish when rotating the gameplay camera.
            drawTriangle(p0, q1, q0, r, g, b, alpha);
            drawTriangle(p0, p1, q1, r, g, b, alpha);
        }
    }
    for (Point3 offset : {Point3{}, scale(sideA, core), scale(sideA, -core),
                          scale(sideB, core), scale(sideB, -core)}) {
        const Point3 a = add(start, offset), z = add(end, offset);
        call<>(hash::DRAW_LINE, a.x, a.y, a.z, z.x, z.y, z.z,
               offset.x == 0.0f && offset.y == 0.0f && offset.z == 0.0f ? 255 : r,
               offset.x == 0.0f && offset.y == 0.0f && offset.z == 0.0f ? 245 : g,
               offset.x == 0.0f && offset.y == 0.0f && offset.z == 0.0f ? 235 : b, 255);
    }
    if (laser.glow && laser.impactGlowScale > 0.0f)
        call<>(hash::DRAW_LIGHT_WITH_RANGE, end.x, end.y, end.z, r, g, b,
               2.0f + laser.impactGlowScale * 15.0f, 2.2f);
}

void particle(const char* effect, Point3 location, float scaleFactor) {
    if (!call<bool>(hash::HAS_NAMED_PTFX_ASSET_LOADED, "core")) {
        call<>(hash::REQUEST_NAMED_PTFX_ASSET, "core");
        return;
    }
    call<>(hash::USE_PARTICLE_FX_ASSET, "core");
    call<>(hash::START_PARTICLE_FX_NON_LOOPED_AT_COORD, effect,
           location.x, location.y, location.z,
           0.0f, 0.0f, 0.0f, scaleFactor, false, false, false);
}

class Superman {
public:
    enum class Cooldown : std::size_t {
        Clap, GroundPound, SolarFlare, BulletTime, Takedown, Uppercut, Count
    };
    struct HeldHeat {
        bool active = false;
        std::uint32_t started = 0;
        std::uint32_t lockedUntil = 0;
    };
    bool enabled = false;
    bool flight = false;
    bool combat = false;
    bool bulletTime = false;
    bool xray = false;
    int beam = 0;
    int lockedTarget = 0;
    int carriedVehicle = 0;
    int frozenEntity = 0;
    std::uint32_t thawAt = 0;
    std::uint32_t lastAttack = 0;
    std::uint32_t lastBreathFx = 0;
    std::uint32_t spacePressedAt = 0;
    std::uint32_t flightStartedAt = 0;
    std::uint32_t landingStartedAt = 0;
    std::uint32_t lastSonicTrailFx = 0;
    bool autoLanding = false;
    bool landingCancelOnRelease = false;
    bool flightBoosting = false;
    FlightStick flightStick{};
    std::uint32_t lastLaserFx = 0;
    std::uint32_t lastLaserExplosion = 0;
    std::uint32_t lastChargeFx = 0;
    std::uint32_t activationStartedAt = 0;
    bool flightPoseActive = false;
    bool takeoffPosePending = false;
    bool supersonicFxActive = false;
    bool heldPoseActive = false;
    bool carryPoseActive = false;
    PowerAnim heldPower = PowerAnim::HeatVision;
    PowerAnim carryPower = PowerAnim::CarryIdle;
    std::uint32_t lastHeldPoseAttempt = 0;
    std::uint32_t lastCarryPoseAttempt = 0;
    std::uint32_t poseBlockUntil = 0;
    std::array<std::uint32_t, static_cast<std::size_t>(Cooldown::Count)> readyAt{};
    HeldHeat laserHeat{}, breathHeat{};
    bool groundFast = false;
    std::uint32_t lastFlightPoseAttempt = 0;
    // Flight animation is supported by the engine; these angles additionally
    // orient the player's torso while gliding and banking into a turn.
    float smoothedPitch = 0.0f;
    float smoothedBank = 0.0f;
    bool flightTiltApplied = false;
    struct ShockWave {
        Point3 center{};
        float maxRadius = 0.0f;
        std::uint32_t started = 0;
        std::uint32_t lifetime = 0;
        int r = 255, g = 255, b = 255;
        bool spherical = false;
        bool active = false;
    };
    std::array<ShockWave, 3> waves{};
    std::size_t nextWave = 0;
    std::string activeFlightDict;
    std::string activeFlightAnim;
    struct QueuedAction {
        bool waiting = false;
        bool playing = false;
        bool plunging = false;
        PowerAnim name = PowerAnim::ThunderClap;
        std::uint32_t started = 0;
        std::uint32_t requested = 0;
    } action{};
    Point3 smoothedFlight{};
    Config config{};
    Input input{};
    bool initialized = false;

    void tick() {
        input.sample();
        const int ped = call<int>(hash::PLAYER_PED_ID);
        if (!ped || !call<bool>(hash::DOES_ENTITY_EXIST, ped)) return;
        // This plugin is strictly for single-player ScriptHook gameplay.
        if (call<bool>(hash::NETWORK_IS_SESSION_STARTED)) {
            if (enabled) shutdown(ped);
            return;
        }
        if (!initialized) {
            initialized = true;
            if (config.startEnabled) toggle(ped);
        }
        const auto now = call<std::uint32_t>(hash::GET_GAME_TIMER);

        if (input.pressed(config.toggle)) toggle(ped);
        if (frozenEntity && now >= thawAt) {
            call<>(hash::FREEZE_ENTITY_POSITION, frozenEntity, false);
            frozenEntity = 0;
        }
        if (!enabled) return;

        // Stream assets before native playback. Loading is asynchronous on iOS.
        if (!call<bool>(hash::HAS_NAMED_PTFX_ASSET_LOADED, "core"))
            call<>(hash::REQUEST_NAMED_PTFX_ASSET, "core");
        processAction(ped, now);

        if (config.invincible) call<>(hash::SET_ENTITY_INVINCIBLE, ped, true);
        if (config.noRagdoll) call<>(hash::SET_PED_CAN_RAGDOLL, ped, false);
        if (config.noWantedLevel) {
            const int player = call<int>(hash::PLAYER_ID);
            call<>(hash::SET_PLAYER_WANTED_LEVEL, player, 0, false);
            call<>(hash::SET_PLAYER_WANTED_LEVEL_NOW, player, false);
        }

        if (input.pressed(config.combat)) combat = !combat;
        if (input.pressed(config.xray)) {
            xray = !xray;
            // Available native visual filter; not real occlusion-penetrating X-ray.
            call<>(hash::SET_NIGHTVISION, xray);
        }
        if (input.pressed(config.slowMotion)) {
            if (bulletTime) {
                bulletTime = false;
                call<>(hash::SET_TIME_SCALE, 1.0f);
                putCooldown(Cooldown::BulletTime, now, config.bulletTimeCooldownMs);
                supermanPlaySound("bullet_time", false);
            } else if (ready(Cooldown::BulletTime, now)) {
                bulletTime = true;
                call<>(hash::SET_TIME_SCALE, config.slowTimeScale);
                supermanPlaySound("bullet_time", false);
            }
        }

        // Move rate is a per-frame ped override; the player sprint multiplier
        // is a persistent player setting and MUST be restored after use.
        const bool fastOnFoot = !flight && !call<bool>(hash::IS_PED_IN_ANY_VEHICLE, ped, false) &&
                                (input.down(config.boost) || input.down(SHIFT));
        if (fastOnFoot != groundFast) {
            call<>(hash::SET_RUN_SPRINT_MULTIPLIER_FOR_PLAYER,
                   call<int>(hash::PLAYER_ID), fastOnFoot ? config.sprintMultiplier : 1.0f);
            groundFast = fastOnFoot;
        }
        if (fastOnFoot)
            call<>(hash::SET_PED_MOVE_RATE_OVERRIDE, ped,
                   std::clamp(1.0f + config.groundSpeedBoost / 45.0f, 1.0f, 1.8f));

        if (input.pressed(config.fly)) {
            spacePressedAt = now;
            if (flight && autoLanding) {
                autoLanding = false;
                landingCancelOnRelease = true;
            }
        }
        if (input.down(config.fly) && !flight) {
            call<>(hash::SET_SUPER_JUMP_THIS_FRAME, call<int>(hash::PLAYER_ID));
            if (now - spacePressedAt >= static_cast<std::uint32_t>(config.tapHoldMs) &&
                !call<bool>(hash::IS_PED_IN_ANY_VEHICLE, ped, false)) {
                flight = true;
                flightStartedAt = now;
                autoLanding = false;
                landingCancelOnRelease = false;
                smoothedFlight = entityVelocity(ped);
                call<>(hash::SET_ENTITY_HAS_GRAVITY, ped, false);
                takeoffPosePending = !playAnim(ped, config.anim(PowerAnim::Takeoff), 650, 0);
                poseBlockUntil = now + 530U;
                supermanPlaySound("takeoff", false);
                supermanPlaySound("flight_loop", true);
            }
        }
        if (!flight && input.released(config.fly) &&
            now - spacePressedAt < static_cast<std::uint32_t>(config.tapHoldMs) &&
            !call<bool>(hash::IS_PED_IN_ANY_VEHICLE, ped, false)) {
            // Source behavior: short tap is a vertical super-jump; long hold
            // is flight takeoff. The port previously omitted the real jump.
            Point3 launch = entityVelocity(ped);
            launch.z = std::max(launch.z, config.jumpPower);
            if (input.down(W)) launch = add(launch, scale(viewDirection(), config.jumpForward));
            setVelocity(ped, launch);
            playAnim(ped, config.anim(PowerAnim::SuperJump), 520, 0);
            supermanPlaySound("super_jump", false);
        }
        if (flight) {
            flightStick = readFlightStick(input, config.stickDeadzone);
            // A short tap while hovering lands the player using the existing
            // Fly button; the iPhone has no LCTRL virtual key by default.
            // Long holds still drive forward thrust instead of cancelling.
            if (input.released(config.fly)) {
                if (landingCancelOnRelease) landingCancelOnRelease = false;
                else if (now - flightStartedAt > 550U &&
                         now - spacePressedAt < static_cast<std::uint32_t>(config.tapHoldMs) &&
                         flightStick.magnitude < 0.20f) {
                    autoLanding = true;
                    landingStartedAt = now;
                }
            }
            if (takeoffPosePending && now < poseBlockUntil) {
                const int remaining = static_cast<int>(poseBlockUntil - now + 120U);
                if (playAnim(ped, config.anim(PowerAnim::Takeoff), remaining, 0))
                    takeoffPosePending = false;
            }
            if (now >= poseBlockUntil) takeoffPosePending = false;
            handleFlight(ped, now);
            if (flight) updateFlightPose(ped, now);
            if (flight) updateFlightTilt(ped, flightStick.magnitude > 0.15f);
        }
        updateHeldPose(ped, now);

        for (int i = 0; i < 5; ++i)
            if (input.pressed(config.beamKeys[i])) beam = i;
        if (input.pressed(config.cycle)) beam = (beam + 1) % 5;
        const bool laserAllowed = channelAllowed(laserHeat, input.down(config.laser),
            now, config.laserMaxMs, config.laserCooldownMs);
        if (laserAllowed) handleLaser(ped, now);
        const bool breathAllowed = channelAllowed(breathHeat,
            input.down(config.freezeBreath) || input.down(config.superBreath) || input.down(config.tornado),
            now, config.breathMaxMs, config.breathCooldownMs);
        if (input.down(config.freezeBreath) &&
            breathAllowed &&
            (input.pressed(config.freezeBreath) || now - lastBreathFx >= 125U)) {
            lastBreathFx = now;
            coneBreath(ped, true, input.pressed(config.freezeBreath));
        }
        if (input.down(config.superBreath) &&
            breathAllowed &&
            (input.pressed(config.superBreath) || now - lastBreathFx >= 125U)) {
            lastBreathFx = now;
            coneBreath(ped, false, input.pressed(config.superBreath));
        }
        if (input.pressed(config.clap) && ready(Cooldown::Clap, now) &&
            requestAction(PowerAnim::ThunderClap, now)) {
            putCooldown(Cooldown::Clap, now, config.clapCooldownMs);
        }
        if (input.down(config.tornado) && breathAllowed) tornado(ped, now);
        if (input.pressed(config.groundPound) && ready(Cooldown::GroundPound, now) &&
            requestAction(PowerAnim::GroundPound, now)) {
            putCooldown(Cooldown::GroundPound, now, config.groundCooldownMs);
        }
        if (input.pressed(config.lift))
            requestAction(carriedVehicle ? PowerAnim::Throw : PowerAnim::Lift, now);
        if (carriedVehicle) updateCarry(ped, now);
        if (input.pressed(config.solarFlare) && ready(Cooldown::SolarFlare, now)) {
            solarFlare(ped);
            putCooldown(Cooldown::SolarFlare, now, config.solarCooldownMs);
        }

        if (combat) handleCombat(ped, now);
        renderShockwaves(now);
    }

    void shutdown(int ped) {
        if (flight) supermanStopSound("flight_loop");
        stopSupersonicFx();
        if (bulletTime) call<>(hash::SET_TIME_SCALE, 1.0f);
        if (xray) call<>(hash::SET_NIGHTVISION, false);
        if (carriedVehicle) call<>(hash::FREEZE_ENTITY_POSITION, carriedVehicle, false);
        if (frozenEntity) call<>(hash::FREEZE_ENTITY_POSITION, frozenEntity, false);
        if (groundFast) call<>(hash::SET_RUN_SPRINT_MULTIPLIER_FOR_PLAYER,
                                call<int>(hash::PLAYER_ID), 1.0f);
        if (ped && config.invincible) call<>(hash::SET_ENTITY_INVINCIBLE, ped, false);
        if (ped && config.noRagdoll) call<>(hash::SET_PED_CAN_RAGDOLL, ped, true);
        if (ped) call<>(hash::SET_ENTITY_HAS_GRAVITY, ped, true);
        stopHeldPose(ped);
        stopCarryPose(ped);
        stopFlightPose(ped);
        resetFlightTilt(ped);
        enabled = flight = combat = bulletTime = xray = false;
        autoLanding = landingCancelOnRelease = flightBoosting = false;
        flightStick = {};
        readyAt.fill(0);
        laserHeat = breathHeat = {};
        groundFast = false;
        action = {};
        takeoffPosePending = false;
        lastChargeFx = 0;
        poseBlockUntil = lastFlightPoseAttempt = 0;
        carriedVehicle = frozenEntity = lockedTarget = 0;
        waves = {};
        nextWave = 0;
    }

private:
    bool ready(Cooldown which, std::uint32_t now) const {
        return !config.cooldownsEnabled || now >= readyAt[static_cast<std::size_t>(which)];
    }

    void putCooldown(Cooldown which, std::uint32_t now, std::uint32_t duration) {
        if (config.cooldownsEnabled)
            readyAt[static_cast<std::size_t>(which)] = now + duration;
    }

    bool channelAllowed(HeldHeat& heat, bool held, std::uint32_t now,
                        std::uint32_t maxMs, std::uint32_t lockMs) const {
        if (!held) { heat.active = false; return false; }
        if (!config.overheatEnabled || maxMs == 0U) return true;
        if (now < heat.lockedUntil) return false;
        if (!heat.active) {
            heat.active = true;
            heat.started = now;
        }
        if (now - heat.started >= maxMs) {
            heat.active = false;
            heat.lockedUntil = now + lockMs;
            return false;
        }
        return true;
    }
    void notify(bool turnedOn) const {
        if (!config.notifications) return;
        call<>(hash::BEGIN_TEXT_COMMAND_THEFEED_POST, "STRING");
        call<>(hash::ADD_TEXT_COMPONENT_SUBSTRING_PLAYER_NAME,
               turnedOn ? "~b~Superman mode ~g~ENABLED~s~" :
                          "~b~Superman mode ~r~DISABLED~s~");
        call<int>(hash::END_TEXT_COMMAND_THEFEED_POST_TICKER, false, false);
    }

    bool playAnim(int ped, const Animation& anim, int duration, int flags) {
        if (!call<bool>(hash::HAS_ANIM_DICT_LOADED, anim.dict.c_str())) {
            call<>(hash::REQUEST_ANIM_DICT, anim.dict.c_str());
            return false;
        }
        call<>(hash::TASK_PLAY_ANIM, ped, anim.dict.c_str(), anim.clip.c_str(),
               4.0f, -4.0f, duration, flags, 1.0f, false, false, false);
        return true;
    }

    bool requestAction(PowerAnim name, std::uint32_t now) {
        // Don't interrupt an in-progress animation or slam halfway through.
        // Cancelled actions previously consumed their cooldown with no effect.
        if (action.waiting) return false;
        action = {true, false, false, name, 0, now};
        lastChargeFx = 0;
        const Animation& clip = config.anim(name);
        call<>(hash::REQUEST_ANIM_DICT, clip.dict.c_str());
        return true;
    }

    void animateCharge(int ped, std::uint32_t now, const Animation& clip) {
        if (!config.actionChargeGlow || !action.playing || action.plunging ||
            (action.name != PowerAnim::ThunderClap &&
             action.name != PowerAnim::GroundPound)) return;
        const float progress = clip.impactMs == 0U ? 1.0f :
            std::clamp(static_cast<float>(now - action.started) /
                       static_cast<float>(clip.impactMs), 0.0f, 1.0f);
        const bool slam = action.name == PowerAnim::GroundPound;
        const Point3 left = point(call<Vec3>(hash::GET_PED_BONE_COORDS,
            ped, 18905, 0.0f, 0.0f, 0.0f));
        const Point3 right = point(call<Vec3>(hash::GET_PED_BONE_COORDS,
            ped, 57005, 0.0f, 0.0f, 0.0f));
        for (const Point3 hand : {left, right})
            call<>(hash::DRAW_LIGHT_WITH_RANGE, hand.x, hand.y, hand.z,
                   slam ? 255 : 170, slam ? 142 : 215, slam ? 90 : 255,
                   0.7f + progress * 1.2f, 0.55f + progress * 0.6f);
        // A small pair of hand sparks follows the animation; never spawn
        // particles every frame (the user's earlier build had poor FPS).
        if (now - lastChargeFx >= 190U) {
            lastChargeFx = now;
            particle("bul_carmetal", left, 0.17f);
            particle("bul_carmetal", right, 0.17f);
        }
    }

    void processAction(int ped, std::uint32_t now) {
        if (!action.waiting) return;
        const Animation& clip = config.anim(action.name);
        if (action.plunging) {
            const float altitude = call<float>(hash::GET_ENTITY_HEIGHT_ABOVE_GROUND, ped);
            if (altitude < 0.0f || altitude > 1.5f) {
                if (now - action.started >= 3200U) {
                    // Prevent a permanent locked downward pose if the ground
                    // cannot be reached (water, broken collision or teleport).
                    action = {};
                    poseBlockUntil = 0;
                }
                return;
            }
            stopFlying(ped);
            action.plunging = false;
            action.playing = false;
            action.requested = now;
            poseBlockUntil = now + clip.impactMs + 300U;
            return;
        }
        if (!action.playing) {
            if (now - action.requested > 2200U) {
                // A dictionary that never arrives must not consume the
                // cooldown of a power that never actually played.
                if (action.name == PowerAnim::ThunderClap)
                    readyAt[static_cast<std::size_t>(Cooldown::Clap)] = 0;
                if (action.name == PowerAnim::GroundPound)
                    readyAt[static_cast<std::size_t>(Cooldown::GroundPound)] = 0;
                action = {};
                return;
            }
            if (action.name == PowerAnim::GroundPound && flight) {
                const float altitude = call<float>(hash::GET_ENTITY_HEIGHT_ABOVE_GROUND, ped);
                if (altitude > 1.5f) {
                    // Descend first, THEN play the grounded slam animation.
                    // Previously the attack pose finished during the dive.
                    action.plunging = action.playing = true;
                    action.started = now;
                    poseBlockUntil = now + 3200U;
                    stopFlightPose(ped);
                    resetFlightTilt(ped);
                    const Animation dive{config.flyDict, config.flyAnim, 0};
                    if (playAnim(ped, dive, -1, 1)) {
                        flightPoseActive = true;
                        activeFlightDict = dive.dict;
                        activeFlightAnim = dive.clip;
                    }
                    return;
                }
                stopFlying(ped);
            }
            if (!playAnim(ped, clip, static_cast<int>(clip.impactMs + 330U), 0)) return;
            resetFlightTilt(ped);
            action.started = now;
            action.playing = true;
            poseBlockUntil = now + clip.impactMs + 300U;
            return;
        }
        animateCharge(ped, now, clip);
        if (now - action.started < clip.impactMs) return;
        if (action.name == PowerAnim::ThunderClap) thunderClap(ped);
        if (action.name == PowerAnim::GroundPound) groundPound(ped);
        if (action.name == PowerAnim::Lift || action.name == PowerAnim::Throw)
            carryOrThrow(ped);
        action = {};
    }

    void stopFlightPose(int ped) {
        if (ped && flightPoseActive && !activeFlightDict.empty())
            call<>(hash::STOP_ANIM_TASK, ped, activeFlightDict.c_str(), activeFlightAnim.c_str(), 2.0f);
        flightPoseActive = false;
        activeFlightDict.clear();
        activeFlightAnim.clear();
    }

    void stopFlying(int ped) {
        if (!flight) return;
        flight = false;
        autoLanding = false;
        flightBoosting = false;
        landingCancelOnRelease = false;
        flightStick = {};
        smoothedFlight = {};
        takeoffPosePending = false;
        supermanStopSound("flight_loop");
        stopSupersonicFx();
        stopFlightPose(ped);
        resetFlightTilt(ped);
        call<>(hash::SET_ENTITY_HAS_GRAVITY, ped, true);
    }

    void landFromFlight(int ped) {
        const float impactSpeed = std::max(0.0f, -smoothedFlight.z);
        stopFlying(ped);
        setVelocity(ped, {});
        playAnim(ped, config.anim(PowerAnim::Landing), 800, 0);
        supermanPlaySound("landing_shockwave", false);
        const Point3 p = groundImpactPoint(ped);
        // Even a controlled touchdown needs visible ground dust/rings. Only
        // strong landings push away nearby NPCs and vehicles.
        shockRing(p, std::min(config.shockRadius, 5.0f), "exp_grd_flare");
        addShockwave(add(p, {0.0f, 0.0f, 0.09f}), 5.5f,
                     480U, 245, 225, 190);
        shake(0.22f);
        if (impactSpeed < config.landingShockwaveMinSpeed) return;
        shockRing(p, config.shockRadius, "exp_grd_flare");
        addShockwave(add(p, {0.0f, 0.0f, 0.13f}), config.shockRadius,
                     430U, 255, 232, 196);
        radialImpulse(ped, p, config.shockRadius, config.landingForce,
                      config.landingLift);
        shake(0.75f);
    }

    void resetFlightTilt(int ped) {
        if (ped && flightTiltApplied) {
            const float heading = call<float>(hash::GET_ENTITY_HEADING, ped);
            call<>(hash::SET_ENTITY_ROTATION, ped, 0.0f, 0.0f, heading, 2, true);
        }
        smoothedPitch = smoothedBank = 0.0f;
        flightTiltApplied = false;
    }

    void updateFlightTilt(int ped, bool forwardMotion) {
        if (!config.flightBodyTilt || !forwardMotion ||
            (action.waiting && action.playing) || !flightPoseActive) {
            resetFlightTilt(ped);
            return;
        }
        const Vec3 cam = call<Vec3>(hash::GET_GAMEPLAY_CAM_ROT, 2);
        // Camera pitch must NOT rotate the actor (and consequently the iOS
        // follow camera) toward the sky. Tilt is a small steering animation.
        const float pitch = std::clamp(-flightStick.forward * 8.0f * config.pitchScale,
                                       -9.0f, 9.0f);
        const float turn = std::clamp(-flightStick.right * config.bankAngle * 0.40f,
                                       -12.0f, 12.0f);
        smoothedPitch += (pitch - smoothedPitch) * 0.20f;
        smoothedBank += (turn - smoothedBank) * 0.20f;
        call<>(hash::SET_ENTITY_ROTATION, ped, smoothedPitch, smoothedBank,
               cam.z, 2, true);
        flightTiltApplied = true;
    }

    void addShockwave(Point3 center, float radius, std::uint32_t lifetime,
                      int r, int g, int b, bool spherical = false) {
        if (!config.shockwaveMeshes) return;
        waves[nextWave] = {center, std::min(radius, 70.0f),
                           call<std::uint32_t>(hash::GET_GAME_TIMER),
                           lifetime, r, g, b, spherical, true};
        nextWave = (nextWave + 1) % waves.size();
    }

    void ringPlane(const ShockWave& wave, Point3 axisX, Point3 axisY,
                   float radius, int alpha) {
        // World-space annulus: bounded 8 wedges, 4 polygons each. Both
        // windings keep it visible from above and below on a flying camera.
        constexpr int segments = 8;
        const float width = std::clamp(radius * 0.10f, 0.30f, 1.80f);
        const float inner = std::max(0.01f, radius - width);
        auto position = [&](float angle, float distance) {
            return add(wave.center, add(scale(axisX, std::cos(angle) * distance),
                                        scale(axisY, std::sin(angle) * distance)));
        };
        for (int i = 0; i < segments; ++i) {
            const float a = 2.0f * kPi * static_cast<float>(i) / segments;
            const float b = 2.0f * kPi * static_cast<float>(i + 1) / segments;
            const Point3 aInner = position(a, inner), aOuter = position(a, radius);
            const Point3 bInner = position(b, inner), bOuter = position(b, radius);
            drawTriangle(aInner, aOuter, bOuter, wave.r, wave.g, wave.b, alpha);
            drawTriangle(aInner, bOuter, bInner, wave.r, wave.g, wave.b, alpha);
            drawTriangle(aInner, bOuter, aOuter, wave.r, wave.g, wave.b, alpha);
            drawTriangle(aInner, bInner, bOuter, wave.r, wave.g, wave.b, alpha);
        }
    }

    void renderShockwaves(std::uint32_t now) {
        if (!config.shockwaveMeshes) return;
        for (auto& wave : waves) {
            if (!wave.active) continue;
            const std::uint32_t elapsed = now - wave.started;
            if (elapsed >= wave.lifetime || wave.lifetime == 0U) {
                wave.active = false;
                continue;
            }
            const float progress = std::clamp(static_cast<float>(elapsed) /
                                        static_cast<float>(wave.lifetime), 0.0f, 1.0f);
            const float radius = std::max(0.10f, progress * wave.maxRadius);
            const int alpha = static_cast<int>(65.0f * (1.0f - progress));
            const Point3 x{1.0f, 0.0f, 0.0f}, y{0.0f, 1.0f, 0.0f};
            const Point3 z{0.0f, 0.0f, 1.0f};
            ringPlane(wave, x, y, radius, alpha);
            if (wave.spherical) {
                ringPlane(wave, x, z, radius, alpha / 2);
                ringPlane(wave, y, z, radius, alpha / 2);
            }
        }
    }

    void drawSupersonicTrail(int ped) {
        if (!config.supersonicTrail || length(smoothedFlight) < 25.0f) return;
        const Point3 direction = normalized(smoothedFlight);
        const Point3 side = normalized({direction.y, -direction.x, 0.0f});
        if (length(side) < 0.5f) return;
        const Point3 center = add(entityPosition(ped), {0.0f, 0.0f, 0.65f});
        const float speedRatio = std::clamp(length(smoothedFlight) / 170.0f, 0.0f, 1.0f);
        const float trailLength = 1.5f + speedRatio * 4.0f;
        // Two translucent tapered wakes trail the shoulders, not the feet.
        // No particle assets or per-frame allocation, and no opaque cone.
        for (const float sideSign : {-1.0f, 1.0f}) {
            const Point3 shoulder = add(center, scale(side, sideSign * 0.40f));
            const Point3 tail = sub(shoulder, scale(direction, trailLength));
            const Point3 edgeA = add(shoulder, scale(side, 0.10f));
            const Point3 edgeB = sub(shoulder, scale(side, 0.10f));
            drawTriangle(edgeA, edgeB, tail, 181, 226, 255, 32);
            drawTriangle(edgeB, edgeA, tail, 181, 226, 255, 32);
        }
    }

    void stopSupersonicFx() {
        if (supersonicFxActive && !config.supersonicPostFx.empty())
            call<>(hash::ANIMPOSTFX_STOP, config.supersonicPostFx.c_str());
        supersonicFxActive = false;
        boostPreviously = false;
    }

    void stopHeldPose(int ped) {
        if (heldPoseActive && ped) {
            const Animation& clip = config.anim(heldPower);
            call<>(hash::STOP_ANIM_TASK, ped, clip.dict.c_str(), clip.clip.c_str(), 2.0f);
        }
        heldPoseActive = false;
    }

    void stopCarryPose(int ped) {
        if (carryPoseActive && ped) {
            const Animation& clip = config.anim(carryPower);
            call<>(hash::STOP_ANIM_TASK, ped, clip.dict.c_str(), clip.clip.c_str(), 2.0f);
        }
        carryPoseActive = false;
    }

    void updateHeldPose(int ped, std::uint32_t now) {
        // The original has specific arm poses for heat vision and breath.
        // Keep full-body flight anim intact while permitting the powers in air.
        if (flight || (action.waiting && action.playing && now < poseBlockUntil)) {
            stopHeldPose(ped);
            return;
        }
        const bool firing = input.down(config.laser);
        const bool breathing = input.down(config.freezeBreath) || input.down(config.superBreath);
        const bool spinning = input.down(config.tornado);
        if (!firing && !breathing && !spinning) { stopHeldPose(ped); return; }
        const PowerAnim wanted = firing ? PowerAnim::HeatVision :
                                 breathing ? PowerAnim::Breath : PowerAnim::Tornado;
        if (heldPoseActive && heldPower != wanted) stopHeldPose(ped);
        heldPower = wanted;
        if (heldPoseActive && now - lastHeldPoseAttempt < 500U) return;
        const Animation& clip = config.anim(wanted);
        if (heldPoseActive && call<bool>(hash::IS_ENTITY_PLAYING_ANIM, ped,
                                        clip.dict.c_str(), clip.clip.c_str(), 3)) return;
        // 48 = upper body + secondary, preserving the player's legs and walking.
        if (playAnim(ped, clip, -1, 48)) {
            heldPoseActive = true;
            lastHeldPoseAttempt = now;
        }
    }

    void updateFlightPose(int ped, std::uint32_t now) {
        if (now < poseBlockUntil || (action.waiting && action.playing)) return;
        const bool moving = flightStick.magnitude > 0.15f || flightBoosting ||
                            input.down(config.descend) || input.down(CTRL) || autoLanding;
        const bool fast = flightBoosting;
        const std::string& wantedDict = fast ? config.supersonicDict :
                                        moving ? config.flyDict : config.hoverDict;
        const std::string& wantedAnim = fast ? config.supersonicAnim :
                                        moving ? config.flyAnim : config.hoverAnim;
        const bool changed = activeFlightDict != wantedDict || activeFlightAnim != wantedAnim;
        if (!changed && now - lastFlightPoseAttempt < 550U) return;
        if (!changed && call<bool>(hash::IS_ENTITY_PLAYING_ANIM, ped,
                                  wantedDict.c_str(), wantedAnim.c_str(), 3)) return;
        if (!call<bool>(hash::HAS_ANIM_DICT_LOADED, wantedDict.c_str())) {
            call<>(hash::REQUEST_ANIM_DICT, wantedDict.c_str());
            return;
        }
        if (changed) stopFlightPose(ped);
        // AF_LOOPING only (1): original R11 used 49 = upper-body + secondary,
        // leaving legs in an unrelated ground animation during flight.
        call<>(hash::TASK_PLAY_ANIM, ped, wantedDict.c_str(), wantedAnim.c_str(),
               3.0f, -3.0f, -1, 1, 1.0f, false, false, false);
        activeFlightDict = wantedDict;
        activeFlightAnim = wantedAnim;
        flightPoseActive = true;
        lastFlightPoseAttempt = now;
    }

    void toggle(int ped) {
        if (enabled) shutdown(ped);
        else {
            enabled = true;
            activationStartedAt = call<std::uint32_t>(hash::GET_GAME_TIMER);
            // Preload only the shared flight/action dictionaries. A missing
            // dictionary at takeoff used to leave an invisible pose gap on
            // slower iPhones until the next flight animation became ready.
            const std::array<const std::string*, 7> dicts{{
                &config.hoverDict, &config.flyDict, &config.supersonicDict,
                &config.anim(PowerAnim::Takeoff).dict,
                &config.anim(PowerAnim::Landing).dict,
                &config.anim(PowerAnim::ThunderClap).dict,
                &config.anim(PowerAnim::GroundPound).dict
            }};
            for (std::size_t i = 0; i < dicts.size(); ++i) {
                const std::string& name = *dicts[i];
                if (name.empty()) continue;
                bool repeated = false;
                for (std::size_t j = 0; j < i; ++j)
                    repeated = repeated || name == *dicts[j];
                if (!repeated && !call<bool>(hash::HAS_ANIM_DICT_LOADED, name.c_str()))
                    call<>(hash::REQUEST_ANIM_DICT, name.c_str());
            }
            supermanPlaySound("super_jump", false);
        }
        notify(enabled);
    }

    void handleFlight(int ped, std::uint32_t now) {
        if (action.waiting && action.playing && action.name == PowerAnim::GroundPound) {
            // Direct vertical plunge; the impact animation and shockwave are
            // handled by processAction only when the character reaches ground.
            setVelocity(ped, {smoothedFlight.x * 0.15f, smoothedFlight.y * 0.15f, -48.0f});
            return;
        }
        // The gameplay camera may point vertically on iPhone. Steering uses
        // camera YAW only, so a forward stick movement never launches the ped
        // straight into the sky just because the camera follows the avatar.
        const Vec3 camera = call<Vec3>(hash::GET_GAMEPLAY_CAM_ROT, 2);
        const float yaw = camera.z * kDeg;
        const Point3 forward{-std::sin(yaw), std::cos(yaw), 0.0f};
        const Point3 right{forward.y, -forward.x, 0.0f};
        Point3 move = add(scale(forward, flightStick.forward),
                          scale(right, flightStick.right));
        const bool flyHeld = input.down(config.fly);
        const bool thrust = flyHeld && now - flightStartedAt > 550U;
        // Keep TamedMods' controller mappings: RB/cover 44 = descend, and
        // Sprint 21 = boost. On iOS the regular Sprint button can activate it.
        const bool manualDescend = input.down(config.descend) || input.down(CTRL) ||
                                   padPressed(44);
        if (manualDescend && !autoLanding) {
            autoLanding = true;
            landingStartedAt = now;
        }
        if (autoLanding && flightStick.magnitude > 0.0f)
            move = scale(move, 0.32f); // steer gently while descending
        // Once in the air, holding Fly without moving the stick means "fly
        // forward fast". The short initial takeoff window is still vertical.
        if (thrust && !autoLanding && flightStick.magnitude < 0.10f)
            move = forward;
        const bool moving = length(move) > 0.10f;
        const bool boost = !autoLanding && moving &&
                           (thrust || input.down(config.boost) ||
                            input.down(SHIFT) || padPressed(21));
        flightBoosting = boost;
        const float speed = boost ? config.supersonicSpeed : config.cruiseSpeed;
        Point3 target = scale(move, speed);
        const bool takeoffAscent = flyHeld && !thrust &&
                                   flightStick.magnitude < 0.10f && !autoLanding;
        if (autoLanding)
            target.z = -config.autoLandingSpeed;
        else if (manualDescend)
            target.z = -config.verticalSpeed;
        else if (takeoffAscent)
            target.z = config.verticalSpeed;
        else
            target.z = 0.0f;
        const float smoothing = std::clamp(config.acceleration * 2.0f, 0.02f, 0.95f);
        smoothedFlight = add(scale(smoothedFlight, 1.0f - smoothing), scale(target, smoothing));
        if (!moving && !autoLanding && !takeoffAscent)
            smoothedFlight = scale(smoothedFlight, 1.0f - config.hoverDrag);
        setVelocity(ped, smoothedFlight);
        // Face the actual movement vector, not an unrelated walking heading.
        if (moving)
            call<>(hash::SET_ENTITY_HEADING, ped,
                   -std::atan2(move.x, move.y) / kDeg);
        const bool supersonic = boost;
        if (supersonic && !boostPreviously && config.sonicBoom) {
            supermanPlaySound("sonic_boom", false);
            if (config.sonicCameraShake) shake(0.35f);
            addShockwave(entityPosition(ped), 4.0f, 220U, 185, 225, 255, true);
        }
        if (supersonic && !supersonicFxActive && !config.supersonicPostFx.empty()) {
            call<>(hash::ANIMPOSTFX_PLAY, config.supersonicPostFx.c_str(), 0, true);
            supersonicFxActive = true;
        }
        if (!supersonic && supersonicFxActive) stopSupersonicFx();
        boostPreviously = supersonic;
        if (supersonic) {
            drawSupersonicTrail(ped);
            if (now - lastSonicTrailFx >= 850U) {
                lastSonicTrailFx = now;
                const Point3 tail = sub(entityPosition(ped), scale(normalized(move), 2.2f));
                particle("ent_dst_gen_gobstop", tail, 0.65f);
                addShockwave(tail, 3.0f, 260U, 195, 225, 255, true);
            }
        }
        if (autoLanding || manualDescend ||
            (now - flightStartedAt > 1100U && !flyHeld && !moving)) {
            const float altitude = groundDistance(ped);
            if (altitude >= 0.0f && altitude < 1.8f &&
                now - flightStartedAt > 500U) {
                landFromFlight(ped);
            } else if (autoLanding && now - landingStartedAt > 10000U &&
                       altitude < 0.0f) {
                // If terrain natives are unavailable (e.g. water or remote
                // unloaded terrain), return physics control to GTA. Do not
                // create a false impact shockwave in the air.
                stopFlying(ped);
                setVelocity(ped, {0.0f, 0.0f, -8.0f});
            }
        }
    }

    void handleLaser(int ped, std::uint32_t now) {
        const LaserSpec& mode = config.lasers[static_cast<std::size_t>(beam)];
        const RayHit hit = traceRay(ped, mode.range);
        // Head-bone local offsets instead of world-X offsets: the two beams
        // should rotate with the head, even when the camera faces east/west.
        const Point3 eyeLeft = point(call<Vec3>(hash::GET_PED_BONE_COORDS,
            ped, 31086, -mode.eyeSeparation * 0.5f, mode.eyeForward, 0.08f));
        const Point3 eyeRight = point(call<Vec3>(hash::GET_PED_BONE_COORDS,
            ped, 31086, mode.eyeSeparation * 0.5f, mode.eyeForward, 0.08f));
        const bool due = now - lastLaserFx >= std::max(90U, mode.pulseMs);
        // Preserve visible pulse for ~100ms instead of rendering for a single
        // frame every 320ms, which was barely perceptible on an iPhone.
        const bool showBeam = mode.pulseMs == 0U || due ||
                              now - lastLaserFx <= 100U;
        if (showBeam) {
            drawBeam(eyeLeft, hit.point, mode, config.volumetricBeams);
            drawBeam(eyeRight, hit.point, mode, config.volumetricBeams);
            if (mode.muzzleGlowScale > 0.0f) {
                const Point3 middle = scale(add(eyeLeft, eyeRight), 0.5f);
                call<>(hash::DRAW_LIGHT_WITH_RANGE,
                       middle.x, middle.y, middle.z, mode.r, mode.g, mode.b,
                       mode.muzzleGlowScale * 4.0f, 1.2f);
            }
        }

        if (!due) return;
        lastLaserFx = now;
        particle(mode.particleName.c_str(), hit.point, mode.particleScale);
        if (hit.hit && hit.entity && hit.entity != ped) {
            if (beam == 4) {
                if (frozenEntity && frozenEntity != hit.entity)
                    call<>(hash::FREEZE_ENTITY_POSITION, frozenEntity, false);
                call<>(hash::FREEZE_ENTITY_POSITION, hit.entity, true);
                frozenEntity = hit.entity;
                thawAt = now + 5000;
            } else if (mode.damagePerSecond > 0.0f &&
                       call<bool>(hash::IS_ENTITY_A_PED, hit.entity)) {
                call<>(hash::APPLY_DAMAGE_TO_PED, hit.entity,
                       static_cast<int>(std::max(1.0f, mode.damagePerSecond * 0.09f)),
                       false, 0, 0);
            } else if (call<bool>(hash::IS_ENTITY_A_VEHICLE, hit.entity)) {
                if (beam == 0 || beam == 1 || beam == 2)
                    call<>(hash::SET_VEHICLE_ENGINE_HEALTH, hit.entity, 10.0f);
            }
        }
        const std::uint32_t explosionInterval = beam == 1 ? 250U : beam == 2 ? 500U : 320U;
        if (hit.hit && mode.explosionType >= 0 &&
            now - lastLaserExplosion >= explosionInterval) {
            lastLaserExplosion = now;
            // Preserve the source explosion *type*, but reduce damage scale
            // until the iOS mobile effect budget can be measured on-device.
            explosion(hit.point, mode.explosionType, 0.1f);
        }
        static const char* const wav[5] = {
            "heat_vision", "plasma_arc", "solar_flare_emp", "pulse_cannon", "cryo_beam"};
        if (!input.was[config.laser]) supermanPlaySound(wav[beam], false);
    }

    void pushTarget(int ped, float force, float lift) {
        const RayHit hit = traceRay(ped, 30.0f);
        if (!hit.hit || !hit.entity || hit.entity == ped) return;
        const Point3 dir = viewDirection();
        call<>(hash::APPLY_FORCE_TO_ENTITY, hit.entity, 1,
               dir.x * force, dir.y * force, dir.z * force + lift,
               0.0f, 0.0f, 0.0f, 0, false, true, true, false, true);
    }

    // Spatially sample a *bounded* set of nearby peds/vehicles. GTA's
    // GET_PED_NEARBY_PEDS uses a version-sensitive sizeAndPeds buffer; writing
    // into an incorrectly sized array could corrupt the iOS game process.
    // This is an intentionally approximate radial force, not full world-pool
    // enumeration: deduplicated hits keep animation/physics cost predictable.
    int radialImpulse(int self, Point3 origin, float radius, float force,
                      float upward, bool knockdown = true) {
        if (radius < 0.5f || force <= 0.0f) return 0;
        std::array<int, 28> affected{};
        int count = 0;
        auto affect = [&](int entity) {
            if (!entity || entity == self || !call<bool>(hash::DOES_ENTITY_EXIST, entity)) return;
            for (int i = 0; i < count; ++i)
                if (affected[static_cast<std::size_t>(i)] == entity) return;
            if (count >= static_cast<int>(affected.size())) return;
            const Point3 delta = sub(entityPosition(entity), origin);
            const float distance = length(delta);
            if (distance > radius || distance < 0.05f) return;
            const bool isPed = call<bool>(hash::IS_ENTITY_A_PED, entity);
            const bool isVehicle = call<bool>(hash::IS_ENTITY_A_VEHICLE, entity);
            if (!isPed && !isVehicle) return;
            affected[static_cast<std::size_t>(count++)] = entity;
            const float attenuation = std::clamp(1.0f - distance / radius, 0.20f, 1.0f);
            const Point3 away = normalized({delta.x, delta.y, 0.0f});
            // Knock the target loose before applying physical impulse; on
            // standing NPCs a force alone may be damped by locomotion AI.
            if (isPed && knockdown)
                call<bool>(hash::SET_PED_TO_RAGDOLL, entity, 500, 1000, 0,
                           false, false, false);
            call<>(hash::APPLY_FORCE_TO_ENTITY, entity, 1,
                   away.x * force * attenuation, away.y * force * attenuation,
                   upward * attenuation, 0.0f, 0.0f, 0.0f,
                   0, false, true, true, false, true);
        };

        constexpr std::array<Point3, 9> samplePoints{{
            {0.0f, 0.0f, 0.0f}, {0.48f, 0.0f, 0.0f}, {-0.48f, 0.0f, 0.0f},
            {0.0f, 0.48f, 0.0f}, {0.0f, -0.48f, 0.0f},
            {0.67f, 0.67f, 0.0f}, {-0.67f, 0.67f, 0.0f},
            {0.67f, -0.67f, 0.0f}, {-0.67f, -0.67f, 0.0f}
        }};
        const float queryRadius = radius * 0.45f;
        for (const Point3 offset : samplePoints) {
            const Point3 pos = add(origin, scale(offset, radius));
            // Include stationary & wandering peds without accepting the
            // player's own ped or entities outside the requested circle.
            affect(call<int>(hash::GET_RANDOM_PED_AT_COORD,
                             pos.x, pos.y, pos.z, queryRadius, queryRadius,
                             std::min(radius * 0.45f, 5.0f), -1));
            int closest = 0;
            if (call<bool>(hash::GET_CLOSEST_PED,
                    pos.x, pos.y, pos.z, queryRadius,
                    true, false, &closest, false, false, -1)) affect(closest);
            affect(call<int>(hash::GET_CLOSEST_VEHICLE,
                             pos.x, pos.y, pos.z, queryRadius, 0, 127));
        }
        // Preserve the old ray-target behavior if the spatial sampler finds
        // nothing (e.g. mission actors are not returned by random-ped natives).
        if (count == 0) pushTarget(self, force, upward);
        return count;
    }

    void shockRing(Point3 center, float radius, const char* effect) {
        // Low fixed budget: three spaced puffs plus the origin. Using a single
        // particle at the user's feet was visually too easy to miss.
        particle(effect, center, 1.5f);
        for (int step = 0; step < 3; ++step) {
            const float radians = (static_cast<float>(step) / 3.0f) * 2.0f * kPi;
            particle(effect, add(center, {std::cos(radians) * radius * 0.55f,
                                          std::sin(radians) * radius * 0.55f, 0.1f}), 1.1f);
        }
    }

    void coneBreath(int ped, bool freezing, bool firstPress) {
        const Point3 forward = viewDirection();
        const Point3 start = add(point(call<Vec3>(hash::GET_PED_BONE_COORDS,
                                                  ped, 31086, 0.0f, 0.15f, 0.0f)),
                                 scale(forward, 0.40f));
        const float range = freezing ? config.freezeRange : config.superBreathRange;
        const char* effect = freezing ? config.freezeFx.c_str() : "exp_grd_bzgas_smoke";
        const Point3 right = normalized({forward.y, -forward.x, 0.0f});
        constexpr std::array<float, 3> strides{{0.25f, 0.55f, 0.85f}};
        // Approximate the original 3D cone with longitudinal puffs rather
        // than the R12 single target puff. At most 3 per 125 ms interval.
        for (std::size_t i = 0; i < strides.size(); ++i) {
            const float fraction = strides[i];
            Point3 pos = add(start, scale(forward, range * fraction));
            if (i == 1) pos = add(pos, scale(right, 0.65f));
            if (i == 2) pos = sub(pos, scale(right, 1.1f));
            particle(effect, pos, 0.55f + fraction);
        }

        // Sample along the beam for multiple opponents. No global entity-pool
        // traversal and no unmanaged script memory. Limit candidates and
        // explicitly reject anything outside a 32-degree cone (plan view).
        const Point3 forwardFlat = normalized({forward.x, forward.y, 0.0f});
        std::array<int, 8> seen{};
        int seenCount = 0;
        auto affect = [&](int entity) {
            if (!entity || entity == ped || !call<bool>(hash::DOES_ENTITY_EXIST, entity)) return;
            for (int i = 0; i < seenCount; ++i)
                if (seen[static_cast<std::size_t>(i)] == entity) return;
            const Point3 delta = sub(entityPosition(entity), start);
            const float distance = length(delta);
            if (distance < 0.20f || distance > range) return;
            const Point3 targetFlat = normalized({delta.x, delta.y, 0.0f});
            if (forwardFlat.x * targetFlat.x + forwardFlat.y * targetFlat.y < 0.96f) return;
            const bool isPed = call<bool>(hash::IS_ENTITY_A_PED, entity);
            const bool isVehicle = call<bool>(hash::IS_ENTITY_A_VEHICLE, entity);
            if (!isPed && !isVehicle) return;
            if (seenCount >= static_cast<int>(seen.size())) return;
            seen[static_cast<std::size_t>(seenCount++)] = entity;
            if (freezing) {
                if (frozenEntity && frozenEntity != entity)
                    call<>(hash::FREEZE_ENTITY_POSITION, frozenEntity, false);
                frozenEntity = entity;
                call<>(hash::FREEZE_ENTITY_POSITION, entity, true);
                thawAt = call<std::uint32_t>(hash::GET_GAME_TIMER) + config.freezeDurationMs;
            } else {
                const float force = isVehicle ? config.superBreathVehicleForce :
                                                config.superBreathPedForce;
                if (isPed)
                    call<bool>(hash::SET_PED_TO_RAGDOLL, entity, 350, 800, 0,
                               false, false, false);
                call<>(hash::APPLY_FORCE_TO_ENTITY, entity, 1,
                       forward.x * force, forward.y * force,
                       forward.z * force + force * 0.12f,
                       0.0f, 0.0f, 0.0f, 0, false, true, true, false, true);
            }
        };
        for (float fraction : strides) {
            const Point3 pos = add(start, scale(forward, range * fraction));
            const float area = std::min(4.0f, range * fraction * 0.18f);
            affect(call<int>(hash::GET_RANDOM_PED_AT_COORD,
                             pos.x, pos.y, pos.z, area, area, 2.0f, -1));
            int nearbyPed = 0;
            if (call<bool>(hash::GET_CLOSEST_PED,
                    pos.x, pos.y, pos.z, area,
                    true, false, &nearbyPed, false, false, -1)) affect(nearbyPed);
            affect(call<int>(hash::GET_CLOSEST_VEHICLE,
                             pos.x, pos.y, pos.z, area, 0, 127));
        }
        if (firstPress) supermanPlaySound(freezing ? "freeze_breath" : "super_breath", false);
    }

    void thunderClap(int ped) {
        const Point3 p = entityPosition(ped);
        shockRing(p, config.clapRadius, "exp_grd_flare");
        addShockwave(p, config.clapRadius, 480U, 195, 220, 255, true);
        shake(0.8f);
        radialImpulse(ped, p, config.clapRadius, config.clapForce, config.clapLift);
        supermanPlaySound("thunder_clap", false);
    }

    void tornado(int ped, std::uint32_t now) {
        if (now - lastAttack < 230U) return;
        lastAttack = now;
        const Point3 center = entityPosition(ped);
        radialImpulse(ped, center, config.tornadoRadius, config.tornadoForce, config.tornadoLift);
        particle("ent_sht_extinguisher", center, 1.0f);
        if (input.pressed(config.tornado)) supermanPlaySound("tornado_spin", false);
    }

    void groundPound(int ped) {
        const Point3 p = groundImpactPoint(ped);
        explosion(p, 19, 0.0f);
        shockRing(p, config.shockRadius, "exp_grd_flare");
        addShockwave(add(p, {0.0f, 0.0f, 0.13f}), config.shockRadius,
                     520U, 255, 221, 175);
        radialImpulse(ped, p, config.shockRadius, config.landingForce, config.landingLift);
        shake(1.0f);
        supermanPlaySound("ground_pound", false);
    }

    void carryOrThrow(int ped) {
        if (carriedVehicle) {
            const int v = carriedVehicle;
            carriedVehicle = 0;
            stopCarryPose(ped);
            call<>(hash::FREEZE_ENTITY_POSITION, v, false);
            setVelocity(v, scale(viewDirection(), 75.0f));
            supermanPlaySound("super_punch", false);
            return;
        }
        const Point3 p = entityPosition(ped);
        const int vehicle = call<int>(hash::GET_CLOSEST_VEHICLE,
            p.x, p.y, p.z, 10.0f, 0, 70);
        if (vehicle && call<bool>(hash::DOES_ENTITY_EXIST, vehicle)) {
            carriedVehicle = vehicle;
            call<>(hash::FREEZE_ENTITY_POSITION, vehicle, true);
        }
    }

    void updateCarry(int ped, std::uint32_t now) {
        if (!call<bool>(hash::DOES_ENTITY_EXIST, carriedVehicle)) {
            stopCarryPose(ped);
            carriedVehicle = 0;
            return;
        }
        const Point3 desired = add(entityPosition(ped), scale(viewDirection(), 5.5f));
        call<>(hash::SET_ENTITY_COORDS_NO_OFFSET, carriedVehicle,
               desired.x, desired.y, desired.z + 1.0f, false, false, false);
        if (flight || (action.waiting && action.playing)) return;
        const float speed = call<float>(hash::GET_ENTITY_SPEED, ped);
        const PowerAnim desiredPose = speed > 4.5f ? PowerAnim::CarryRun :
                                      speed > 0.6f ? PowerAnim::CarryWalk : PowerAnim::CarryIdle;
        if (carryPoseActive && carryPower != desiredPose) stopCarryPose(ped);
        carryPower = desiredPose;
        if (carryPoseActive && now - lastCarryPoseAttempt < 550U) return;
        const Animation& clip = config.anim(carryPower);
        if (carryPoseActive && call<bool>(hash::IS_ENTITY_PLAYING_ANIM, ped,
                                         clip.dict.c_str(), clip.clip.c_str(), 3)) return;
        if (playAnim(ped, clip, -1, 48)) {
            carryPoseActive = true;
            lastCarryPoseAttempt = now;
        }
    }

    void solarFlare(int ped) {
        const Point3 p = entityPosition(ped);
        explosion(p, 19, 0.2f);
        shockRing(p, config.solarRadius, "exp_grd_flare");
        addShockwave(p, config.solarRadius, 650U, 255, 241, 175, true);
        radialImpulse(ped, p, config.solarRadius, config.solarPedForce, 12.0f);
        shake(1.5f);
        supermanPlaySound("solar_flare_emp", false);
    }

    void handleCombat(int ped, std::uint32_t now) {
        if (input.pressed(config.lock)) lockedTarget = traceRay(ped, 75.0f).entity;
        if (lockedTarget && !call<bool>(hash::DOES_ENTITY_EXIST, lockedTarget)) lockedTarget = 0;
        if (input.pressed(config.attack) && now - lastAttack > 180U) {
            lastAttack = now;
            const int target = lockedTarget ? lockedTarget : traceRay(ped, 4.0f).entity;
            if (target) {
                call<>(hash::APPLY_DAMAGE_TO_PED, target, 20, false, 0, 0);
                pushTarget(ped, 45.0f, 5.0f);
                supermanPlaySound("super_punch", false);
            }
        }
        if (input.pressed(config.uppercut) && ready(Cooldown::Uppercut, now)) {
            pushTarget(ped, 90.0f, 85.0f);
            supermanPlaySound("super_punch", false);
            putCooldown(Cooldown::Uppercut, now, config.uppercutCooldownMs);
        }
        if (input.pressed(config.takedown) && ready(Cooldown::Takedown, now)) {
            pushTarget(ped, 115.0f, 5.0f);
            supermanPlaySound("super_punch", false);
            putCooldown(Cooldown::Takedown, now, config.takedownCooldownMs);
        }
        if (input.pressed(config.piledrive)) {
            pushTarget(ped, 75.0f, -60.0f);
            supermanPlaySound("piledrive_slam", false);
        }
    }

    bool boostPreviously = false;
};

Superman gSuperman;
void scriptMain() {
    for (;;) {
        gSuperman.tick();
        scriptWait(0);
    }
}
} // namespace

// The native port enumerates *.shv.dylib and resolves DllMain via dlsym.
extern "C" __attribute__((visibility("default")))
bool DllMain(void* module, std::uint32_t reason, void*) {
    if (reason == 1) {
        gSuperman.config.load();
        scriptRegister(module, scriptMain);
    }
    if (reason == 0) {
        gSuperman.shutdown(call<int>(hash::PLAYER_PED_ID));
        scriptUnregister(module);
    }
    return true;
}

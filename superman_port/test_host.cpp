// Test the independent C++ gameplay state machine with ScriptHook mocks.
// This does NOT simulate RAGE rendering, physics or actual iOS injection.
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <string>
#include <utility>
#include <vector>

#include "SupermanR6.cpp"

namespace {
std::array<bool, 256> keyState{};
std::uint64_t currentNative = 0;
std::array<std::uint64_t, 32> result{};
std::vector<std::uint64_t> args{};
std::vector<std::uint64_t> recorded{};
std::vector<std::pair<std::string, std::string>> playedAnimations{};
std::vector<std::string> notifications{};
std::vector<std::string> particleNames{};
std::vector<int> forceTargets{};
std::vector<std::pair<float, float>> flightRotations{};
std::vector<int> meshAlphas{};
bool simulateNearbyEntities = false;
bool simulatedAnimLoaded = true;
float simulatedAltitude = 10.0f;
std::uint32_t ms = 1000;
void (*scriptCallback)() = nullptr;
int sounds = 0;

template <typename T> void setResult(const T& v) {
    static_assert(sizeof(T) <= sizeof(result));
    std::memcpy(result.data(), &v, sizeof(T));
}
}

extern "C" bool iosKeyIsDown(int vk) { return vk > 0 && vk < 255 && keyState[vk]; }
extern "C" void scriptRegister(void*, void (*func)()) { scriptCallback = func; }
extern "C" void scriptUnregister(void*) { scriptCallback = nullptr; }
extern "C" void scriptWait(std::uint32_t) {}
extern "C" void nativeInit(std::uint64_t hash) { currentNative = hash; args.clear(); }
extern "C" void nativePush64(std::uint64_t v) { args.push_back(v); }
extern "C" std::uint64_t* nativeCall() {
    using namespace shv;
    recorded.push_back(currentNative);
    result.fill(0);
    switch (currentNative) {
    case hash::PLAYER_PED_ID: setResult(42); break;
    case hash::PLAYER_ID: setResult(0); break;
    case hash::DOES_ENTITY_EXIST: setResult(true); break;
    case hash::GET_GAME_TIMER: setResult(ms); break;
    case hash::GET_ENTITY_HEIGHT_ABOVE_GROUND: setResult(simulatedAltitude); break;
    case hash::GET_ENTITY_COORDS: {
        const int id = static_cast<int>(args[0]);
        if (simulateNearbyEntities && id >= 52 && id <= 55) {
            if (id == 52) setResult(Vec3{5, 0, 0, 0, 5, 0});
            if (id == 53) setResult(Vec3{-5, 0, 0, 0, 5, 0});
            if (id == 54) setResult(Vec3{0, 0, -5, 0, 5, 0});
            if (id == 55) setResult(Vec3{0, 0, 5, 0, 5, 0});
            break;
        }
        setResult(Vec3{0, 0, 0, 0, 5, 0});
        break;
    }
    case hash::GET_GAMEPLAY_CAM_COORD:
    case hash::GET_PED_BONE_COORDS:
    case hash::GET_ENTITY_VELOCITY: setResult(Vec3{0, 0, 0, 0, 5, 0}); break;
    case hash::GET_GAMEPLAY_CAM_ROT: setResult(Vec3{0, 0, 0, 0, 0, 0}); break;
    case hash::START_SHAPE_TEST_LOS_PROBE: setResult(7); break;
    case hash::GET_SHAPE_TEST_RESULT: {
        int status = 2;
        setResult(status);
        *reinterpret_cast<int*>(args[1]) = 1;
        *reinterpret_cast<Vec3*>(args[2]) = Vec3{0, 0, 15, 0, 1, 0};
        *reinterpret_cast<int*>(args[4]) = 44;
        break;
    }
    case hash::HAS_NAMED_PTFX_ASSET_LOADED: setResult(true); break;
    case hash::IS_ENTITY_A_PED: setResult(args[0] != 54ULL); break;
    case hash::IS_ENTITY_A_VEHICLE: setResult(args[0] == 54ULL); break;
    case hash::GET_RANDOM_PED_AT_COORD:
        if (simulateNearbyEntities) {
            float x = 0.0f;
            std::memcpy(&x, &args[0], sizeof(x));
            if (x > 1.0f) setResult(52);
            if (x < -1.0f) setResult(53);
        }
        break;
    case hash::GET_CLOSEST_PED:
        if (simulateNearbyEntities) {
            float y = 0.0f;
            std::memcpy(&y, &args[1], sizeof(y));
            if (y > 1.0f) {
                *reinterpret_cast<int*>(args[6]) = 55;
                setResult(true);
            }
        }
        break;
    case hash::GET_CLOSEST_VEHICLE:
        if (simulateNearbyEntities) {
            float y = 0.0f;
            std::memcpy(&y, &args[1], sizeof(y));
            if (y < -1.0f) setResult(54);
        }
        break;
    case hash::APPLY_FORCE_TO_ENTITY:
        forceTargets.push_back(static_cast<int>(args[0]));
        break;
    case hash::HAS_ANIM_DICT_LOADED: setResult(simulatedAnimLoaded); break;
    case hash::TASK_PLAY_ANIM:
        playedAnimations.emplace_back(reinterpret_cast<const char*>(args[1]),
                                      reinterpret_cast<const char*>(args[2]));
        break;
    case hash::ADD_TEXT_COMPONENT_SUBSTRING_PLAYER_NAME:
        notifications.emplace_back(reinterpret_cast<const char*>(args[0]));
        break;
    case hash::START_PARTICLE_FX_NON_LOOPED_AT_COORD:
        particleNames.emplace_back(reinterpret_cast<const char*>(args[0]));
        break;
    case hash::SET_ENTITY_ROTATION: {
        float pitch = 0.0f, roll = 0.0f;
        std::memcpy(&pitch, &args[1], sizeof(pitch));
        std::memcpy(&roll, &args[2], sizeof(roll));
        flightRotations.emplace_back(pitch, roll);
        break;
    }
    case hash::DRAW_POLY:
        assert(args.size() == 13);
        meshAlphas.push_back(static_cast<int>(args[12]));
        break;
    default: break;
    }
    return result.data();
}
extern "C" void supermanPlaySound(const char*, bool) { sounds++; }
extern "C" void supermanStopSound(const char*) {}

int main() {
    Config fixture{};
    fixture.load("superman_port/test_Superman.ini");
    assert(fixture.toggle == 120);
    assert(fixture.beamKeys[0] == 105);
    assert(fixture.tapHoldMs == 320);
    assert(fixture.cruiseSpeed == 66.5f);
    assert(fixture.beamRange == 205.0f);
    assert(fixture.lasers[0].range == 205.0f);
    assert(fixture.lasers[0].r == 201);
    assert(fixture.lasers[0].damagePerSecond == 1400.0f);
    assert(fixture.lasers[3].pulseMs == 320);
    assert(fixture.lasers[3].b == 229);
    assert(fixture.slowTimeScale == 0.4f);
    assert(fixture.sprintMultiplier == 1.49f);
    assert(fixture.groundSpeedBoost == 28.0f);
    assert(fixture.clapRadius == 20.0f);
    assert(fixture.freezeRange == 18.0f);
    assert(fixture.freezeDurationMs == 10500U);
    assert(fixture.superBreathRange == 27.0f);
    assert(fixture.superBreathPedForce == 64.0f);
    assert(fixture.superBreathVehicleForce == 175.0f);
    assert(fixture.clapCooldownMs == 6000U);
    assert(fixture.laserMaxMs == 350U);
    assert(!fixture.notifications);
    assert(fixture.hoverDict == "skydive@parachute@");
    assert(fixture.flyAnim == "free_forward");
    assert(fixture.landingShockwaveMinSpeed == 22.0f);
    assert(fixture.actionChargeGlow);
    assert(fixture.bankAngle == 28.0f);
    assert(fixture.pitchScale == 0.8f);
    assert(fixture.volumetricBeams && fixture.shockwaveMeshes &&
           fixture.flightBodyTilt && fixture.supersonicTrail);
    assert(fixture.lasers[0].spokes == 6);
    assert(fixture.lasers[0].layers == 6);
    assert(fixture.lasers[0].spread == 0.04f);
    assert(fixture.lasers[0].eyeSeparation == 0.15f);
    assert(fixture.lasers[0].muzzleGlowScale == 0.1f);
    assert(fixture.anim(PowerAnim::ThunderClap).impactMs == 520);
    assert(fixture.anim(PowerAnim::GroundPound).clip == "ground_attack_on_spot");
    assert(DllMain(reinterpret_cast<void*>(1), 1, nullptr));
    assert(scriptCallback);
    gSuperman.tick();
    keyState[F10] = true;
    gSuperman.tick();
    assert(gSuperman.enabled);
    assert(std::find(recorded.begin(), recorded.end(),
                     shv::hash::BEGIN_TEXT_COMMAND_THEFEED_POST) != recorded.end());
    assert(notifications.size() == 1);
    assert(notifications.back().find("ENABLED") != std::string::npos);
    const auto beforeHeldToggle = std::count(recorded.begin(), recorded.end(),
                                             shv::hash::BEGIN_TEXT_COMMAND_THEFEED_POST);
    gSuperman.tick(); // pressing F10 for more than one frame must not toggle repeatedly
    assert(gSuperman.enabled);
    assert(std::count(recorded.begin(), recorded.end(),
                      shv::hash::BEGIN_TEXT_COMMAND_THEFEED_POST) == beforeHeldToggle);
    keyState[F10] = false;
    keyState[SHIFT] = true;
    gSuperman.tick();
    assert(std::find(recorded.begin(), recorded.end(),
                     shv::hash::SET_PED_MOVE_RATE_OVERRIDE) != recorded.end());
    assert(gSuperman.groundFast);
    keyState[SHIFT] = false;
    gSuperman.tick();
    assert(!gSuperman.groundFast);
    keyState[SPACE] = true;
    ms = 1200;
    gSuperman.tick();
    assert(!gSuperman.flight);
    ms = 1500;
    keyState[W] = true;
    gSuperman.tick();
    assert(gSuperman.flight);
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::SET_ENTITY_VELOCITY) != recorded.end());
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::SET_ENTITY_HAS_GRAVITY) != recorded.end());
    keyState[SHIFT] = true;
    ms = 1550;
    gSuperman.tick();
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::ANIMPOSTFX_PLAY) != recorded.end());
    assert(std::find(particleNames.begin(), particleNames.end(), "exp_grd_flare") == particleNames.end());
    keyState[SHIFT] = false;
    ms = 1600;
    gSuperman.tick();
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::ANIMPOSTFX_STOP) != recorded.end());
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::TASK_PLAY_ANIM) != recorded.end());
    // The takeoff clip blocks normal flight animation/rotation until 2030ms;
    // banking is checked once that clip and the clap action have completed.
    keyState[R] = true;
    keyState[NP1] = true;
    gSuperman.config.laserMaxMs = 350U;
    gSuperman.config.laserCooldownMs = 1200U;
    const std::size_t meshesBeforeLaser = meshAlphas.size();
    ms = 1800;
    gSuperman.tick();
    assert(meshAlphas.size() > meshesBeforeLaser); // 3D twin-eye beam shell
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::DRAW_LINE) != recorded.end());
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::START_PARTICLE_FX_NON_LOOPED_AT_COORD) != recorded.end());
    keyState[NP1] = false;
    keyState[V] = true;
    ms = 1880;
    gSuperman.tick();
    keyState[V] = false;
    ms = 1900;
    gSuperman.tick(); // animation begins only after its dictionary is ready
    assert(gSuperman.action.playing);
    const auto beamsBeforeOverheat = std::count(recorded.begin(), recorded.end(),
                                               shv::hash::DRAW_LINE);
    const std::size_t meshesBeforeClap = meshAlphas.size();
    ms = 2430;
    simulateNearbyEntities = true;
    gSuperman.tick();
    assert(!gSuperman.action.waiting);
    assert(meshAlphas.size() > meshesBeforeClap); // shockwave after clap impact
    assert(gSuperman.laserHeat.lockedUntil > ms);
    assert(std::count(recorded.begin(), recorded.end(),
                      shv::hash::DRAW_LINE) == beamsBeforeOverheat);
    for (int expected : {52, 53, 54, 55})
        assert(std::count(forceTargets.begin(), forceTargets.end(), expected) == 1);
    assert(std::find(recorded.begin(), recorded.end(),
                     shv::hash::SET_PED_TO_RAGDOLL) != recorded.end());
    simulateNearbyEntities = false;
    // The original one-shot powers have a recharge window, so repeated
    // button presses cannot spam huge physics bursts each game tick.
    keyState[V] = true;
    ms = 2700;
    gSuperman.tick();
    assert(!gSuperman.action.waiting);
    keyState[V] = false;
    // Super breath is a held ability: the spatial cone must hit the NPC
    // straight ahead and must not treat a hold as a repeated button press.
    keyState[H] = true;
    simulateNearbyEntities = true;
    ms = 2750;
    gSuperman.tick();
    assert(std::count(forceTargets.begin(), forceTargets.end(), 55) == 2);
    keyState[H] = false;
    simulateNearbyEntities = false;
    ms = 2800;
    gSuperman.tick();
    assert(!flightRotations.empty()); // body tilt uses an actual RAGE native
    keyState[D] = true;
    ms = 2850;
    gSuperman.tick();
    assert(std::any_of(flightRotations.begin(), flightRotations.end(),
                       [](const auto& rot) { return std::fabs(rot.second) > 0.1f; }));
    keyState[D] = false;
    assert(std::any_of(playedAnimations.begin(), playedAnimations.end(),
                       [](const auto& a) { return a.first == "skydive@freefall" &&
                                                     a.second == "free_forward"; }));
    keyState[F10] = true;
    ms = 3000;
    gSuperman.tick();
    assert(!gSuperman.enabled);
    assert(!gSuperman.flightTiltApplied);
    assert(flightRotations.back().first == 0.0f &&
           flightRotations.back().second == 0.0f); // neutral pose restored
    assert(notifications.size() == 2);
    assert(notifications.back().find("DISABLED") != std::string::npos);
    assert(sounds >= 2);

    // R15: landing must restore gravity even if the actor is still moving
    // fast downwards; the R14 low-speed-only guard left players airborne.
    keyState.fill(false);
    keyState[CTRL] = true;
    simulatedAltitude = 1.1f;
    Superman landingScenario;
    landingScenario.enabled = true;
    landingScenario.initialized = true;
    landingScenario.flight = true;
    landingScenario.smoothedFlight = {0.0f, 0.0f, -32.0f};
    ms = 4000;
    landingScenario.tick();
    assert(!landingScenario.flight);
    assert(!landingScenario.waves.empty() && landingScenario.waves[0].active);
    assert(std::any_of(playedAnimations.begin(), playedAnimations.end(),
                       [](const auto& a) { return a.second == "land_bend_knees"; }));

    // R15: air-to-ground Ground Pound should keep the dive until contact,
    // then play the ground attack and only afterward apply its explosion.
    keyState.fill(false);
    keyState[B] = true;
    simulatedAltitude = 35.0f;
    Superman plungeScenario;
    plungeScenario.enabled = true;
    plungeScenario.initialized = true;
    plungeScenario.flight = true;
    plungeScenario.smoothedFlight = {0.0f, 0.0f, -6.0f};
    ms = 5000;
    plungeScenario.tick();
    assert(plungeScenario.action.waiting && !plungeScenario.action.playing);
    keyState[B] = false;
    ms = 5060;
    plungeScenario.tick();
    assert(plungeScenario.action.plunging && plungeScenario.flight);
    const auto impactsBeforeLanding = std::count(recorded.begin(), recorded.end(),
                                                 shv::hash::ADD_EXPLOSION);
    ms = 5360;
    plungeScenario.tick();
    assert(plungeScenario.action.plunging);
    assert(std::count(recorded.begin(), recorded.end(),
                      shv::hash::ADD_EXPLOSION) == impactsBeforeLanding);
    // A simultaneous clap request must not replace the active dive or burn
    // a cooldown without performing that action.
    keyState[V] = true;
    ms = 5400;
    plungeScenario.tick();
    assert(plungeScenario.action.name == PowerAnim::GroundPound);
    assert(plungeScenario.readyAt[static_cast<std::size_t>(Superman::Cooldown::Clap)] == 0U);
    keyState[V] = false;
    simulatedAltitude = 1.0f;
    ms = 5450;
    plungeScenario.tick();
    assert(!plungeScenario.flight);
    assert(plungeScenario.action.waiting && !plungeScenario.action.playing);
    ms = 5470;
    plungeScenario.tick();
    assert(plungeScenario.action.playing && !plungeScenario.action.plunging);
    const auto lightsBeforeCharge = std::count(recorded.begin(), recorded.end(),
                                               shv::hash::DRAW_LIGHT_WITH_RANGE);
    const std::size_t particlesBeforeCharge = particleNames.size();
    ms = 5590;
    plungeScenario.tick();
    assert(std::count(recorded.begin(), recorded.end(),
                      shv::hash::DRAW_LIGHT_WITH_RANGE) > lightsBeforeCharge);
    assert(particleNames.size() == particlesBeforeCharge + 2U);
    ms = 5600;
    plungeScenario.tick();
    assert(particleNames.size() == particlesBeforeCharge + 2U);
    ms = 5890;
    plungeScenario.tick();
    assert(!plungeScenario.action.waiting);
    assert(std::count(recorded.begin(), recorded.end(),
                      shv::hash::ADD_EXPLOSION) > impactsBeforeLanding);

    // R15: delayed animation streaming should retry the takeoff during the
    // start clip's remaining window, not silently lose the pose.
    keyState.fill(false);
    keyState[SPACE] = true;
    simulatedAltitude = 5.0f;
    Superman delayedTakeoff;
    delayedTakeoff.enabled = true;
    delayedTakeoff.initialized = true;
    delayedTakeoff.config.tapHoldMs = 150;
    ms = 6100;
    delayedTakeoff.tick();
    simulatedAnimLoaded = false;
    ms = 6400;
    delayedTakeoff.tick();
    assert(delayedTakeoff.flight && delayedTakeoff.takeoffPosePending);
    simulatedAnimLoaded = true;
    ms = 6450;
    delayedTakeoff.tick();
    assert(!delayedTakeoff.takeoffPosePending);
    delayedTakeoff.shutdown(42);

    // R15: an action that never receives its animation dictionary must be
    // cancelled and refunded, so users do not have to spam the touch button.
    keyState.fill(false);
    keyState[V] = true;
    simulatedAnimLoaded = false;
    Superman unavailableAnimation;
    unavailableAnimation.enabled = true;
    unavailableAnimation.initialized = true;
    ms = 7000;
    unavailableAnimation.tick();
    assert(unavailableAnimation.action.waiting);
    assert(unavailableAnimation.readyAt[static_cast<std::size_t>(Superman::Cooldown::Clap)] > 7000U);
    keyState[V] = false;
    ms = 9300;
    unavailableAnimation.tick();
    assert(!unavailableAnimation.action.waiting);
    assert(unavailableAnimation.readyAt[static_cast<std::size_t>(Superman::Cooldown::Clap)] == 0U);

    // R15: never apply a phantom ground blast if collision or terrain data
    // remains unavailable throughout an airborne dive.
    simulatedAnimLoaded = true;
    simulatedAltitude = 20.0f;
    keyState[B] = true;
    Superman unreachableGround;
    unreachableGround.enabled = true;
    unreachableGround.initialized = true;
    unreachableGround.flight = true;
    ms = 10000;
    unreachableGround.tick();
    keyState[B] = false;
    ms = 10050;
    unreachableGround.tick();
    assert(unreachableGround.action.plunging);
    simulatedAltitude = -1.0f;
    const auto explosionsBeforeTimeout = std::count(recorded.begin(), recorded.end(),
                                                    shv::hash::ADD_EXPLOSION);
    ms = 13300;
    unreachableGround.tick();
    assert(!unreachableGround.action.waiting);
    assert(unreachableGround.flight);
    assert(std::count(recorded.begin(), recorded.end(),
                      shv::hash::ADD_EXPLOSION) == explosionsBeforeTimeout);
    unreachableGround.shutdown(42);
    assert(DllMain(reinterpret_cast<void*>(1), 0, nullptr));
    assert(!scriptCallback);
}

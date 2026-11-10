#include "GameplayCore.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <dlfcn.h>
#include <initializer_list>

std::atomic<uint32_t> gSMClicks{0};
std::atomic<uint32_t> gSMHolds{0};
std::atomic<bool> gSMScriptRegistered{false};
std::atomic<bool> gSMScriptRunning{false};
std::atomic<bool> gSMEnabled{false};
std::atomic<bool> gSMFlying{false};

namespace {
constexpr float kPi = 3.14159265358979323846f;
float clamp(float value, float lower, float upper) {
    return std::isfinite(value) ? std::max(lower, std::min(value, upper)) : lower;
}
}

SMVec3 SMCameraForward(float pitchDegrees, float yawDegrees) {
    if (!std::isfinite(pitchDegrees) || !std::isfinite(yawDegrees)) return {0, 1, 0};
    float pitch = pitchDegrees * kPi / 180.f;
    float yaw = yawDegrees * kPi / 180.f;
    float flat = std::cos(pitch);
    return {-std::sin(yaw) * flat, std::cos(yaw) * flat, std::sin(pitch)};
}

bool SMIsFinite(SMVec3 value) {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

SMSettings SMSanitizeSettings(SMSettings settings) {
    settings.cruiseSpeed = clamp(settings.cruiseSpeed, 5.f, 55.f);
    settings.boostSpeed = clamp(settings.boostSpeed, settings.cruiseSpeed, 95.f);
    settings.verticalSpeed = clamp(settings.verticalSpeed, 3.f, 30.f);
    settings.heatRange = clamp(settings.heatRange, 10.f, 140.f);
    settings.shockRadius = clamp(settings.shockRadius, 3.f, 20.f);
    settings.shockForce = clamp(settings.shockForce, 3.f, 40.f);
    settings.shockLift = clamp(settings.shockLift, 1.f, 16.f);
    settings.heatDamage = std::max(0, std::min(settings.heatDamage, 25));
    settings.heatIntervalMs = std::max(100, std::min(settings.heatIntervalMs, 600));
    settings.shockCooldownMs = std::max(800, std::min(settings.shockCooldownMs, 8000));
    return settings;
}

extern "C" void SMButtonClick(uint32_t action) {
    constexpr uint32_t allowed = SM_TOGGLE | SM_FLIGHT | SM_SHOCK | SM_GROUND;
    gSMClicks.fetch_or(action & allowed, std::memory_order_relaxed);
}

extern "C" void SMButtonHold(uint32_t action, bool isDown) {
    constexpr uint32_t allowed = SM_FORWARD | SM_UP | SM_DOWN | SM_HEAT | SM_BOOST;
    action &= allowed;
    if (isDown) gSMHolds.fetch_or(action, std::memory_order_relaxed);
    else gSMHolds.fetch_and(~action, std::memory_order_relaxed);
}

#ifndef SUPERMAN_MATH_ONLY
namespace {
// Verified hashes against citizenfx/natives and the native ScriptHookV API.
enum : uint64_t {
    H_PLAYER_PED_ID                 = 0xD80958FC74E988A6ULL,
    H_DOES_ENTITY_EXIST            = 0x7239B21A38F536BAULL,
    H_IS_PED_IN_ANY_VEHICLE        = 0x997ABD671D25CA0BULL,
    H_NETWORK_IS_SESSION_ACTIVE    = 0xD83C2B94E7508980ULL,
    H_GET_ENTITY_COORDS            = 0x3FEF770D40960D5AULL,
    H_GET_GAMEPLAY_CAM_COORD       = 0x14D6F5678D8F1B37ULL,
    H_GET_GAMEPLAY_CAM_ROT         = 0x837765A25378F0BBULL,
    H_SET_ENTITY_HAS_GRAVITY       = 0x4A4722448F18EEF5ULL,
    H_SET_ENTITY_VELOCITY          = 0x1C99BB7B6E96D16FULL,
    H_DRAW_LINE                    = 0x6B7256074AE34680ULL,
    H_APPLY_FORCE_TO_ENTITY        = 0xC5F68BE9613E2D18ULL,
    H_SHOOT_SINGLE_BULLET          = 0x867654CBC7606F2CULL,
    H_REQUEST_WEAPON_ASSET         = 0x5443438F033E29C3ULL,
    H_HAS_WEAPON_ASSET_LOADED      = 0x36E353271F0E90EEULL,
};
constexpr uint32_t kWeaponPistol = 0x1B06D571u;

using InitNative = void(*)(uint64_t);
using PushNative = void(*)(uint64_t);
using CallNative = uint64_t*(*)();
using WaitScript = void(*)(unsigned long);
using WorldPool = int(*)(int*, int);

struct NativeAPI {
    InitNative init = nullptr;
    PushNative push = nullptr;
    CallNative call = nullptr;
    WaitScript wait = nullptr;
    WorldPool allPeds = nullptr;
    WorldPool allVehicles = nullptr;
};

NativeAPI& api() {
    static NativeAPI functions;
    static bool loaded = false;
    if (!loaded) {
        functions.init = reinterpret_cast<InitNative>(dlsym(RTLD_DEFAULT, "nativeInit"));
        functions.push = reinterpret_cast<PushNative>(dlsym(RTLD_DEFAULT, "nativePush64"));
        functions.call = reinterpret_cast<CallNative>(dlsym(RTLD_DEFAULT, "nativeCall"));
        functions.wait = reinterpret_cast<WaitScript>(dlsym(RTLD_DEFAULT, "scriptWait"));
        functions.allPeds = reinterpret_cast<WorldPool>(dlsym(RTLD_DEFAULT, "worldGetAllPeds"));
        functions.allVehicles = reinterpret_cast<WorldPool>(dlsym(RTLD_DEFAULT, "worldGetAllVehicles"));
        loaded = functions.init && functions.push && functions.call && functions.wait;
    }
    return functions;
}

uint64_t floatSlot(float value) {
    uint32_t bits;
    static_assert(sizeof(bits) == sizeof(value), "Float must be 32-bit");
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

uint64_t* call(uint64_t nativeHash, std::initializer_list<uint64_t> args = {}) {
    NativeAPI& fn = api();
    fn.init(nativeHash);
    for (uint64_t arg : args) fn.push(arg);
    return fn.call();
}

uint64_t result(uint64_t nativeHash, std::initializer_list<uint64_t> args = {}) {
    uint64_t* ptr = call(nativeHash, args);
    return ptr ? ptr[0] : 0;
}

// NativeVector3 uses 8-byte aligned slots, not three contiguous floats.
SMVec3 vectorResult(uint64_t nativeHash, std::initializer_list<uint64_t> args = {}) {
    uint64_t* ptr = call(nativeHash, args);
    SMVec3 vector = {0, 0, 0};
    if (!ptr) return vector;
    std::memcpy(&vector.x, &ptr[0], 4);
    std::memcpy(&vector.y, &ptr[1], 4);
    std::memcpy(&vector.z, &ptr[2], 4);
    return vector;
}

SMVec3 add(SMVec3 a, SMVec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
SMVec3 sub(SMVec3 a, SMVec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
SMVec3 mul(SMVec3 a, float scale) { return {a.x * scale, a.y * scale, a.z * scale}; }
float magnitude(SMVec3 v) { return std::sqrt(v.x*v.x + v.y*v.y + v.z*v.z); }

SMVec3 cameraDirection() {
    SMVec3 rotation = vectorResult(H_GET_GAMEPLAY_CAM_ROT, {2});
    return SMCameraForward(rotation.x, rotation.z);
}

void setGravity(int entity, bool enabled) {
    call(H_SET_ENTITY_HAS_GRAVITY, {uint64_t(entity), uint64_t(enabled)});
}
void setVelocity(int entity, SMVec3 v) {
    if (!SMIsFinite(v)) return;
    call(H_SET_ENTITY_VELOCITY, {uint64_t(entity), floatSlot(v.x), floatSlot(v.y), floatSlot(v.z)});
}

void shockPool(WorldPool pool, int self, SMVec3 origin, SMSettings s) {
    if (!pool) return;
    int entities[128] = {};
    int count = std::min(128, std::max(0, pool(entities, 128)));
    for (int i = 0; i < count; ++i) {
        const int entity = entities[i];
        if (!entity || entity == self) continue;
        if (!result(H_DOES_ENTITY_EXIST, {uint64_t(entity)})) continue;
        SMVec3 center = vectorResult(H_GET_ENTITY_COORDS, {uint64_t(entity), 0});
        SMVec3 diff = sub(center, origin);
        float distance = magnitude(diff);
        if (!SMIsFinite(diff) || distance < 0.3f || distance > s.shockRadius) continue;
        const float strength = s.shockForce * (1.f - distance / s.shockRadius);
        const SMVec3 force = add(mul(diff, strength / distance), {0, 0, s.shockLift});
        // ForceType 1: maximum 128 candidates/pool; no remote/online entities.
        call(H_APPLY_FORCE_TO_ENTITY,
            {uint64_t(entity), 1, floatSlot(force.x), floatSlot(force.y), floatSlot(force.z),
             0, 0, 0, 0, 0, 0, 1, 0, 1});
    }
}

SMSettings settings;
bool active = false;
bool flying = false;
int gravityEntity = 0;
uint64_t lastBeam = 0;
uint64_t lastShock = 0;
uint64_t lastHeatSound = 0;
bool weaponRequested = false;

uint64_t monotonicMs() {
    using namespace std::chrono;
    return uint64_t(duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
}

void stopFlying() {
    if (gravityEntity && result(H_DOES_ENTITY_EXIST, {uint64_t(gravityEntity)}))
        setGravity(gravityEntity, true);
    flying = false;
    gravityEntity = 0;
    gSMFlying.store(false, std::memory_order_relaxed);
}

void stopEverything() {
    stopFlying();
    active = false;
    gSMEnabled.store(false, std::memory_order_relaxed);
    gSMHolds.store(0, std::memory_order_relaxed);
}

void tick() {
    const uint64_t now = monotonicMs();
    const bool online = result(H_NETWORK_IS_SESSION_ACTIVE) != 0;
    if (online) {
        gSMClicks.exchange(0, std::memory_order_relaxed);
        if (active || flying) stopEverything();
        return;
    }

    int ped = int(result(H_PLAYER_PED_ID));
    if (!ped || !result(H_DOES_ENTITY_EXIST, {uint64_t(ped)})) {
        gSMClicks.exchange(0, std::memory_order_relaxed);
        if (flying) stopFlying();
        return;
    }
    if (flying && gravityEntity != ped) stopFlying();

    const uint32_t clicks = gSMClicks.exchange(0, std::memory_order_relaxed);
    if (clicks & SM_TOGGLE) {
        if (active) stopEverything();
        else { active = true; gSMEnabled.store(true, std::memory_order_relaxed); }
    }
    if (!active) return;

    bool inVehicle = result(H_IS_PED_IN_ANY_VEHICLE, {uint64_t(ped), 0}) != 0;
    if (inVehicle && flying) stopFlying();
    if ((clicks & SM_FLIGHT) && !inVehicle) {
        if (flying) stopFlying();
        else {
            flying = true;
            gravityEntity = ped;
            setGravity(ped, false);
            gSMFlying.store(true, std::memory_order_relaxed);
            SMPlaySound("takeoff");
        }
    }

    uint32_t held = gSMHolds.load(std::memory_order_relaxed);
    if (flying) {
        SMVec3 velocity{0, 0, 0};
        if (held & SM_FORWARD) {
            float speed = (held & SM_BOOST) ? settings.boostSpeed : settings.cruiseSpeed;
            velocity = mul(cameraDirection(), speed);
        }
        if (held & SM_UP) velocity.z += settings.verticalSpeed;
        if (held & SM_DOWN) velocity.z -= settings.verticalSpeed;
        setVelocity(ped, velocity);
    }

    if ((clicks & (SM_SHOCK | SM_GROUND)) && now - lastShock >= uint64_t(settings.shockCooldownMs)) {
        lastShock = now;
        SMVec3 origin = vectorResult(H_GET_ENTITY_COORDS, {uint64_t(ped), 0});
        if (SMIsFinite(origin)) {
            SMSettings effect = settings;
            if (clicks & SM_GROUND) {
                effect.shockRadius *= 0.7f;
                effect.shockLift *= 1.2f;
            }
            shockPool(api().allPeds, ped, origin, effect);
            shockPool(api().allVehicles, ped, origin, effect);
            SMPlaySound((clicks & SM_GROUND) ? "ground_pound" : "thunder_clap");
        }
    }

    if (held & SM_HEAT) {
        SMVec3 camera = vectorResult(H_GET_GAMEPLAY_CAM_COORD);
        SMVec3 direction = cameraDirection();
        SMVec3 target = add(camera, mul(direction, settings.heatRange));
        if (!SMIsFinite(camera) || !SMIsFinite(target)) return;
        SMVec3 eye = add(vectorResult(H_GET_ENTITY_COORDS, {uint64_t(ped), 0}), {0, 0, 1.60f});
        if (!SMIsFinite(eye)) return;
        call(H_DRAW_LINE, {floatSlot(eye.x), floatSlot(eye.y), floatSlot(eye.z),
                           floatSlot(target.x), floatSlot(target.y), floatSlot(target.z),
                           255, 25, 10, 240});
        call(H_DRAW_LINE, {floatSlot(eye.x + 0.09f), floatSlot(eye.y), floatSlot(eye.z),
                           floatSlot(target.x), floatSlot(target.y), floatSlot(target.z),
                           255, 195, 40, 160});
        if (now - lastBeam >= uint64_t(settings.heatIntervalMs)) {
            lastBeam = now;
            if (!weaponRequested) {
                call(H_REQUEST_WEAPON_ASSET, {kWeaponPistol, 31, 0});
                weaponRequested = true;
            }
            if (settings.heatDamage > 0 && result(H_HAS_WEAPON_ASSET_LOADED, {kWeaponPistol})) {
                // Small, capped single-player damage; no creation of fire/particle pools.
                call(H_SHOOT_SINGLE_BULLET,
                    {floatSlot(eye.x), floatSlot(eye.y), floatSlot(eye.z),
                     floatSlot(target.x), floatSlot(target.y), floatSlot(target.z),
                     uint64_t(settings.heatDamage), 1, kWeaponPistol, uint64_t(ped), 0, 1, floatSlot(500.f)});
            }
        }
        if (now - lastHeatSound >= 1000u) {
            lastHeatSound = now;
            SMPlaySound("heat_vision");
        }
    }
}
}

extern "C" void SMSetSettings(SMSettings value) {
    // Called once on main thread at initialization before script registration.
    settings = SMSanitizeSettings(value);
}

extern "C" void SMGameplayMain() {
    if (!api().wait) return;
    settings = SMSanitizeSettings(settings);
    gSMScriptRunning.store(true, std::memory_order_relaxed);
    api().wait(0);
    while (true) {
        tick();
        api().wait(0);
    }
}
#else
extern "C" void SMSetSettings(SMSettings) {}
extern "C" void SMGameplayMain() {}
#endif

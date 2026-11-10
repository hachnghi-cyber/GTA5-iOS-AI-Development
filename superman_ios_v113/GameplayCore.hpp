#pragma once

#include <atomic>
#include <cstdint>

// Private bridge for this original ARM64 implementation. It does not attempt
// to load or emulate TamedMods' Windows-x64 Superman.asi.
enum SupermanAction : uint32_t {
    SM_TOGGLE = 1u << 0,
    SM_FLIGHT = 1u << 1,
    SM_SHOCK = 1u << 2,
    SM_FORWARD = 1u << 3,
    SM_UP = 1u << 4,
    SM_DOWN = 1u << 5,
    SM_HEAT = 1u << 6,
    SM_BOOST = 1u << 7,
    SM_GROUND = 1u << 8,
};

struct SMVec3 {
    float x, y, z;
};

struct SMSettings {
    float cruiseSpeed = 30.f;
    float boostSpeed = 60.f;
    float verticalSpeed = 14.f;
    float heatRange = 80.f;
    float shockRadius = 12.f;
    float shockForce = 22.f;
    float shockLift = 8.f;
    int heatDamage = 10;
    int heatIntervalMs = 180;
    int shockCooldownMs = 2400;
};

// Pure math is tested on Linux; the game-native calls run ONLY on the
// ScriptHookV cooperative script thread, never in UIKit handlers.
SMVec3 SMCameraForward(float pitchDegrees, float yawDegrees);
bool SMIsFinite(SMVec3 value);
SMSettings SMSanitizeSettings(SMSettings value);

extern std::atomic<uint32_t> gSMClicks;
extern std::atomic<uint32_t> gSMHolds;
extern std::atomic<bool> gSMScriptRegistered;
extern std::atomic<bool> gSMScriptRunning;
extern std::atomic<bool> gSMEnabled;
extern std::atomic<bool> gSMFlying;

extern "C" void SMButtonClick(uint32_t action);
extern "C" void SMButtonHold(uint32_t action, bool isDown);
extern "C" void SMSetSettings(SMSettings settings);
extern "C" void SMGameplayMain();
extern "C" void SMPlaySound(const char* name);


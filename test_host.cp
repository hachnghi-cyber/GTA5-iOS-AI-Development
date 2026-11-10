// Test the independent C++ gameplay state machine with ScriptHook mocks.
// This does NOT simulate RAGE rendering, physics or actual iOS injection.
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>

#include "SupermanR6.cpp"

namespace {
std::array<bool, 256> keyState{};
std::uint64_t currentNative = 0;
std::array<std::uint64_t, 32> result{};
std::vector<std::uint64_t> args{};
std::vector<std::uint64_t> recorded{};
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
    case hash::GET_GAMEPLAY_CAM_COORD:
    case hash::GET_ENTITY_COORDS:
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
    assert(fixture.slowTimeScale == 0.4f);
    assert(DllMain(reinterpret_cast<void*>(1), 1, nullptr));
    assert(scriptCallback);
    gSuperman.tick();
    keyState[F10] = true;
    gSuperman.tick();
    assert(gSuperman.enabled);
    keyState[F10] = false;
    keyState[SPACE] = true;
    ms = 1200;
    gSuperman.tick();
    assert(!gSuperman.flight);
    ms = 1500;
    keyState[W] = true;
    gSuperman.tick();
    assert(gSuperman.flight);
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::SET_ENTITY_VELOCITY) != recorded.end());
    keyState[R] = true;
    keyState[NP1] = true;
    ms = 1800;
    gSuperman.tick();
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::DRAW_LINE) != recorded.end());
    assert(std::find(recorded.begin(), recorded.end(), shv::hash::START_PARTICLE_FX_NON_LOOPED_AT_COORD) != recorded.end());
    keyState[NP1] = false;
    keyState[F10] = true;
    ms = 2000;
    gSuperman.tick();
    assert(!gSuperman.enabled);
    assert(sounds >= 2);
    assert(DllMain(reinterpret_cast<void*>(1), 0, nullptr));
    assert(!scriptCallback);
}

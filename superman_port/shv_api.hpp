#pragma once

// Independently written native interface for the ScriptHookV.dylib found in
// GTA V iOS R6. This does not contain any code from TamedMods' Windows plugin.
#include <cstdint>
#include <cstring>
#include <type_traits>

extern "C" {
void scriptRegister(void* module, void (*function)());
void scriptUnregister(void* module);
void scriptWait(std::uint32_t milliseconds);
void nativeInit(std::uint64_t hash);
void nativePush64(std::uint64_t argument);
std::uint64_t* nativeCall();
bool iosKeyIsDown(int virtualKey);
}

namespace shv {
// ScriptHookV native Vector3 uses padding after each component.
struct Vec3 {
    float x;
    std::uint32_t padX;
    float y;
    std::uint32_t padY;
    float z;
    std::uint32_t padZ;
};

struct Point3 {
    float x = 0;
    float y = 0;
    float z = 0;
};

inline Point3 point(const Vec3& v) { return {v.x, v.y, v.z}; }
inline Point3 add(Point3 a, Point3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline Point3 sub(Point3 a, Point3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline Point3 scale(Point3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }

template <typename T>
std::uint64_t pushBits(T v) {
    if constexpr (std::is_pointer_v<T>) {
        return reinterpret_cast<std::uintptr_t>(v);
    } else if constexpr (std::is_floating_point_v<T>) {
        static_assert(sizeof(T) <= sizeof(std::uint64_t));
        std::uint64_t bits = 0;
        std::memcpy(&bits, &v, sizeof(T));
        return bits;
    } else {
        return static_cast<std::uint64_t>(v);
    }
}

template <typename Ret = void, typename... Args>
Ret call(std::uint64_t nativeHash, Args... args) {
    nativeInit(nativeHash);
    (nativePush64(pushBits(args)), ...);
    std::uint64_t* result = nativeCall();
    if constexpr (!std::is_same_v<Ret, void>) {
        Ret out{};
        if (result) std::memcpy(&out, result, sizeof(Ret));
        return out;
    }
}

namespace hash {
// GTA V Legacy hashes checked against alloc8or/gta5-nativedb-data.
constexpr std::uint64_t PLAYER_PED_ID = 0xD80958FC74E988A6ULL;
constexpr std::uint64_t PLAYER_ID = 0x4F8644AF03D0E0D6ULL;
constexpr std::uint64_t GET_ENTITY_COORDS = 0x3FEF770D40960D5AULL;
constexpr std::uint64_t GET_ENTITY_VELOCITY = 0x4805D2B1D8CF94A9ULL;
constexpr std::uint64_t SET_ENTITY_VELOCITY = 0x1C99BB7B6E96D16FULL;
constexpr std::uint64_t SET_ENTITY_HAS_GRAVITY = 0x4A4722448F18EEF5ULL;
constexpr std::uint64_t GET_ENTITY_HEIGHT_ABOVE_GROUND = 0x1DD55701034110E5ULL;
constexpr std::uint64_t SET_ENTITY_INVINCIBLE = 0x3882114BDE571AD4ULL;
constexpr std::uint64_t SET_ENTITY_PROOFS = 0xFAEE099C6F890BB8ULL;
constexpr std::uint64_t IS_ENTITY_DEAD = 0x5F9532F3B5CC2551ULL;
constexpr std::uint64_t DOES_ENTITY_EXIST = 0x7239B21A38F536BAULL;
constexpr std::uint64_t IS_ENTITY_A_PED = 0x524AC5ECEA15343EULL;
constexpr std::uint64_t IS_ENTITY_A_VEHICLE = 0x6AC7003FA6E5575EULL;
constexpr std::uint64_t NETWORK_IS_SESSION_STARTED = 0x9DE624D2FC4B603FULL;
constexpr std::uint64_t GET_ENTITY_HEALTH = 0xEEF059FAD016D209ULL;
constexpr std::uint64_t SET_ENTITY_HEALTH = 0x6B76DC1F3AE6E6A3ULL;
constexpr std::uint64_t SET_PLAYER_WANTED_LEVEL = 0x39FF19C64EF7DA5BULL;
constexpr std::uint64_t SET_PLAYER_WANTED_LEVEL_NOW = 0xE0A7D1E497FFCD6FULL;
constexpr std::uint64_t SET_SUPER_JUMP_THIS_FRAME = 0x57FFF03E423A4C0BULL;
constexpr std::uint64_t GET_GAMEPLAY_CAM_ROT = 0x837765A25378F0BBULL;
constexpr std::uint64_t GET_GAMEPLAY_CAM_COORD = 0x14D6F5678D8F1B37ULL;
constexpr std::uint64_t GET_ENTITY_SPEED = 0xD5037BA82E12416FULL;
constexpr std::uint64_t GET_ENTITY_HEADING = 0xE83D4F9BA2A38914ULL;
constexpr std::uint64_t SET_ENTITY_HEADING = 0x8E2530AA8ADA980EULL;
constexpr std::uint64_t SET_ENTITY_ROTATION = 0x8524A8B0171D5E07ULL;
constexpr std::uint64_t GET_GAME_TIMER = 0x9CD27B0045628463ULL;
constexpr std::uint64_t GET_CLOSEST_VEHICLE = 0xF73EB622C4F1689BULL;
// Native signatures documented by citizenfx/natives; use bounded spatial
// sampling instead of GET_PED_NEARBY_PEDS' unsafe sizeAndPeds buffer layout.
constexpr std::uint64_t GET_CLOSEST_PED = 0xC33AB876A77F8164ULL;
constexpr std::uint64_t GET_RANDOM_PED_AT_COORD = 0x876046A8E3A4B71CULL;
constexpr std::uint64_t SET_RUN_SPRINT_MULTIPLIER_FOR_PLAYER = 0x6DB47AA77FD94E09ULL;
constexpr std::uint64_t SET_PED_MOVE_RATE_OVERRIDE = 0x085BF80FA50A39D1ULL;
constexpr std::uint64_t GET_PED_BONE_COORDS = 0x17C07FC640E86B4EULL;
constexpr std::uint64_t SET_PED_CAN_RAGDOLL = 0xB128377056A54E2AULL;
constexpr std::uint64_t SET_PED_TO_RAGDOLL = 0xAE99FB955581844AULL;
constexpr std::uint64_t IS_PED_IN_ANY_VEHICLE = 0x997ABD671D25CA0BULL;
constexpr std::uint64_t SET_ENTITY_COORDS_NO_OFFSET = 0x239A3351AC1DA385ULL;
constexpr std::uint64_t FREEZE_ENTITY_POSITION = 0x428CA6DBD1094446ULL;
constexpr std::uint64_t SET_ENTITY_COLLISION = 0x1A9205C1B9EE827FULL;
constexpr std::uint64_t APPLY_FORCE_TO_ENTITY = 0xC5F68BE9613E2D18ULL;
constexpr std::uint64_t APPLY_DAMAGE_TO_PED = 0x697157CED63F18D4ULL;
constexpr std::uint64_t ADD_EXPLOSION = 0xE3AD2BDBAEE269ACULL;
constexpr std::uint64_t DRAW_LINE = 0x6B7256074AE34680ULL;
constexpr std::uint64_t DRAW_POLY = 0xAC26716048436851ULL;
constexpr std::uint64_t DRAW_LIGHT_WITH_RANGE = 0xF2A1B2771A01DBD4ULL;
constexpr std::uint64_t START_SHAPE_TEST_LOS_PROBE = 0x7EE9F5D83DD4F90EULL;
constexpr std::uint64_t GET_SHAPE_TEST_RESULT = 0x3D87450E15D98694ULL;
constexpr std::uint64_t REQUEST_NAMED_PTFX_ASSET = 0xB80D8756B4668AB6ULL;
constexpr std::uint64_t HAS_NAMED_PTFX_ASSET_LOADED = 0x8702416E512EC454ULL;
constexpr std::uint64_t USE_PARTICLE_FX_ASSET = 0x6C38AF3693A69A91ULL;
constexpr std::uint64_t START_PARTICLE_FX_NON_LOOPED_AT_COORD = 0x25129531F77B9ED3ULL;
constexpr std::uint64_t SET_TIME_SCALE = 0x1D408577D440E81EULL;
constexpr std::uint64_t SHAKE_GAMEPLAY_CAM = 0xFD55E49555E017CFULL;
constexpr std::uint64_t SET_VEHICLE_ENGINE_HEALTH = 0x45F6D8EEF34ABEF1ULL;
constexpr std::uint64_t SET_VEHICLE_ENGINE_ON = 0x2497C4717C8B881EULL;
constexpr std::uint64_t SET_NIGHTVISION = 0x18F621F7A5B1F85DULL;
constexpr std::uint64_t GET_GAMEPLAY_CAM_FOV = 0x65019750A0324133ULL;
// Actor animation natives, for the visual/pose layer in R10.
constexpr std::uint64_t REQUEST_ANIM_DICT = 0xD3BD40951412FEF6ULL;
constexpr std::uint64_t HAS_ANIM_DICT_LOADED = 0xD031A9162D01088CULL;
constexpr std::uint64_t TASK_PLAY_ANIM = 0xEA47FE3719165B94ULL;
constexpr std::uint64_t IS_ENTITY_PLAYING_ANIM = 0x1F0B79228E461EC9ULL;
constexpr std::uint64_t STOP_ANIM_TASK = 0x97FF36A1D40EA00AULL;
// GTA V HUD notifications and native post-processing. Do not substitute CFX hashes.
constexpr std::uint64_t BEGIN_TEXT_COMMAND_THEFEED_POST = 0x202709F4C58A0424ULL;
constexpr std::uint64_t ADD_TEXT_COMPONENT_SUBSTRING_PLAYER_NAME = 0x6C188BE134E074AAULL;
constexpr std::uint64_t END_TEXT_COMMAND_THEFEED_POST_TICKER = 0x2ED7843F8F801023ULL;
constexpr std::uint64_t ANIMPOSTFX_PLAY = 0x2206BF9A37B7F724ULL;
constexpr std::uint64_t ANIMPOSTFX_STOP = 0x068E835A1D0DC0E3ULL;
} // namespace hash
} // namespace shv

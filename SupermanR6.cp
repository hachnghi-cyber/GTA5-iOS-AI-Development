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

struct Config {
    float cruiseSpeed = 45.0f;
    float supersonicSpeed = 170.0f;
    float verticalSpeed = 22.0f;
    float acceleration = 0.06f;
    float jumpPower = 26.0f;
    float shockRadius = 14.0f;
    float beamRange = 160.0f;
    float beamDamage = 18.0f;
    float slowTimeScale = 0.25f;
    bool invincible = true;
    bool noWantedLevel = false;

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
                                       "/Documents/mods/Superman.ini"}) {
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
            if (section == "General") {
                if (key == "Invincible") invincible = value == "true" || value == "1";
                if (key == "NoWantedLevel") noWantedLevel = value == "true" || value == "1";
                if (key == "StartEnabled") startEnabled = value == "true" || value == "1";
            } else if (section == "Flight") {
                setFloat("CruiseSpeed", cruiseSpeed);
                setFloat("SupersonicSpeed", supersonicSpeed);
                setFloat("VerticalSpeed", verticalSpeed);
                setFloat("Acceleration", acceleration);
            } else if (section == "Landing") {
                setFloat("ShockRadius", shockRadius);
            } else if (section == "Jump") {
                setFloat("JumpPower", jumpPower);
            } else if (section == "Laser1") {
                setFloat("Range", beamRange);
                setFloat("Damage", beamDamage);
            } else if (section == "BulletTime") {
                setFloat("TimeScale", slowTimeScale);
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
        beamRange = std::clamp(beamRange, 5.0f, 450.0f);
        slowTimeScale = std::clamp(slowTimeScale, 0.05f, 1.0f);
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

float length(Point3 p) { return std::sqrt(p.x * p.x + p.y * p.y + p.z * p.z); }
Point3 normalized(Point3 p) { const float d = length(p); return d > 0.001f ? scale(p, 1.0f / d) : Point3{}; }

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
    }
    pendingShape = call<int>(hash::START_SHAPE_TEST_LOS_PROBE,
        from.x, from.y, from.z, to.x, to.y, to.z, -1, ignorePed, 7);
    return {result == 2 && hit != 0, entity, result == 2 && hit ? point(end) : to};
}

void drawBeam(Point3 start, Point3 end, int r, int g, int b) {
    call<>(hash::DRAW_LINE, start.x, start.y, start.z, end.x, end.y, end.z,
           r, g, b, 250);
    call<>(hash::DRAW_LIGHT_WITH_RANGE, end.x, end.y, end.z, r, g, b, 6.5f, 3.0f);
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
    std::uint32_t spacePressedAt = 0;
    std::uint32_t lastLaserFx = 0;
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

        if (config.invincible) call<>(hash::SET_ENTITY_INVINCIBLE, ped, true);
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
            bulletTime = !bulletTime;
            call<>(hash::SET_TIME_SCALE, bulletTime ? config.slowTimeScale : 1.0f);
            supermanPlaySound("bullet_time", false);
        }

        if (input.pressed(config.fly)) spacePressedAt = now;
        if (input.down(config.fly) && !flight) {
            call<>(hash::SET_SUPER_JUMP_THIS_FRAME, call<int>(hash::PLAYER_ID));
            if (now - spacePressedAt >= static_cast<std::uint32_t>(config.tapHoldMs) &&
                !call<bool>(hash::IS_PED_IN_ANY_VEHICLE, ped, false)) {
                flight = true;
                smoothedFlight = entityVelocity(ped);
                supermanPlaySound("takeoff", false);
                supermanPlaySound("flight_loop", true);
            }
        }
        if (flight) handleFlight(ped);

        for (int i = 0; i < 5; ++i)
            if (input.pressed(config.beamKeys[i])) beam = i;
        if (input.pressed(config.cycle)) beam = (beam + 1) % 5;
        if (input.down(config.laser)) handleLaser(ped, now);
        if (input.pressed(config.freezeBreath)) coneBreath(ped, true);
        if (input.pressed(config.superBreath)) coneBreath(ped, false);
        if (input.pressed(config.clap)) thunderClap(ped);
        if (input.down(config.tornado)) tornado(ped, now);
        if (input.pressed(config.groundPound)) groundPound(ped);
        if (input.pressed(config.lift)) carryOrThrow(ped);
        if (carriedVehicle) updateCarry(ped);
        if (input.pressed(config.solarFlare)) solarFlare(ped);

        if (combat) handleCombat(ped, now);
    }

    void shutdown(int ped) {
        if (flight) supermanStopSound("flight_loop");
        if (bulletTime) call<>(hash::SET_TIME_SCALE, 1.0f);
        if (xray) call<>(hash::SET_NIGHTVISION, false);
        if (carriedVehicle) call<>(hash::FREEZE_ENTITY_POSITION, carriedVehicle, false);
        if (frozenEntity) call<>(hash::FREEZE_ENTITY_POSITION, frozenEntity, false);
        if (ped && config.invincible) call<>(hash::SET_ENTITY_INVINCIBLE, ped, false);
        enabled = flight = combat = bulletTime = xray = false;
        carriedVehicle = frozenEntity = lockedTarget = 0;
    }

private:
    void toggle(int ped) {
        if (enabled) shutdown(ped);
        else { enabled = true; supermanPlaySound("super_jump", false); }
    }

    void handleFlight(int ped) {
        const Point3 fwd = viewDirection();
        Point3 right{fwd.y, -fwd.x, 0.0f};
        right = normalized(right);
        Point3 move{};
        if (input.down(W)) move = add(move, fwd);
        if (input.down(S)) move = sub(move, fwd);
        if (input.down(A)) move = sub(move, right);
        if (input.down(D)) move = add(move, right);
        if (input.down(config.fly)) move.z += 1.0f;
        if (input.down(config.descend) || input.down(CTRL)) move.z -= 1.0f;
        const bool boost = input.down(config.boost) || input.down(SHIFT);
        const float speed = boost ? config.supersonicSpeed : config.cruiseSpeed;
        const Point3 target = scale(normalized(move), speed);
        const float smoothing = std::clamp(config.acceleration * 2.0f, 0.02f, 0.95f);
        smoothedFlight = add(scale(smoothedFlight, 1.0f - smoothing), scale(target, smoothing));
        if (length(move) < 0.01f) smoothedFlight = scale(smoothedFlight, 0.82f);
        setVelocity(ped, smoothedFlight);
        if (boost && length(move) > 0.1f && !boostPreviously) {
            supermanPlaySound("sonic_boom", false);
            shake(0.35f);
        }
        boostPreviously = boost;
        if ((input.down(config.descend) || input.down(CTRL)) && !input.down(config.fly)) {
            const float speedNow = call<float>(hash::GET_ENTITY_SPEED, ped);
            if (speedNow < 4.0f && length(smoothedFlight) < 3.0f) {
                flight = false;
                smoothedFlight = {};
                supermanStopSound("flight_loop");
            }
        }
    }

    void handleLaser(int ped, std::uint32_t now) {
        static constexpr int colors[5][3] = {
            {255, 50, 22}, {64, 150, 255}, {255, 230, 90},
            {225, 60, 250}, {90, 195, 255}
        };
        static constexpr const char* fx[5] = {
            "bul_carmetal", "bul_carmetal", "exp_grd_flare",
            "ent_dst_gen_gobstop", "exp_grd_bzgas_smoke"
        };
        const RayHit hit = traceRay(ped, config.beamRange);
        const Vec3 head = call<Vec3>(hash::GET_PED_BONE_COORDS,
            ped, 31086, 0.0f, 0.15f, 0.10f);
        const Point3 eye = point(head);
        const auto* c = colors[beam];
        drawBeam(add(eye, {0.04f, 0, 0}), hit.point, c[0], c[1], c[2]);
        drawBeam(add(eye, {-0.04f, 0, 0}), hit.point, c[0], c[1], c[2]);

        if (now - lastLaserFx < (beam == 3 ? 220U : 90U)) return;
        lastLaserFx = now;
        particle(fx[beam], hit.point, beam == 2 ? 2.0f : 0.6f);
        if (hit.hit && hit.entity && hit.entity != ped) {
            if (beam == 4) {
                if (frozenEntity && frozenEntity != hit.entity)
                    call<>(hash::FREEZE_ENTITY_POSITION, frozenEntity, false);
                call<>(hash::FREEZE_ENTITY_POSITION, hit.entity, true);
                frozenEntity = hit.entity;
                thawAt = now + 5000;
            } else if (call<bool>(hash::IS_ENTITY_A_PED, hit.entity)) {
                call<>(hash::APPLY_DAMAGE_TO_PED, hit.entity,
                       static_cast<int>(config.beamDamage * (beam == 0 ? 1.0f : 1.6f)),
                       false, 0, 0);
            } else if (call<bool>(hash::IS_ENTITY_A_VEHICLE, hit.entity)) {
                if (beam == 0 || beam == 1 || beam == 2)
                    call<>(hash::SET_VEHICLE_ENGINE_HEALTH, hit.entity, 10.0f);
            }
        }
        if (beam == 3) explosion(hit.point, 2, 0.2f);
        if (beam == 2 && hit.hit) explosion(hit.point, 18, 0.1f);
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

    void coneBreath(int ped, bool freezing) {
        const RayHit hit = traceRay(ped, 28.0f);
        particle(freezing ? "ent_sht_extinguisher" : "exp_grd_bzgas_smoke",
                 hit.point, 1.2f);
        if (freezing && hit.hit && hit.entity) {
            call<>(hash::FREEZE_ENTITY_POSITION, hit.entity, true);
            frozenEntity = hit.entity;
            thawAt = call<std::uint32_t>(hash::GET_GAME_TIMER) + 4500;
        } else pushTarget(ped, 75.0f, 5.0f);
        supermanPlaySound(freezing ? "freeze_breath" : "super_breath", false);
    }

    void thunderClap(int ped) {
        const Point3 p = entityPosition(ped);
        particle("exp_grd_flare", p, 2.0f);
        shake(0.8f);
        pushTarget(ped, 175.0f, 20.0f);
        supermanPlaySound("thunder_clap", false);
    }

    void tornado(int ped, std::uint32_t now) {
        if (now - lastAttack < 180U) return;
        lastAttack = now;
        pushTarget(ped, 45.0f, 20.0f);
        particle("ent_sht_extinguisher", entityPosition(ped), 1.0f);
        if (input.pressed(config.tornado)) supermanPlaySound("tornado_spin", false);
    }

    void groundPound(int ped) {
        const Point3 p = entityPosition(ped);
        explosion(p, 19, 0.0f);
        pushTarget(ped, 100.0f, 20.0f);
        shake(1.0f);
        supermanPlaySound("ground_pound", false);
    }

    void carryOrThrow(int ped) {
        if (carriedVehicle) {
            const int v = carriedVehicle;
            carriedVehicle = 0;
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

    void updateCarry(int ped) {
        if (!call<bool>(hash::DOES_ENTITY_EXIST, carriedVehicle)) {
            carriedVehicle = 0;
            return;
        }
        const Point3 desired = add(entityPosition(ped), scale(viewDirection(), 5.5f));
        call<>(hash::SET_ENTITY_COORDS_NO_OFFSET, carriedVehicle,
               desired.x, desired.y, desired.z + 1.0f, false, false, false);
    }

    void solarFlare(int ped) {
        const Point3 p = add(entityPosition(ped), scale(viewDirection(), 8.0f));
        explosion(p, 19, 0.2f);
        particle("exp_grd_flare", p, 4.0f);
        pushTarget(ped, 240.0f, 40.0f);
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
        if (input.pressed(config.uppercut)) {
            pushTarget(ped, 90.0f, 85.0f);
            supermanPlaySound("super_punch", false);
        }
        if (input.pressed(config.takedown)) {
            pushTarget(ped, 115.0f, 5.0f);
            supermanPlaySound("super_punch", false);
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

#include "../GameplayCore.hpp"
#include <cassert>
#include <cmath>
#include <iostream>

static bool close(float a, float b, float tolerance = 0.0001f) {
    return std::fabs(a - b) < tolerance;
}

int main() {
    const SMVec3 north = SMCameraForward(0, 0);
    assert(close(north.x, 0) && close(north.y, 1) && close(north.z, 0));
    const SMVec3 east = SMCameraForward(0, -90);
    assert(close(east.x, 1) && close(east.y, 0) && close(east.z, 0));
    const SMVec3 straightUp = SMCameraForward(90, 25);
    assert(close(straightUp.z, 1));
    assert(SMIsFinite(east));
    assert(!SMIsFinite({NAN, 1, 1}));
    SMSettings bad;
    bad.cruiseSpeed = 999.f;
    bad.boostSpeed = -1.f;
    bad.shockRadius = 500.f;
    bad.heatDamage = -2;
    SMSettings safe = SMSanitizeSettings(bad);
    assert(close(safe.cruiseSpeed, 55.f));
    assert(close(safe.boostSpeed, 55.f));
    assert(close(safe.shockRadius, 20.f));
    assert(safe.heatDamage == 0);
    SMButtonClick(SM_TOGGLE);
    SMButtonClick(SM_SHOCK);
    assert(gSMClicks.exchange(0) == (SM_TOGGLE | SM_SHOCK));
    SMButtonHold(SM_UP, true);
    SMButtonHold(SM_FORWARD, true);
    SMButtonHold(SM_UP, false);
    assert(gSMHolds.exchange(0) == SM_FORWARD);
    std::cout << "PASS: math, clamping, key queue\n";
}

# Superman FX R16 — iPhone touch flight and visible landing

Independent experimental Superman-style GTA V iOS ARM64 ScriptHookV mod.
This is source code, **not** the original TamedMods Windows `Superman.asi`.
R16's actual flight/animation feel still requires a real iPhone test.

## Root cause in the user's R15 video

- The iPhone left virtual joystick reported GTA V PAD `INPUT_MOVE_LR` (30) and
  `INPUT_MOVE_UD` (31), but R15 accepted only virtual keys W/A/S/D. Holding
  the custom Fly key (Space) therefore changed only altitude, with no forward
  motion or lateral control.
- The only landing path expected keyboard Ctrl / a separate Descend key. The
  touch screen in the video had no matching, accessible control.
- Pitch-follow `SET_ENTITY_ROTATION` could turn the character/camera toward
  the sky. The skydive animation still isn't a custom Superman mesh or pose.
- Low-speed landings did not draw shockwaves; no accessible landing input meant
  the user almost never saw even the original hard-landing effect.

## R16 behavior

1. **Left-stick flight (mobile) and WASD (Mac):** continuously read PAD 30/31
   and fall back to disabled PAD values or virtual keys. Apply a configurable
   deadzone and preserve analog magnitude for steering. Direction is relative
   to *camera yaw only*; steep camera pitch no longer sends the player skyward.
2. **Fast forward:** continue holding Fly while steering to accelerate toward
   `SupersonicSpeed`; **also** allow the normal Sprint/Chạy control (PAD 21) or
   Shift. When already airborne and holding Fly with a neutral stick, thrust
   forward fast. The short takeoff window still permits upward movement.
3. **Landing accessible on a touch screen:** release Fly after takeoff; while
   hovering with a neutral stick, tap Fly briefly and release to enter a
   controlled automatic descent. Another press interrupts auto-landing.
   Existing Descend keyboard control and original controller PAD 44 still work.
   Near ground, gravity and normal motion are restored.
4. **Contact FX at low and high speeds:** any verified landing creates a short,
   ground-anchored dust burst and expanding ring. Hard landings above the
   original `Landing.ShockwaveMinSpeed` also create a stronger ring, camera
   shake and radial impulse. A ground-Z query backs up height-above-ground
   where available; invalid terrain never triggers a fake blast in mid-air.
5. **Steadier body angle and more visible speed:** camera-pitch-driven body
   tilt is disabled by default. Users can opt into subtle bank in `.ini`.
   Supersonic flight retains the streaks/audio and now emits small spaced
   wake particles and translucent 3D rings, with bounded update frequency.

## How to play R16 on an iPhone

1. Enable Superman with F10/your existing mapped touch shortcut.
2. **Hold Fly** for takeoff. Release it once airborne.
3. **Move the left joystick** to fly forward, backward, left and right.
4. **While steering, hold Fly or Chạy** to fly much faster. Alternatively,
   **hold Fly without moving the stick** for forward superspeed after takeoff.
5. To land, **release the joystick, briefly tap Fly, then release it**.
   You should descend toward the terrain and see a ground ring/dust on contact.

## Configuration

The following optional fields supplement the original Superman.ini:

```ini
[Flight]
StickDeadzone = 0.17
AutoLandingSpeed = 24.0

[VisualsIOS]
FlightBodyTilt = false
SupersonicTrail = true
ShockwaveMeshes = true
```

The code defaults to a stable level body without camera-pitch rotation.
`FlightBodyTilt = true` allows only a small steering bank. Default values are
also used when no Superman.ini has been imported.

## GitHub Actions and IPA workflow

1. Unzip `SupermanFX-R16-Touch-Flight-ARM64-Source.zip` and copy **all contained
   paths** into the existing GitHub repository. The workflow lives in
   `.github/workflows/build-superman-fx-r16.yml`, not inside `superman_port`.
2. In **Actions**, choose **Build Superman FX R16 - iPhone Joystick Flight and
   Landing (ARM64)**, then **Run workflow**. The macOS runner uses Xcode to
   compile the actual ARM64 `.shv.dylib` and verifies its `_DllMain` export.
3. Download `Superman-FX-R16-Touch-Flight-ARM64.zip` from that run. A ZIP
   containing only `SupermanR6.shv.dylib` is the correct build artifact.
4. Integrate it into the matching unchanged **R11 base IPA**, by running:

   ```bash
   python3 superman_port/package_fx_r16.py \
     GTAV-v11.4-SupermanFX-Hold-R11-TEST.ipa \
     SupermanR6.shv.dylib \
     GTAV-v11.4-SupermanFX-R16-TouchFlight-TEST.ipa
   ```

   The packager rejects the wrong base/plugin, verifies that **only** the
   Superman plugin changed, and preserves all 19 sound files. The output
   requires valid iOS app signing before installation.

## Verification performed (host only)

- C++17 host mock test with `-Wall -Wextra -Wpedantic -Werror` passed.
- AddressSanitizer and UndefinedBehaviorSanitizer passed.
- New tests cover analog joystick direction when camera pitch is steep,
  analog left/right, boosting with held Fly and PAD 21 (Sprint), touch-triggered
  auto-landing, ground ring on low-speed touch-down, disabled PAD fallback,
  and terrain height fallback. The older power/action tests are retained.
- The original R15 source is archived in `superman_port/reference/SupermanR15.cpp`
  locally, but is intentionally not included in the source-only build ZIP.

**Still unverified:** actual iOS controller mapping (some ports modify PAD
input), camera stability during flight, physics collision during auto-landing,
particle rendering, FPS and game crashes. This code is not a ready-made tested
IPA; the user must compile it on a Mac or GitHub Actions, then test on iPhone.
CustomKeys' long-hold-versus-drag conflict belongs to the separate touch editor
and is not modified by this Superman-only revision.

## Reference

- Official GTA V PAD native: https://github.com/citizenfx/natives/blob/master/PAD/GetControlNormal.md
- Disabled PAD fallback: https://github.com/citizenfx/natives/blob/master/PAD/GetDisabledControlNormal.md
- Original GTA control IDs 21, 30 and 31: https://github.com/citizenfx/fivem-docs/blob/master/content/docs/game-references/controls.md
- Terrain contact: https://github.com/citizenfx/natives/blob/master/MISC/GetGroundZFor_3dCoord.md

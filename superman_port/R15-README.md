# Superman FX R15 — Flight and action animation fixes (iOS ARM64)

**Experimental independent reimplementation.** This repository contains no
copied code from the Windows TamedMods `Superman.asi`. It uses the supplied
`Superman.ini` as a behavior reference. The visual appearance and iOS runtime
stability are **not yet verified on an iPhone**.

## What changed since R14

1. **Reliable Superman landing.** The previous landing guard required an
   almost stationary player even while descending. R15 lands once the player
   approaches terrain while holding the descend control, restores gravity,
   ends flight audio and bank rotation, then plays the configured original
   landing animation. Hard landings (vertical speed above the original
   `Landing.ShockwaveMinSpeed`) add a ground-anchored expanding ring, dust,
   knockback and camera shake. Normal landings stay quieter.
2. **Ground Pound animation synchronized with impact.** When used while
   flying, the character first enters a downward freefall pose. Only when
   the actor reaches the terrain does the ground attack animation begin.
   The physical impact follows the original animation's `impactMs` marker.
   Invalid terrain height or an unreachable landing cancels the dive after
   3.2 seconds without a phantom explosion.
3. **Hand charge VFX.** Small light sources follow the hands as Thunder Clap
   and Ground Pound charge. Up to two modest sparks are spawned every 190ms
   (not every frame), helping players see that the configured gesture is
   playing. This is a native approximation, not original custom PC particles.
4. **Animation streaming reliability.** On enabling Superman, pre-request
   the hover, flight, takeoff, landing, clap and ground slam dictionaries.
   If the takeoff dictionary becomes ready a little late, retry while the
   takeoff window is active rather than silently dropping the gesture.
5. **No overwritten powers / lost cooldowns.** While a queued action is
   running, a second action cannot silently replace it. If a required
   animation dictionary never loads, the unused Clap/Ground Pound cooldown
   is refunded. Disable/unload clears pending poses and restores gravity,
   post-processing and the animation queue.

R15 retains all R14 C++ functionality: five laser modes with twin-eye
volumetric beams, flight tilt and sonic trail, 3D shockwaves, controlled
particle budget, freeze/super breath, superhero combat, F10 notification,
ScriptHookV gamepad key bridge and original 19 `.wav` sound files **in the
matching R11 host IPA**. Gameplay scripts remain **Story Mode only**.

## Optional configuration

The original `Superman.ini` already contains `[Landing] ShockwaveMinSpeed`.
The R15 visual layer also accepts:

```ini
[VisualsIOS]
FlightBodyTilt = true
SupersonicTrail = true
ActionChargeGlow = true
VolumetricBeams = true
ShockwaveMeshes = true
```

Turn any item off independently if that particular native effect renders
incorrectly on an iPhone or causes FPS drops. The original animation
dictionary/clip names in `[Animations]` and `[Flight]` remain configurable.

## Build on GitHub Actions

1. Extract the `SupermanFX-R15-Flight-Animations-ARM64-Source.zip` and copy
   **all its files preserving paths** into the GitHub repository. An uploaded
   ZIP file alone cannot be compiled by Actions.
2. Open **Actions** and select
   `Build Superman FX R15 - Flight Animations (GTA V iOS ARM64)`.
3. Choose **Run workflow**. After a successful macOS/Xcode build, download
   the `Superman-FX-R15-Flight-ARM64` artifact. It contains the new
   `SupermanR6.shv.dylib` plugin (not a standalone game IPA).
4. To create a test IPA, download the verified original R11 testing IPA and
   compile the new plugin. On a desktop in the repository root:

   ```sh
   python3 superman_port/package_fx_r15.py \
       GTAV-v11.4-SupermanFX-Hold-R11-TEST.ipa \
       SupermanR6.shv.dylib \
       GTAV-v11.4-SupermanFX-R15-Flight-TEST.ipa
   ```

   The packager explicitly checks ARM64 Mach-O + `_DllMain`, validates the
   original IPA's R11 plugin checksum, preserves the sound files and all
   other IPA entries, checks the ZIP CRC, and outputs a validation report.
   The resulting IPA must be signed with a valid iOS signing identity.

## Verification and limitations

- Host C++ regression test: C++17 `-Wall -Wextra -Wpedantic -Werror` **PASS**.
- AddressSanitizer and UndefinedBehaviorSanitizer: **PASS** with native mocks.
- Added tests for hard landing, queued airborne ground slam, hand-effect
  throttling, overlapping actions, missing-animation cooldown refunds,
  late animation loading, and invalid-terrain timeout.
- Not compiled or physically tested with RAGE/Metal on iOS here. Actual
  gravity interaction, bones, animations, FPS and skin rig must be checked on
  device. The original proprietary `.asi` and custom 3D animation assets are
  not included; 99.99% PC visual equivalence cannot honestly be guaranteed.
- This package does **not** change GTA V's CustomKeys touch editor; holding a
  custom button to drag it instead of activating a held power requires a
  separate adjustment to `libgtacompat` / the touch input overlay in the IPA.

## Native reference

- https://github.com/citizenfx/natives/blob/master/TASK/TaskPlayAnim.md
- https://github.com/citizenfx/natives/blob/master/ENTITY/SetEntityRotation.md
- https://github.com/citizenfx/natives/blob/master/GRAPHICS/DrawPoly.md


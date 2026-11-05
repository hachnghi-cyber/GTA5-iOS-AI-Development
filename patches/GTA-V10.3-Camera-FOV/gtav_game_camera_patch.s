.text
.p2align 4
.globl _game_camera_tick
_game_camera_tick:
    // Replaces GTA5 0x10003d254: mov x22,x0
    stp x19,x20, [sp,#-0x20]!
    stp x29,x30, [sp,#0x10]
    mov x19,x0
    adrp x20, _CAM_STATE@PAGE
    add x20,x20,_CAM_STATE@PAGEOFF

    tst x19,#0x4000000000000       // bit 50: first-person vehicle camera
    b.eq _camera_disable
    bl _PLAYER_PED_ID
    cbz w0,_camera_disable
    mov w1,#0
    bl _IS_PED_IN_ANY_VEHICLE
    cbz w0,_camera_disable
    // Do not fight Freecam/scripted/cutscene cameras.
    bl _IS_GAMEPLAY_CAM_RENDERING
    cbz w0,_camera_disable

    ldr w8,[x20,#4]
    cbnz w8,_camera_ensure
    bl _CAM_GET
    str w0,[x20]
    mov w8,#1
    str w8,[x20,#4]

_camera_ensure:
    bl _CAM_GET
    cmp w0,#4
    b.eq _camera_fov_flags
    mov w0,#4
    bl _CAM_SET

_camera_fov_flags:
    mov w8,#0
    tst x19,#0x20000000000000      // bit 53 90deg
    b.eq _maybe_75
    mov w8,#0x42b40000
    b _set_camera_fov
_maybe_75:
    tst x19,#0x10000000000000      // bit 52 75deg
    b.eq _maybe_60
    mov w8,#0x42960000
    b _set_camera_fov
_maybe_60:
    tst x19,#0x8000000000000       // bit 51 60deg
    b.eq _set_camera_fov
    mov w8,#0x42700000
_set_camera_fov:
    str w8,[x20,#8]
    b _camera_tick_done

_camera_disable:
    ldr w8,[x20,#4]
    cbz w8,_camera_disable_zero
    ldr w0,[x20]
    bl _CAM_SET
_camera_disable_zero:
    str wzr,[x20,#4]
    str wzr,[x20,#8]

_camera_tick_done:
    mov x0,x19
    mov x22,x0                 // displaced instruction
    ldp x29,x30,[sp,#0x10]
    ldp x19,x20,[sp],#0x20
    b _GAME_TICK_RESUME

.p2align 4
.globl _first_person_fov_hook
_first_person_fov_hook:
    // Replaces 0x100377b0c: str s8, [x0,#0x5c0]
    adrp x16,_CAM_STATE@PAGE
    add x16,x16,_CAM_STATE@PAGEOFF
    ldr w17,[x16,#4]
    cbz w17,_fp_fov_restore_instr
    ldr w17,[x16,#8]
    cbz w17,_fp_fov_restore_instr
    fmov s8,w17
_fp_fov_restore_instr:
    str s8,[x0,#0x5c0]
    b _FOV_FP_RESUME

.p2align 4
.globl _follow_vehicle_fov_hook
_follow_vehicle_fov_hook:
    // Replaces 0x1003a9d98: ldp x29,x30,[sp,#0x60]
    adrp x16,_CAM_STATE@PAGE
    add x16,x16,_CAM_STATE@PAGEOFF
    ldr w17,[x16,#4]
    cbz w17,_follow_fov_restore_instr
    ldr w17,[x16,#8]
    cbz w17,_follow_fov_restore_instr
    fmov s0,w17
_follow_fov_restore_instr:
    ldp x29,x30,[sp,#0x60]
    b _FOV_FOLLOW_RESUME

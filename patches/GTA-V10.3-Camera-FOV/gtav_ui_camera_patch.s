.text
.p2align 4
.globl _ui_camera_patch
_ui_camera_patch:
    // The overwritten instruction from libgtacompat offset 0x1a95ec
    ldr x22, [sp], #0x10
    stp x19, x20, [sp, #-0x20]!
    stp x22, x23, [sp, #0x10]
    mov x19, x28   // NSMutableArray for Trainer's Player section

    adr x0, _camera_title
    adr x1, _camera_detail
    mov x2, #50
    adr x3, _camera_icon
    bl _make_camera_row

    adr x0, _fov60_title
    adr x1, _fov60_detail
    mov x2, #51
    adr x3, _camera_icon
    bl _make_camera_row

    adr x0, _fov75_title
    adr x1, _fov75_detail
    mov x2, #52
    adr x3, _camera_icon
    bl _make_camera_row

    adr x0, _fov90_title
    adr x1, _fov90_detail
    mov x2, #53
    adr x3, _camera_icon
    bl _make_camera_row

    ldp x22, x23, [sp, #0x10]
    ldp x19, x20, [sp], #0x20
    b _UI_RESUME

.p2align 4
_make_camera_row:
    sub sp, sp, #0x60
    stp x29, x30, [sp, #0x50]
    add x29, sp, #0x50
    // synthetic 56-byte Item{title,detail,kind,code,bit,page,symbol}
    str x0, [sp, #0x10]
    str x1, [sp, #0x18]
    mov w8, #2
    str w8, [sp, #0x20]
    str xzr, [sp, #0x28]
    str x2, [sp, #0x30]
    str wzr, [sp, #0x38]
    str x3, [sp, #0x40]
    add x0, sp, #0x10
    bl _ROWFROM
    mov x2, x0
    mov x0, x19
    bl _OBJCADD
    ldp x29, x30, [sp, #0x50]
    add sp, sp, #0x60
    ret

_camera_title: .asciz "Góc nhìn thứ nhất (ô tô/xe máy)"
_camera_detail: .asciz "Bật/tắt khi đang lái xe; tự khôi phục góc nhìn cũ"
_fov60_title: .asciz "FOV 60° - góc nhìn thứ nhất"
_fov60_detail: .asciz "Chỉ áp dụng khi bật góc nhìn thứ nhất trong xe"
_fov75_title: .asciz "FOV 75° - góc nhìn thứ nhất"
_fov75_detail: .asciz "Ưu tiên hơn 60° nếu bật cả hai"
_fov90_title: .asciz "FOV 90° - góc nhìn thứ nhất"
_fov90_detail: .asciz "Ưu tiên cao nhất; tắt cả ba để về FOV mặc định"
_camera_icon: .asciz "camera.fill"
.p2align 4

# GTA V iOS v12 — Police RP Only v0.7: Integration contract

**STATUS: SOURCE BRIDGE, NOT INJECTED INTO GTA5 / NOT PLAYABLE.**

`Integration/prp_engine_binding.{h,c}` connects the verified C core to abstract
callbacks supplied by GTA5. The integration is real/tested in an in-memory two-client
harness, but **the executable does not call these callbacks yet**.

Required adapters before building a usable IPA:

1. `read_snapshot(ctx, out)` called from **GTA's game thread every frame**.
   Must attest exact Online session ID, host player ID, local player ID, true
   host status, and up to 32 connected peer snapshots. The remote player's
   role, position, and station flags must have a verified engine origin.
   `ios_native_work_probe.c` verifies the exact GTA5 UUID for native job/shift,
   but does **not** prove Online peer identity. An arbitrary player name or
   client-supplied `native_job` is not a valid attestation.
2. `send_authenticated(ctx, receiver, wire, 56)` must be routed through GTA's
   authenticated/multiplexed Online channel, not raw UDP, not the UDP relay,
   not undocumented RAGE event numbers. The receiver must have v0.7 client.
3. On authenticated inbound delivery, engine game-thread dispatch calls
   `prp_bridge_receive(bridge, trusted_sender_id, authenticated_delivery, data, 56)`.
   `trusted_sender_id` and `authenticated_delivery` come from engine transport
   metadata and **not from user-controlled payload**.
4. `local_ped` callbacks apply local ped animations / frame-scoped control
   restrictions. Never modify a remote player's ped. No such GTA native API
   callback is supplied in this package, so actual cuff animation is missing.
5. The engine calls `prp_bridge_set_consent` on explicit opt-in. Selecting an
   existing police job alone does not imply consent for other players.
6. Never set `channel_authenticated=1` or `session_verified=1` as constants;
   default to disabled if the real Online engine has no verified data source.

Note: v12 stock intentionally does not run Menyoo scripts in multiplayer; the
bridge never enables ScriptHookV or invokes Menyoo. Offline NPC arrest stays
unchanged. Host migration resets Police RP including explicit opt-in.

### Why no executable IPA yet?

- The macOS/iOS linker SDK is unavailable in the local Linux environment.
- More importantly, the exact, safe GTA5 game-thread callback and authenticated
  Online message dispatch are **not verified** in the binary. Merely linking
  a dylib would load dormant code, not enable multiplayer arrests.
- No on-device game test exists for this bridge; only sanitizer-backed simulations.
- Do not publish or install an IPA claimed to arrest Online players based on
  this source alone. Avoid memory-patching an unvalidated engine address.

## V0.8: Luồng mạng độc lập với game thread

Network callback chỉ gọi `prp_bridge_enqueue(bridge, ENGINE_TRUSTED_SESSION,
ENGINE_TRUSTED_SENDER, ENGINE_AUTHENTICATED, data, length)`. Không gọi
`prp_bridge_receive` trực tiếp từ network thread, vì thao tác game-thread không
an toàn. Mỗi game-frame phải gọi `prp_bridge_frame` và hàng đợi tối đa 64 gói,
đọc tối đa 32 gói/frame. Hàng đợi được xóa khi chuyển phiên. Nếu không có
trusted-session/sender do engine cấp, **tắt Police RP**.

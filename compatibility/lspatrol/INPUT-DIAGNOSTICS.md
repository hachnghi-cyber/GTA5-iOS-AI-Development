# LSPatrol compatibility validation

Scope: original single-player mod, unchanged. No upstream binary or SDK is included.

1. Verify original ASI registration and script execution in Story Mode.
2. Independently verify F10 key-down, key-up and GetAsyncKeyState. A configured menu key alone does not prove delivery. Use an independent input-only probe; compare with and without the probe because polling may affect edge semantics.
3. Verify the existing directional control callback delivery (NUM8/2/4/6/5/0).
4. Separate missing Windows API imports from observed calls to stub functions. A zero return does not reproduce the API contract; never substitute fabricated success handles or implement callbacks by calling guest addresses directly on a native thread.
5. Obtain an authorized version-matched runtime source before changing the guest API resolver. Validate guest ABI, callback dispatch, object lifetime, cancellation, and error codes independently.
6. Compile the SDK only for companion mods when needed. Its compilation is not evidence of ASI runtime compatibility.

Do not mark iOS runtime compatibility as passed without device evidence. Keep Vietnamese resource configuration separate from the runtime and original game/mod binary.

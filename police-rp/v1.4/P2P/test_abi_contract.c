/* RP-002 compile-time host checks for the public source-facing contract.
 * This does NOT establish a live RAGE hook, arm64 layout, or iPhone build. */
#include "prp_runtime.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdint.h>

_Static_assert(PRP_VERSION == 1u, "RP wire protocol version drift");
_Static_assert(PRP_WIRE_SIZE == 56u, "RP wire packet length drift");
_Static_assert(PRP_MAX_PEERS == 32u, "RP player limit drift");
_Static_assert(PR_ADAPTER_ABI == 2u, "RP engine-view ABI version drift");
_Static_assert(PR_ABI_VERSION == 1u, "RP local policy ABI version drift");
_Static_assert(sizeof(((PRP_Msg *)0)->session_id) == sizeof(uint64_t),
               "RP session IDs must stay 64-bit");

typedef void (*ExpectedTick)(PRP_Runtime *, uint64_t,
                             const PR_EngineView *, const PR_Callbacks *,
                             const PRP_SendCallbacks *);
typedef PRP_Outcome (*ExpectedReceive)(PRP_Runtime *, const uint8_t *,
                                       size_t, const PRP_TransportContext *,
                                       const PR_EngineView *);
typedef void (*ExpectedStop)(PRP_Runtime *, const PR_Callbacks *);
typedef int (*ExpectedConsent)(PRP_Runtime *, uint8_t,
                               const PRP_TransportContext *,
                               const PRP_SendCallbacks *);
typedef int (*ExpectedSend)(void *, uint64_t, const uint8_t *, size_t);

static int mock_authenticated_carrier(void *unused, uint64_t receiver,
                                      const uint8_t *wire, size_t n) {
    (void)unused; (void)wire;
    return receiver != 0 && n == PRP_WIRE_SIZE;
}

int main(void) {
    /* Compile errors are intentional if ABI/source signatures drift. */
    ExpectedTick tick = &prp_runtime_tick;
    ExpectedReceive receive = &prp_runtime_receive;
    ExpectedStop stop = &prp_runtime_stop;
    ExpectedConsent consent = &prp_runtime_consent;
    ExpectedSend send = &mock_authenticated_carrier;
    PRP_SendCallbacks callbacks = {.send = send, .ud = NULL};
    assert(tick != NULL && receive != NULL && stop != NULL && consent != NULL);
    assert(callbacks.send(NULL, 123u, NULL, PRP_WIRE_SIZE) == 1);
    assert(callbacks.send(NULL, 123u, NULL, PRP_WIRE_SIZE - 1u) == 0);
    puts("Police RP v12 source API signatures and version constants OK (host only)");
    return 0;
}

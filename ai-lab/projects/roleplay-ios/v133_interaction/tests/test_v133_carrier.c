/* Synthetic regression for an independently observed native payload mutation.
 * This model is NOT an engine, network, signature, or two-iPhone test.
 */
#include "rp_v133_carrier.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void observed_slot_normalization(uint8_t *payload, uint8_t actual_slot) {
    if (payload[8] != actual_slot) {
        payload[8] = actual_slot;
        payload[9] = payload[10] = payload[11] = 0;
    }
}

int main(void) {
    const rp_v133_action original = {UINT64_C(0x123456789abcdef0), 22, 7, 3, RP_V133_GREET};
    rp_v133_action decoded = {0};
    uint8_t bare[RP_V133_WIRE_BYTES];
    assert(rp_v133_wire_encode(&original, bare, sizeof bare));
    observed_slot_normalization(bare, 5);
    assert(rp_v133_wire_decode(bare, sizeof bare, &decoded));
    assert(decoded.session_id != original.session_id); /* Old bare carrier is unsafe. */

    uint8_t carrier[RP_V133_CARRIER_BYTES], saved[RP_V133_CARRIER_BYTES];
    assert(rp_v133_carrier_encode(&original, carrier, sizeof carrier));
    observed_slot_normalization(carrier, 5);
    assert(rp_v133_wire_decode(carrier+16, 40, &decoded));
    assert(decoded.session_id == original.session_id && decoded.nonce == original.nonce);
    memcpy(saved, carrier, sizeof saved);
    rp_v133_mailbox box;
    rp_v133_mailbox_init(&box);
    rp_v133_delivery trusted = {111, original.session_id, original.epoch, 0};
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    assert(box.count == 0); /* Engine-normalized slot is not sufficient trust. */
    trusted.authenticated = 1; /* Explicit host fixture, never production evidence. */
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_QUEUED);
    assert(box.count == 1 && box.entries[0].trusted.transport_sender == 111);
    assert(memcmp(box.entries[0].wire, carrier+16, 40) == 0);
    assert(memcmp(saved, carrier, sizeof saved) == 0); /* Original engine event untouched. */
    assert(rp_v133_carrier_enqueue(&box, NULL, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    trusted.transport_epoch++;
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    trusted.transport_epoch--;
    trusted.transport_session++;
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    trusted.transport_session--;
    trusted.authenticated = 2;
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    trusted.authenticated = 1;
    for (size_t n=0; n<sizeof carrier; ++n)
        assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, n) != RP_V133_CARRIER_QUEUED);
    carrier[12] = 1;
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    carrier[12] = 0;
    carrier[20] = 99; /* Inner wire version. */
    assert(rp_v133_carrier_enqueue(&box, &trusted, carrier, sizeof carrier) == RP_V133_CARRIER_DENIED);
    uint8_t stock[244] = {'M','P','J','2'};
    assert(rp_v133_carrier_enqueue(&box, &trusted, stock, sizeof stock) == RP_V133_CARRIER_NOT_OURS);
    assert(rp_v133_carrier_enqueue(&box, &trusted, bare, sizeof bare) == RP_V133_CARRIER_NOT_OURS);
    assert(!rp_v133_carrier_encode(NULL, carrier, sizeof carrier));
    assert(!rp_v133_carrier_encode(&original, carrier, sizeof carrier-1));
    puts("P9 carrier mutation/isolation/trust tests PASS (synthetic only)");
    return 0;
}

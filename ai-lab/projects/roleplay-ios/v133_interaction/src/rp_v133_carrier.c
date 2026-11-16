#include "rp_v133_carrier.h"

static const uint8_t marker[8] = {'P','R','P','3','E','V','0','1'};

int rp_v133_carrier_encode(const rp_v133_action *action,
                           uint8_t *out, size_t size) {
    if (!out || size != RP_V133_CARRIER_BYTES) return 0;
    uint8_t frame[RP_V133_CARRIER_BYTES] = {0};
    if (!rp_v133_wire_encode(action, frame + RP_V133_CARRIER_HEADER_BYTES,
                             RP_V133_WIRE_BYTES)) return 0;
    for (unsigned i=0; i<sizeof marker; ++i) frame[i] = marker[i];
    for (unsigned i=0; i<sizeof frame; ++i) out[i] = frame[i];
    return 1;
}

rp_v133_carrier_result rp_v133_carrier_enqueue(
    rp_v133_mailbox *box, const rp_v133_delivery *trusted,
    const uint8_t *payload, size_t size) {
    if (!payload || size < sizeof marker) return RP_V133_CARRIER_NOT_OURS;
    for (unsigned i=0; i<sizeof marker; ++i)
        if (payload[i] != marker[i]) return RP_V133_CARRIER_NOT_OURS;
    if (size != RP_V133_CARRIER_BYTES) return RP_V133_CARRIER_DENIED;
    /* Bytes 8..11 are engine scratch, NEVER an identity or authentication flag. */
    for (unsigned i=12; i<RP_V133_CARRIER_HEADER_BYTES; ++i)
        if (payload[i]) return RP_V133_CARRIER_DENIED;
    rp_v133_action action = {0};
    const uint8_t *wire = payload + RP_V133_CARRIER_HEADER_BYTES;
    if (!trusted || trusted->authenticated != 1 ||
        !rp_v133_wire_decode(wire, RP_V133_WIRE_BYTES, &action) ||
        action.session_id != trusted->transport_session ||
        action.epoch != trusted->transport_epoch)
        return RP_V133_CARRIER_DENIED;
    return rp_v133_mailbox_enqueue(box, trusted, wire, RP_V133_WIRE_BYTES)
        ? RP_V133_CARRIER_QUEUED : RP_V133_CARRIER_DENIED;
}

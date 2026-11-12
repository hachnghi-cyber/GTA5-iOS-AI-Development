#ifndef PRP_TRANSPORT_PORT_H
#define PRP_TRANSPORT_PORT_H
#include "prp_event_isolation.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Thin, dependency-injected glue layer for a FUTURE game engine integration.
 * The "send_private" endpoint MUST transmit over a dedicated authenticated
 * police route. It MUST NOT inject data into MPJ2 or a raw UDP socket.
 * This source intentionally DOES NOT install a hook into GTA5. */
typedef int (*PRP_SendPrivateEvent)(void *ctx, uint64_t receiver,
                                   const uint8_t *carrier, size_t n);
typedef struct {
    PRP_GameBridge bridge;
    PRP_EngineCallbacks underlying;
    PRP_SendPrivateEvent send_private;
    void *send_ctx;
    uint32_t outbound_rejected;
} PRP_TransportPort;
/* These callbacks must originate in the verified GTA frame/transport adapter;
 * never populate them from network data, an INI or a client-supplied username. */
void prp_port_init(PRP_TransportPort *port,
                   const PRP_EngineCallbacks *engine,
                   PRP_SendPrivateEvent send_private,
                   void *send_ctx);
int prp_port_frame(PRP_TransportPort *port);
void prp_port_consent(PRP_TransportPort *port,int enable);
PRP_Outcome prp_port_arrest(PRP_TransportPort *port,uint8_t op,
                            uint64_t target,uint32_t jail_ms);
/* The raw event is passed to the original game unchanged unless a separate,
 * engine authenticated RP event route has explicitly been selected. */
PRP_EventDecision prp_port_deliver(PRP_TransportPort *port,
                        const uint8_t *carrier,size_t n,
                        const PRP_EventRoute *route);
/* Must be called on game thread after disconnect; new callbacks resume only
 * after an independently verified session. */
void prp_port_stop(PRP_TransportPort *port);
#ifdef __cplusplus
}
#endif
#endif

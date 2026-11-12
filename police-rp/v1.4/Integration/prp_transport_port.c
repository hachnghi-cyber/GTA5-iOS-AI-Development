#include "prp_transport_port.h"
#include <string.h>
static int read_bridge_snapshot(void *ctx,PRP_GameSnapshot *out) {
    PRP_TransportPort *p=(PRP_TransportPort *)ctx;
    return p && p->underlying.read_snapshot &&
        p->underlying.read_snapshot(p->underlying.userdata,out);
}
static int send_bridge_wire(void *ctx,uint64_t to,
                            const uint8_t *wire,size_t n) {
    PRP_TransportPort *p=(PRP_TransportPort *)ctx;
    uint8_t carrier[PRP_CANDIDATE_CARRIER_SIZE];
    if(!p || !p->send_private || n!=PRP_WIRE_SIZE ||
       !prp_carrier_pack(carrier,wire)) {
        if(p)p->outbound_rejected++;
        return 0;
    }
    /* No access to stock MPJ2 dispatcher here. The future engine adapter
     * must offer a separate authenticated Police RP channel. */
    if(p->send_private(p->send_ctx,to,carrier,sizeof(carrier))!=1) {
        p->outbound_rejected++;
        return 0;
    }
    return 1;
}
void prp_port_init(PRP_TransportPort *p,const PRP_EngineCallbacks *engine,
                   PRP_SendPrivateEvent send_private,void *send_ctx) {
    if(!p)return;
    memset(p,0,sizeof(*p));
    if(engine)p->underlying=*engine;
    p->send_private=send_private;
    p->send_ctx=send_ctx;
    PRP_EngineCallbacks cb={0};
    cb.read_snapshot=read_bridge_snapshot;
    cb.send_authenticated=send_bridge_wire;
    cb.userdata=p;
    if(engine)cb.local_ped=engine->local_ped;
    prp_bridge_init(&p->bridge,&cb);
}
int prp_port_frame(PRP_TransportPort *p){
    return p?prp_bridge_frame(&p->bridge):0;
}
void prp_port_consent(PRP_TransportPort *p,int enable){
    if(p)prp_bridge_set_consent(&p->bridge,enable);
}
PRP_Outcome prp_port_arrest(PRP_TransportPort *p,uint8_t op,
                            uint64_t target,uint32_t jail_ms){
    return p?prp_bridge_arrest(&p->bridge,op,target,jail_ms):PRP_ERR_SESSION;
}
PRP_EventDecision prp_port_deliver(PRP_TransportPort *p,
                     const uint8_t *carrier,size_t n,
                     const PRP_EventRoute *route) {
    /* In particular: never reinterpret a stock game event as a Police RP
       event based on its payload magic. */
    if(!route || !route->on_separate_police_route)
        return PRP_PASS_TO_ORIGINAL_GAME;
    if(!p)return PRP_PRIVATE_REJECTED;
    return prp_isolate_inbound(&p->bridge,carrier,n,route);
}
void prp_port_stop(PRP_TransportPort *p){
    if(p)prp_bridge_stop(&p->bridge);
}

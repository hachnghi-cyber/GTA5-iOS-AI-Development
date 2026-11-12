#include "prp_candidate_carrier.h"
#include <string.h>

/* CRC32 detects corruption, NOT tampering. Transport auth remains required. */
static uint32_t crc32(const uint8_t *p,size_t n){
    uint32_t crc=0xffffffffu;
    for(size_t i=0;i<n;i++){
        crc^=p[i];
        for(unsigned j=0;j<8;j++)
            crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);
    }
    return ~crc;
}
static void put32(uint8_t *p,uint32_t v){
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);
    p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}
static uint32_t get32(const uint8_t *p){
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|
           ((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
int prp_carrier_pack(uint8_t out[PRP_CANDIDATE_CARRIER_SIZE],
                     const uint8_t wire[PRP_WIRE_SIZE]){
    PRP_Msg m;
    if(!out||!wire||!prp_decode(&m,wire,PRP_WIRE_SIZE))return 0;
    memset(out,0,PRP_CANDIDATE_CARRIER_SIZE);
    memcpy(out,"PRC1",4);
    out[4]=1;
    out[6]=(uint8_t)PRP_WIRE_SIZE;
    memcpy(out+PRP_CANDIDATE_PAYLOAD_OFFSET,wire,PRP_WIRE_SIZE);
    put32(out+PRP_CANDIDATE_CRC_OFFSET,crc32(wire,PRP_WIRE_SIZE));
    return 1;
}
int prp_carrier_unpack(uint8_t wire[PRP_WIRE_SIZE],
                       const uint8_t *data,size_t n,
                       const PRP_TrustedDelivery *trusted){
    if(!wire||!data||!trusted||n!=PRP_CANDIDATE_CARRIER_SIZE||
       !trusted->authenticated||!trusted->trusted_session_id||
       !trusted->trusted_sender_id||memcmp(data,"PRC1",4)!=0||
       data[4]!=1||data[5]!=0||data[6]!=PRP_WIRE_SIZE||data[7]!=0)
        return 0;
    for(size_t i=PRP_CANDIDATE_CRC_OFFSET+4;i<n;i++)
        if(data[i])return 0;
    const uint8_t *p=data+PRP_CANDIDATE_PAYLOAD_OFFSET;
    if(crc32(p,PRP_WIRE_SIZE)!=get32(data+PRP_CANDIDATE_CRC_OFFSET))
        return 0;
    PRP_Msg m;
    if(!prp_decode(&m,p,PRP_WIRE_SIZE)||
       m.sender_id!=trusted->trusted_sender_id||
       m.session_id!=trusted->trusted_session_id)
        return 0;
    memcpy(wire,p,PRP_WIRE_SIZE);
    return 1;
}
int prp_carrier_enqueue(PRP_GameBridge *bridge,const uint8_t *data,size_t n,
                        const PRP_TrustedDelivery *trusted){
    if(!bridge||!trusted)return 0;
    uint8_t wire[PRP_WIRE_SIZE];
    if(!prp_carrier_unpack(wire,data,n,trusted))return 0;
    return prp_bridge_enqueue(bridge,trusted->trusted_session_id,
          trusted->trusted_sender_id,trusted->authenticated,wire,sizeof(wire));
}

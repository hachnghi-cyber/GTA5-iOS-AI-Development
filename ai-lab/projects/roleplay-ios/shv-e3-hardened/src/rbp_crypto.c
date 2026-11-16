#include "rbp_wire_c.h"
#ifdef __APPLE__
/* iPhoneOS SDK: CommonCrypto is available via system frameworks. */
#include <CommonCrypto/CommonHMAC.h>
int rbp_hmac_sha256(const uint8_t key[32],const uint8_t *data,size_t n,uint8_t out[32]) {
    if(!key||!data||!out)return 0;
    CCHmac(kCCHmacAlgSHA256,key,32,data,n,out);
    return 1;
}
#else
#include <openssl/hmac.h>
#include <openssl/evp.h>
int rbp_hmac_sha256(const uint8_t key[32],const uint8_t *data,size_t n,uint8_t out[32]) {
    unsigned length=0;
    if(!key||!data||!out)return 0;
    return HMAC(EVP_sha256(),key,32,data,n,out,&length)!=NULL && length==32;
}
#endif

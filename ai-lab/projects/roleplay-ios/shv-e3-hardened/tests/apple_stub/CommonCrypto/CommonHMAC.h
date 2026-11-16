/* TEST ONLY: fake CommonCrypto declaration, NOT an Apple SDK header. */
#ifndef RBP_TEST_COMMONCRYPTO_H
#define RBP_TEST_COMMONCRYPTO_H
#include <stddef.h>
#define kCCHmacAlgSHA256 2
void CCHmac(int algorithm,const void *key,size_t key_length,
           const void *data,size_t data_length,void *mac_out);
#endif

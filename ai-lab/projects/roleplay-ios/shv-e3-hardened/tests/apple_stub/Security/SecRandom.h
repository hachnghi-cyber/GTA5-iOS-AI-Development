/* TEST ONLY. Not an Apple SDK header. */
#ifndef RBP_TEST_SECURITY_SECRANDOM_H
#define RBP_TEST_SECURITY_SECRANDOM_H
#include <stddef.h>
typedef const struct __SecRandom *SecRandomRef;
#define kSecRandomDefault ((SecRandomRef)0)
int SecRandomCopyBytes(SecRandomRef rnd,size_t count,void *bytes);
#endif

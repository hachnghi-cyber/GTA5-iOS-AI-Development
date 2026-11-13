/* Non-Apple safety contract: return failure, clear output, ignore anchors. */
#include "rp_v13_dladdr_identity.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    RP_V13_IdentityEvidence evidence;
    memset(&evidence, 0xFF, sizeof(evidence));
    assert(rp_v13_dladdr_collect_identity((const void *)1,(const void *)2,&evidence)==0);
    assert(evidence.abi==0u);
    assert(evidence.executable_uuid_verified_by_loader==0u);
    assert(evidence.compat_uuid_verified_by_loader==0u);
    assert(rp_v13_dladdr_collect_identity(NULL,NULL,NULL)==0);
    puts("RP v13 dladdr non-Apple fail-closed PASS: 5 checks (host-only)");
    return 0;
}

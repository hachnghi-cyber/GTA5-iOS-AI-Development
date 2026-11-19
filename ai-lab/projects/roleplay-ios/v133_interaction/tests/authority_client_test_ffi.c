/* Test-only opaque boundary for exercising the native C client over real TLS.
 * Never included in the normal server library or iOS dylib. */
#include "rp_v133_authority_client.h"
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT void *test_client_create(uint64_t id) {
    rp_authority_client *client = calloc(1, sizeof *client);
    if (!rp_authority_client_init(client, id)) { free(client); return NULL; }
    return client;
}
EXPORT void test_client_destroy(void *client) { free(client); }
EXPORT int test_client_receive(void *client, const uint8_t *header, size_t header_size,
                                const uint8_t *payload, size_t size) {
    uint8_t kind;
    uint32_t length;
    if (!rp_authority_record_header(header, header_size, &kind, &length) || length != size) {
        rp_authority_client_stop(client);
        return 0;
    }
    return rp_authority_client_receive(client, kind, payload, size);
}
EXPORT int test_client_request(void *client, uint32_t op, uint64_t target, uint8_t *out, size_t size) {
    return rp_authority_client_request(client, (rp_police_operation)op, target, out, size);
}
EXPORT int test_client_row(void *handle, uint64_t id, uint64_t *out, size_t count) {
    const rp_authority_client *client = handle;
    if (!client || !out || count != 10) return 0;
    memset(out, 0, sizeof(uint64_t) * count);
    for (uint32_t i = 0; i < client->member_count; ++i)
        if (client->members[i][0] == id) {
            memcpy(out, client->members[i], sizeof client->members[i]);
            return 1;
        }
    return 0;
}
EXPORT uint64_t test_client_revision(const void *handle) {
    const rp_authority_client *client = handle;
    return client ? client->revision : 0;
}
EXPORT int test_client_consent_step(void *client, uint32_t *phase, uint8_t *out, size_t size) {
    rp_consent_probe_phase value = (rp_consent_probe_phase)*phase;
    rp_consent_probe_result result = rp_authority_consent_probe_step(client, &value, out, size);
    *phase = (uint32_t)value;
    return result;
}

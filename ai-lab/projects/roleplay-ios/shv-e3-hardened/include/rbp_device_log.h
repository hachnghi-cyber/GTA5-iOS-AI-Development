#ifndef RBP_DEVICE_LOG_H
#define RBP_DEVICE_LOG_H
/* Diagnostic-only: no identifiers, IP addresses or cryptographic secrets. */
#ifdef __cplusplus
extern "C" {
#endif
void rbp_logf(const char *format, ...);
#ifdef __cplusplus
}
#endif

#endif /* RBP_DEVICE_LOG_H */

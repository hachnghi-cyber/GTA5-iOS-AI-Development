#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <poll.h>
#include <errno.h>
#include <time.h>
#define ERRNO errno
#define NONBLOCK O_NONBLOCK
#define CLOCK_MONO CLOCK_MONOTONIC
#ifdef __APPLE__
#define SEND_FLAGS 0
#else
#define SEND_FLAGS MSG_NOSIGNAL
#endif
#define SOL SOL_SOCKET
#define SOERR SO_ERROR

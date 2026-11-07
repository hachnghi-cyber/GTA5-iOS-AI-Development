#include "GojoTouchQueue.h"
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>

static void *press_action(void *arg)
{
    unsigned int action = (unsigned int)(uintptr_t)arg;
    for (unsigned int n = 0; n < 100000; n++) gojo_touch_press(action);
    return NULL;
}

int main(void)
{
    assert(gojo_touch_consume() == 0);
    gojo_touch_press(0);
    gojo_touch_press(4);
    gojo_touch_press(4);
    assert(gojo_touch_consume() == 0x11u);
    assert(gojo_touch_consume() == 0);
    gojo_touch_press(5);
    gojo_touch_press(999);
    assert(gojo_touch_consume() == 0);

    pthread_t workers[5];
    for (unsigned int i = 0; i < 5; i++)
        assert(pthread_create(&workers[i], NULL, press_action, (void *)(uintptr_t)i) == 0);
    for (unsigned int i = 0; i < 5; i++)
        assert(pthread_join(workers[i], NULL) == 0);
    assert(gojo_touch_consume() == 0x1fu);
    gojo_touch_press(3);
    gojo_touch_clear();
    assert(gojo_touch_consume() == 0);
    puts("GojoTouchQueue: all tests passed");
    return 0;
}

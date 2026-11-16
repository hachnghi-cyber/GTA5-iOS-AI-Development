/* Mock ONLY: verifies native invocation ordering. Not an actual RAGE test. */
#include "rbp_native_adapter.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint64_t hashes[8];
static uint64_t args[10];
static int n_init=0,n_push=0,n_call=0;
static uint64_t ret=0;
static void fake_init(uint64_t hash){assert(n_init<8);hashes[n_init++]=hash;}
static void fake_push(uint64_t arg){assert(n_push<10);args[n_push++]=arg;}
static uint64_t *fake_call(void){n_call++;return &ret;}
int main(void){
 rbp_handoff h; rbp_handoff_init(&h);
 rbp_native_api api = {fake_init,fake_push,fake_call};
 assert(rbp_diagnostic_game_tick(&h,&api)==0);
 rbp_diag_event event={0}; event.type=1;event.sequence=42;
 assert(rbp_handoff_push(&h,&event)==1);
 assert(rbp_diagnostic_game_tick(&h,&api)==1);
 assert(n_init==3 && n_push==4 && n_call==3);
 assert(hashes[0]==UINT64_C(0xB87A37EEB7FAA67D));
 assert(hashes[1]==UINT64_C(0x6C188BE134E074AA));
 assert(hashes[2]==UINT64_C(0x9D77056A530643F6));
 assert(strcmp((const char*)(uintptr_t)args[0],"STRING")==0);
 assert(strcmp((const char*)(uintptr_t)args[1],"RBP1 REMOTE E3 PING")==0);
 assert(args[2]==1500 && args[3]==1);
 assert(rbp_diagnostic_game_tick(&h,&api)==0);
 assert(rbp_local_probe_action(&api)==1);
 assert(n_init==6 && n_call==6 && n_push==8);
 printf("PASS mocked E1+E3 HUD adapter: 6 calls, 8 args, no real GTA\n");
 return 0;
}

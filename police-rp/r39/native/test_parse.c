#include <stdio.h>
#include <assert.h>
#include "frame.h"
int main(void){Frame f={0};assert(parse_line(&f,"[rp-r35] ms=1 online=1 slot=1 alive=1 xyz_cm=1,2,3 mask=0x00000003 nearest=0 dist_cm=100 custom=0x80")==1);assert(parse_line(&f,"[rp-r35-request] slot=1 target=2 dist_cm=100 alive=1")==0);assert(parse_line(&f,"[rp-r35-request] slot=1 target=0 dist_cm=100 alive=1")==2&&f.pressed);assert(parse_line(&f,"[rp-r35] ms=2 tick=1 skipped=2")==-1&&!f.valid);assert(parse_line(&f,"[rp-r35-request] slot=1 target=0 dist_cm=100 alive=1")==0);puts("PASS parser");}

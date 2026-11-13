#include "../native/PointValidation.hpp"
#include <cassert>
#include <initializer_list>
#include <limits>
int main(){
 using namespace v12plus;
 assert(valid({0,0,1}));assert(valid({9500,-9500,-200}));
 assert(!valid({std::numeric_limits<float>::quiet_NaN(),0,0}));
 assert(!valid({10001,0,0}));assert(!valid({0,0,5001}));
 assert(allowAction(Action::Save,false,true,false));
 assert(allowAction(Action::Waypoint,false,true,false));
 assert(!allowAction(Action::Return,false,true,false));
 assert(allowAction(Action::Return,false,true,true));
 for(Action a:{Action::Save,Action::Return,Action::Waypoint}){
  assert(!allowAction(a,true,true,true));assert(!allowAction(a,false,false,true));
 }
 assert(!allowAction(Action::None,false,true,true));
}

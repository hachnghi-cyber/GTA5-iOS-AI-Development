#pragma once
#include <cmath>
#include <cstdint>
namespace v12plus {
struct Point {float x,y,z;};
enum class Action:int {None=0,Save=1,Return=2,Waypoint=3};
inline bool valid(Point p) {
 return std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z)&&
 p.x>=-10000.f&&p.x<=10000.f&&p.y>=-10000.f&&p.y<=10000.f&&
 p.z>=-1000.f&&p.z<=5000.f;
}
inline bool allowAction(Action a,bool online,bool pedExists,bool hasSaved){
 if(online||!pedExists)return false;
 if(a==Action::Return)return hasSaved;
 return a==Action::Save||a==Action::Waypoint;
}
}

// Independently implemented GTA V iOS v12 ScriptHook location prototype.
// Only Story Mode; iOS/arm64 + UIKit. NOT verified on iPhone.
#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#include "PointValidation.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <type_traits>

namespace {
using namespace v12plus;
std::atomic<int> queued{0};
using Reg=void (*)(void*,void(*)());
using Unreg=void (*)(void*);
using Wait=void (*)(uint32_t);
using Init=void (*)(uint64_t);
using Push=void (*)(uint64_t);
using Call=uint64_t *(*)();
struct API {void *h=nullptr;Reg reg=nullptr;Unreg unreg=nullptr;Wait wait=nullptr;Init init=nullptr;Push push=nullptr;Call call=nullptr;};
API api;
void *module=nullptr;
UIButton *mainButton=nil;
NSArray<UIButton*> *actions=nil;
constexpr uint64_t NETWORK_IS_SESSION_STARTED=0x9DE624D2FC4B603FULL;
constexpr uint64_t PLAYER_PED_ID=0xD80958FC74E988A6ULL;
constexpr uint64_t DOES_ENTITY_EXIST=0x7239B21A38F536BAULL;
constexpr uint64_t GET_ENTITY_COORDS=0x3FEF770D40960D5AULL;
constexpr uint64_t SET_ENTITY_COORDS_NO_OFFSET=0x239A3351AC1DA385ULL;
constexpr uint64_t IS_WAYPOINT_ACTIVE=0x1DD1F58F493F1DA5ULL;
constexpr uint64_t GET_FIRST_BLIP_INFO_ID=0x1BEDE233E6CD2A1FULL;
constexpr uint64_t DOES_BLIP_EXIST=0xA6DB27D19ECBB7DAULL;
constexpr uint64_t GET_BLIP_INFO_ID_COORD=0xFA7C7F0AADF25D09ULL;
constexpr uint64_t GET_GROUND_Z_FOR_3D_COORD=0xC906A7DAB05C8D2BULL;
struct alignas(8) SHVVec3 {float x;uint32_t px;float y;uint32_t py;float z;uint32_t pz;};
static_assert(sizeof(SHVVec3)==24,"ScriptHook vector ABI must be padded");
uint64_t bits(float f){uint64_t v=0;std::memcpy(&v,&f,sizeof(f));return v;}
uint64_t bits(int i){return static_cast<uint64_t>(static_cast<int64_t>(i));}
uint64_t bits(bool b){return b?1u:0u;}
uint64_t bits(float *p){return reinterpret_cast<uintptr_t>(p);}
template<typename R=uint64_t,typename... P> R invoke(uint64_t hash,P... args){
 api.init(hash);
 (api.push(bits(args)),...);
 uint64_t *r=api.call();
 if constexpr(std::is_void_v<R>)return;
 else {R out{};if(r)std::memcpy(&out,r,sizeof(out));return out;}
}
UIViewController *frontView(){
 UIApplication *app=UIApplication.sharedApplication;
 for(UIScene *s in app.connectedScenes){
  if (![s isKindOfClass:UIWindowScene.class]||s.activationState!=UISceneActivationStateForegroundActive)continue;
  for(UIWindow *w in static_cast<UIWindowScene*>(s).windows)if(w.isKeyWindow&&w.rootViewController)return w.rootViewController;
 }
 return nil;
}
void updateTitle(NSString *title){
 dispatch_async(dispatch_get_main_queue(),^{if(mainButton)[mainButton setTitle:title forState:UIControlStateNormal];});
}
bool loadSaved(Point *out){
 NSArray *a=[[NSUserDefaults standardUserDefaults] arrayForKey:@"v12plus.saved_place.v1"];
 if(![a isKindOfClass:NSArray.class]||a.count!=3)return false;
 for(id item in a)if(![item isKindOfClass:NSNumber.class])return false;
 Point p{[a[0] floatValue],[a[1] floatValue],[a[2] floatValue]};
 if(!valid(p))return false;*out=p;return true;
}
void savePoint(Point p){
 if(valid(p))[[NSUserDefaults standardUserDefaults] setObject:@[@(p.x),@(p.y),@(p.z)] forKey:@"v12plus.saved_place.v1"];
}
Point getPosition(int ped){
 auto v=invoke<SHVVec3>(GET_ENTITY_COORDS,ped,false);
 return {v.x,v.y,v.z};
}
void teleport(int ped,Point p){
 invoke<void>(SET_ENTITY_COORDS_NO_OFFSET,ped,p.x,p.y,p.z,false,false,true);
}
void gameMain(){
 std::fprintf(stderr,"[V12_PLUS] script_main_started\n");
 for(;;){
  int requested=queued.exchange(0,std::memory_order_acq_rel);
  if(requested){
   @autoreleasepool {
    const Action a=static_cast<Action>(requested);
    bool online=invoke<uint64_t>(NETWORK_IS_SESSION_STARTED)!=0;
    int ped=static_cast<int>(invoke<uint64_t>(PLAYER_PED_ID));
    bool exists=ped>0&&invoke<uint64_t>(DOES_ENTITY_EXIST,ped)!=0;
    Point saved{};
    bool hasSaved=loadSaved(&saved);
    if(!allowAction(a,online,exists,hasSaved))updateTitle(online?@"Chỉ Story":@"Chưa có vị trí");
    else if(a==Action::Save){
     Point p=getPosition(ped);
     if(valid(p)){savePoint(p);updateTitle(@"Đã lưu");}
     else updateTitle(@"Vị trí lỗi");
    }else if(a==Action::Return){
     teleport(ped,saved);updateTitle(@"Đã về");
    }else if(a==Action::Waypoint){
     if(!invoke<uint64_t>(IS_WAYPOINT_ACTIVE))updateTitle(@"Chưa đánh dấu");
     else{
      int blip=static_cast<int>(invoke<uint64_t>(GET_FIRST_BLIP_INFO_ID,8));
      if(blip<=0||!invoke<uint64_t>(DOES_BLIP_EXIST,blip))updateTitle(@"Không có waypoint");
      else{
       SHVVec3 v=invoke<SHVVec3>(GET_BLIP_INFO_ID_COORD,blip);
       Point p{v.x,v.y,v.z};float ground=0;bool found=false;
       if(valid(p)){
        for(float height=950.f;height>=0.f;height-=50.f){
         if(invoke<uint64_t>(GET_GROUND_Z_FOR_3D_COORD,p.x,p.y,height,&ground,false,false)){
          if(std::isfinite(ground)&&ground>-500.f&&ground<3000.f){
           p.z=ground+1.5f;found=valid(p);break;
          }
         }
        }
       }
       if(found){teleport(ped,p);updateTitle(@"Đã tới điểm");}
       else updateTitle(@"Không thấy mặt đất");
      }
     }
    }
   }
  }
  api.wait(0);
 }
}
}

@interface V12PlacesControl:NSObject
@property(nonatomic,assign) BOOL expanded;
- (void)attach;
- (void)onMain:(UIButton*)sender;
- (void)onAction:(UIButton*)sender;
@end

@implementation V12PlacesControl
- (void)attach{
 if(mainButton)return;
 UIViewController *vc=frontView();
 if(!vc||!vc.view||vc.view.bounds.size.width<100)return;
 UIView *host=vc.view;
 CGFloat x=host.bounds.size.width-84;
 CGFloat y=std::max<CGFloat>(110,host.bounds.size.height*0.40);
 mainButton=[UIButton buttonWithType:UIButtonTypeSystem];
 mainButton.frame=CGRectMake(x,y,72,44);
 mainButton.backgroundColor=[[UIColor blackColor] colorWithAlphaComponent:0.55];
 [mainButton setTitle:@"📍" forState:UIControlStateNormal];
 [mainButton setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
 mainButton.titleLabel.font=[UIFont systemFontOfSize:17 weight:UIFontWeightSemibold];
 mainButton.layer.cornerRadius=18;
 mainButton.accessibilityLabel=@"Vị trí v12+";
 [mainButton addTarget:self action:@selector(onMain:) forControlEvents:UIControlEventTouchUpInside];
 [host addSubview:mainButton];
 NSMutableArray<UIButton*> *buttons=[NSMutableArray array];
 NSArray<NSString*> *titles=@[@"Lưu",@"Quay lại",@"Waypoint"];
 for(NSInteger i=0;i<3;i++){
  UIButton *b=[UIButton buttonWithType:UIButtonTypeSystem];
  b.tag=i+1;
  b.frame=CGRectMake(x-50,y+50+47*i,122,40);
  b.backgroundColor=[[UIColor blackColor] colorWithAlphaComponent:0.64];
  b.layer.cornerRadius=16;
  [b setTitle:titles[i] forState:UIControlStateNormal];
  [b setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
  [b addTarget:self action:@selector(onAction:) forControlEvents:UIControlEventTouchUpInside];
  b.hidden=YES;
  [host addSubview:b];[buttons addObject:b];
 }
 actions=buttons;
 std::fprintf(stderr,"[V12_PLUS] touch_overlay_attached\n");
}
- (void)onMain:(UIButton*)sender{
 (void)sender;self.expanded=!self.expanded;
 for(UIButton *b in actions)b.hidden=!self.expanded;
}
- (void)onAction:(UIButton*)sender{
 queued.store(static_cast<int>(sender.tag),std::memory_order_release);
 self.expanded=NO;
 for(UIButton *b in actions)b.hidden=YES;
}
@end

namespace {
V12PlacesControl *controller=nil;
void installUI(){
 dispatch_async(dispatch_get_main_queue(),^{
  if(!controller){
   controller=[V12PlacesControl new];
   [[NSNotificationCenter defaultCenter] addObserverForName:UIApplicationDidBecomeActiveNotification
    object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *n){(void)n;[controller attach];}];
  }
  [controller attach];
 });
}
}

__attribute__((constructor)) static void pluginInit(){
 api.h=dlopen("@rpath/ScriptHookV.dylib",RTLD_NOW|RTLD_NOLOAD);
 if(!api.h)api.h=dlopen("@loader_path/ScriptHookV.dylib",RTLD_NOW|RTLD_NOLOAD);
 if(!api.h){std::fprintf(stderr,"[V12_PLUS] ScriptHookV absent\n");return;}
 api.reg=reinterpret_cast<Reg>(dlsym(api.h,"scriptRegister"));
 api.unreg=reinterpret_cast<Unreg>(dlsym(api.h,"scriptUnregister"));
 api.wait=reinterpret_cast<Wait>(dlsym(api.h,"scriptWait"));
 api.init=reinterpret_cast<Init>(dlsym(api.h,"nativeInit"));
 api.push=reinterpret_cast<Push>(dlsym(api.h,"nativePush64"));
 api.call=reinterpret_cast<Call>(dlsym(api.h,"nativeCall"));
 if(!api.reg||!api.wait||!api.init||!api.push||!api.call){
  std::fprintf(stderr,"[V12_PLUS] ScriptHook exports missing\n");return;
 }
 Dl_info info{};
 if(!dladdr(reinterpret_cast<const void*>(&pluginInit),&info)||!info.dli_fbase){
  std::fprintf(stderr,"[V12_PLUS] module identity unavailable\n");return;
 }
 module=const_cast<void*>(info.dli_fbase);
 api.reg(module,&gameMain);
 std::fprintf(stderr,"[V12_PLUS] ScriptHook registered (device QA pending)\n");
 installUI();
}
__attribute__((destructor)) static void pluginDeinit(){
 if(module&&api.unreg)api.unreg(module);
}

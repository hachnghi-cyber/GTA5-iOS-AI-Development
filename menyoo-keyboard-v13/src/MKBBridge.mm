// GTA V iOS v13 — experimental iOS keyboard bridge for Menyoo.
// NOT device-validated. Rebind only Menyoo's nativeInit/nativePush64/nativeCall
// imports to this dylib; forward non-keyboard natives to the original ScriptHookV.
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <dispatch/dispatch.h>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <dlfcn.h>
#include <mutex>
#include <string>

namespace {
constexpr uint64_t kDisplay = 0x00DC833F2568DBF6ULL;
constexpr uint64_t kUpdate  = 0x0CF2B696BBF945AEULL;
constexpr uint64_t kResult  = 0x8362B09B91893647ULL;
constexpr uint64_t kCancel  = 0x58A39BE597CE99CDULL;
struct EditState {
  std::mutex lock;
  uint64_t generation = 0;
  int status = 3; // 0=editing, 1=accepted, 2=cancel, 3=inactive
  std::string value;
} editor;
UIAlertController *activeAlert = nil; // Access only on main queue.

using InitFn = void (*)(uint64_t);
using PushFn = void (*)(uint64_t);
using CallFn = uint64_t *(*)();
struct Original {
  void *handle;
  InitFn init;
  PushFn push;
  CallFn call;
};
const Original &original() {
  static const Original f = [] {
    void *h = dlopen("@rpath/ScriptHookV.dylib", RTLD_NOW | RTLD_NOLOAD);
    if (!h) h = dlopen("@loader_path/ScriptHookV.dylib", RTLD_NOW | RTLD_NOLOAD);
    if (!h) h = dlopen("@rpath/ScriptHookV.dylib", RTLD_NOW);
    Original o{h, nullptr, nullptr, nullptr};
    if (h) {
      o.init = reinterpret_cast<InitFn>(dlsym(h, "nativeInit"));
      o.push = reinterpret_cast<PushFn>(dlsym(h, "nativePush64"));
      o.call = reinterpret_cast<CallFn>(dlsym(h, "nativeCall"));
    }
    if (!o.init || !o.push || !o.call)
      std::fprintf(stderr, "[MKB_V13] ScriptHookV exports unresolved\n");
    return o;
  }();
  return f;
}
bool isKeyboard(uint64_t h) {
  return h == kDisplay || h == kUpdate || h == kResult || h == kCancel;
}
struct Context {
  uint64_t hash = 0;
  uint64_t args[32]{};
  uint64_t answer[8]{};
  size_t count = 0;
  bool intercepted = false;
  bool overflowed = false;
};
thread_local Context ctx;

UIViewController *topController() {
  UIApplication *app = UIApplication.sharedApplication;
  UIWindow *key = nil;
  for (UIScene *scene in app.connectedScenes) {
    if (![scene isKindOfClass:UIWindowScene.class]) continue;
    UIWindowScene *ws = static_cast<UIWindowScene *>(scene);
    if (ws.activationState != UISceneActivationStateForegroundActive) continue;
    for (UIWindow *w in ws.windows) if (w.isKeyWindow) { key = w; break; }
    if (!key) key = ws.windows.firstObject;
    if (key) break;
  }
  if (!key) key = app.keyWindow;
  UIViewController *vc = key.rootViewController;
  while (vc.presentedViewController) vc = vc.presentedViewController;
  return vc;
}
NSString *limitText(NSString *input, NSUInteger maxCharacters) {
  if (!input || !maxCharacters) return @"";
  __block NSUInteger consumed = 0, end = 0;
  [input enumerateSubstringsInRange:NSMakeRange(0, input.length)
                            options:NSStringEnumerationByComposedCharacterSequences
                         usingBlock:^(NSString *part, NSRange r, NSRange enclosing, BOOL *stop) {
    (void)part; (void)enclosing;
    if (consumed >= maxCharacters) { *stop = YES; return; }
    ++consumed;
    end = NSMaxRange(r);
  }];
  return [input substringToIndex:end];
}
void updateStatus(uint64_t g, int status, const char *value) {
  std::lock_guard<std::mutex> guard(editor.lock);
  if (editor.generation != g || editor.status != 0) return;
  editor.status = status;
  if (status == 1) editor.value = value ? value : "";
}
void showKeyboard(const char *initial, int maxCount) {
  const std::string initialCopy = initial ? initial : "";
  const NSUInteger maximum = static_cast<NSUInteger>(std::clamp(maxCount, 1, 255));
  uint64_t g;
  {
    std::lock_guard<std::mutex> guard(editor.lock);
    g = ++editor.generation;
    editor.value.clear();
    editor.status = 0;
  }
  dispatch_async(dispatch_get_main_queue(), ^{
    {
      std::lock_guard<std::mutex> guard(editor.lock);
      if (g != editor.generation) return;
    }
    if (activeAlert) {
      [activeAlert dismissViewControllerAnimated:NO completion:nil];
      activeAlert = nil;
    }
    UIViewController *vc = topController();
    if (!vc) { updateStatus(g, 2, nullptr); return; }
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Tìm kiếm Menyoo"
                                     message:@"Nhập văn bản bằng bàn phím iOS"
                              preferredStyle:UIAlertControllerStyleAlert];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *f) {
      f.text = [NSString stringWithUTF8String:initialCopy.c_str()] ?: @"";
      f.placeholder = @"Tên xe, nhân vật, hoạt ảnh...";
      f.autocorrectionType = UITextAutocorrectionTypeNo;
      f.autocapitalizationType = UITextAutocapitalizationTypeNone;
      f.returnKeyType = UIReturnKeyDone;
    }];
    __weak UIAlertController *weak = alert;
    [alert addAction:[UIAlertAction actionWithTitle:@"Hủy" style:UIAlertActionStyleCancel handler:^(UIAlertAction *a) {
      (void)a;
      updateStatus(g, 2, nullptr);
      if (activeAlert == weak) activeAlert = nil;
    }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Xong" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
      (void)a;
      NSString *value = limitText(weak.textFields.firstObject.text ?: @"", maximum);
      updateStatus(g, 1, value.UTF8String);
      if (activeAlert == weak) activeAlert = nil;
    }]];
    activeAlert = alert;
    [vc presentViewController:alert animated:YES completion:^{
      [alert.textFields.firstObject becomeFirstResponder];
    }];
  });
}
uint64_t *keyboardCall(Context &c) {
  c.answer[0] = 0;
  if (c.overflowed) {
    std::fprintf(stderr, "[MKB_V13] native argument overflow\n");
    return c.answer;
  }
  switch (c.hash) {
    case kDisplay:
      if (c.count < 8) return c.answer;
      showKeyboard(reinterpret_cast<const char *>(c.args[3]), static_cast<int>(c.args[7]));
      break;
    case kUpdate: {
      std::lock_guard<std::mutex> guard(editor.lock);
      c.answer[0] = static_cast<uint64_t>(editor.status);
      break;
    }
    case kResult: {
      static thread_local std::string result;
      std::lock_guard<std::mutex> guard(editor.lock);
      result = editor.status == 1 ? editor.value : std::string();
      c.answer[0] = editor.status == 1 ? reinterpret_cast<uint64_t>(result.c_str()) : 0;
      break;
    }
    case kCancel: {
      uint64_t g;
      {
        std::lock_guard<std::mutex> guard(editor.lock);
        g = editor.generation;
      }
      updateStatus(g, 2, nullptr);
      dispatch_async(dispatch_get_main_queue(), ^{
        if (activeAlert) {
          [activeAlert dismissViewControllerAnimated:NO completion:nil];
          activeAlert = nil;
        }
      });
      break;
    }
    default: break;
  }
  return c.answer;
}
} // namespace

extern "C" __attribute__((visibility("default"))) void nativeInit(uint64_t hash) {
  ctx.hash = hash;
  ctx.count = 0;
  ctx.overflowed = false;
  ctx.intercepted = isKeyboard(hash);
  if (!ctx.intercepted) {
    if (auto f = original().init) f(hash);
  }
}
extern "C" __attribute__((visibility("default"))) void nativePush64(uint64_t value) {
  if (ctx.intercepted) {
    if (ctx.count < 32) ctx.args[ctx.count++] = value;
    else ctx.overflowed = true;
  } else {
    if (auto f = original().push) f(value);
  }
}
extern "C" __attribute__((visibility("default"))) uint64_t *nativeCall() {
  if (ctx.intercepted) return keyboardCall(ctx);
  if (auto f = original().call) return f();
  static thread_local uint64_t nullAnswer[8]{};
  return nullAnswer; // fail closed if the original library is unavailable
}

#import <Foundation/Foundation.h>
#include "NovaVietnameseInstaller.hpp"

extern "C" bool PGInstallBundledVietnameseAccented(void) {
  @autoreleasepool {
    NSString *source = [[NSBundle mainBundle] pathForResource:@"VietnameseAccented" ofType:@"nvp"];
    if (!source) {
      NSLog(@"[VietHoa] Missing bundled VietnameseAccented.nvp");
      return false;
    }
    NSArray<NSURL *> *docs = [[NSFileManager defaultManager]
        URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask];
    if (docs.count == 0) return false;
    NSString *mods = [[docs.firstObject path] stringByAppendingPathComponent:@"Mods"];
    auto result = nova_vi::Install(source.UTF8String, mods.UTF8String);
    NSLog(@"[VietHoa] %s; entries: %zu", result.message.c_str(), result.files);
    return result.ok;
  }
}

// Constructor of the experimental dylib, before app main.
// Does not modify Online/network code.
__attribute__((constructor)) static void PGAutoInstallVietnameseOnLaunch(void) {
  (void)PGInstallBundledVietnameseAccented();
}

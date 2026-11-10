// Original iOS audio adapter. WAV files are NOT bundled in this source package.
// The user must provide legally usable files named in Superman_SFX separately.
#import <AVFoundation/AVFoundation.h>
#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>

static NSMutableDictionary<NSString*, AVAudioPlayer*>* gPlayers;

static NSString* findWav(NSString* name) {
    NSString* filename = [name stringByAppendingPathExtension:@"wav"];
    NSFileManager* manager = [NSFileManager defaultManager];
    NSMutableArray<NSString*>* folders = [NSMutableArray new];
    NSString* bundleDir = [[NSBundle mainBundle] bundlePath];
    [folders addObject:[bundleDir stringByAppendingPathComponent:@"Superman_SFX"]];
    [folders addObject:[[bundleDir stringByAppendingPathComponent:@"Frameworks"]
                        stringByAppendingPathComponent:@"Superman_SFX"]];
    NSArray<NSString*>* docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES);
    for (NSString* document in docs) {
        [folders addObject:[document stringByAppendingPathComponent:@"Superman_SFX"]];
        [folders addObject:[[document stringByAppendingPathComponent:@"mods"]
                            stringByAppendingPathComponent:@"Superman_SFX"]];
        [folders addObject:[[document stringByAppendingPathComponent:@"scripthook"]
                            stringByAppendingPathComponent:@"Superman_SFX"]];
    }
    for (NSString* folder in folders) {
        NSString* path = [folder stringByAppendingPathComponent:filename];
        if ([manager fileExistsAtPath:path]) return path;
    }
    return nil;
}

extern "C" void supermanPlaySound(const char* soundName, bool loop) {
    if (!soundName || !*soundName) return;
    NSString* name = [NSString stringWithUTF8String:soundName];
    if (!name) return;
    dispatch_async(dispatch_get_main_queue(), ^{
        if (!gPlayers) gPlayers = [NSMutableDictionary new];
        AVAudioPlayer* player = gPlayers[name];
        if (!player) {
            NSString* path = findWav(name);
            if (!path) return;
            NSError* error = nil;
            player = [[AVAudioPlayer alloc] initWithContentsOfURL:
                [NSURL fileURLWithPath:path] error:&error];
            if (!player || error) return;
            [player prepareToPlay];
            gPlayers[name] = player;
        }
        player.numberOfLoops = loop ? -1 : 0;
        player.currentTime = 0;
        [player play];
    });
}

extern "C" void supermanStopSound(const char* soundName) {
    if (!soundName || !*soundName) return;
    NSString* name = [NSString stringWithUTF8String:soundName];
    if (!name) return;
    dispatch_async(dispatch_get_main_queue(), ^{ [gPlayers[name] stop]; });
}

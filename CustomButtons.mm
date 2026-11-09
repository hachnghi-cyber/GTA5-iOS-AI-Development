// GTA V iOS v11.2 - extra on-screen Custom buttons (experimental).
// This dylib is an additive overlay: it does not change TCOverlay or TCButton.
// Build for arm64 iOS using the matching iOS SDK. Requires a freshly signed IPA.

#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import <mach-o/loader.h>
#import <dispatch/dispatch.h>
#include <stdint.h>
#include <string.h>

static NSString *const kCBDefaultsKey = @"GTAVExtraCustomButtons_v1";
static NSString *const kCBPlusPositionKey = @"GTAVExtraCustomPlusPosition_v1";
static NSString *const kCBIdentifier = @"id";
static NSString *const kCBTitle = @"title";
static NSString *const kCBKeys = @"keys";
static NSString *const kCBX = @"x";
static NSString *const kCBY = @"y";
static NSString *const kCBSize = @"size";
static NSString *const kCBAlpha = @"alpha";
static NSString *const kCBContext = @"context";

typedef void (*CBNativeSendKey)(unsigned char key, bool down);
static CBNativeSendKey gSendKey = NULL;

// v11.2(2) exact-match safety guard. ASLR is handled by _dyld_get_image_header.
// If the loaded compat binary differs, do NOT guess a private function offset.
static BOOL CBResolveSendKey(void) {
    if (gSendKey) return YES;
    static const uint8_t expectedUUID[16] = {
        0xbd, 0xe1, 0x32, 0x71, 0xa3, 0x50, 0x38, 0x63,
        0xb9, 0x71, 0x0e, 0x84, 0x61, 0xd4, 0xea, 0x3e
    };
    static const uint8_t expectedPrologue[16] = {
        0xff, 0x43, 0x02, 0xd1, 0xf4, 0x4f, 0x07, 0xa9,
        0xfd, 0x7b, 0x08, 0xa9, 0xfd, 0x03, 0x02, 0x91
    };
    for (uint32_t index = 0; index < _dyld_image_count(); index++) {
        const char *name = _dyld_get_image_name(index);
        if (!name || !strstr(name, "/libgtacompat.dylib")) continue;
        const struct mach_header *header = _dyld_get_image_header(index);
        if (!header || header->magic != MH_MAGIC_64) return NO;
        const struct mach_header_64 *mh = (const struct mach_header_64 *)header;
        const uint8_t *commands = (const uint8_t *)mh + sizeof(*mh);
        const uint8_t *cursor = commands;
        BOOL uuidMatches = NO;
        for (uint32_t commandIndex = 0; commandIndex < mh->ncmds; commandIndex++) {
            const struct load_command *lc = (const struct load_command *)cursor;
            if (lc->cmdsize < sizeof(*lc) ||
                cursor + lc->cmdsize > commands + mh->sizeofcmds) return NO;
            if (lc->cmd == LC_UUID && lc->cmdsize >= sizeof(struct uuid_command)) {
                const struct uuid_command *uuidCommand = (const struct uuid_command *)lc;
                uuidMatches = memcmp(uuidCommand->uuid, expectedUUID, 16) == 0;
            }
            cursor += lc->cmdsize;
        }
        if (!uuidMatches) return NO;
        const uint8_t *entry = (const uint8_t *)header + 0x14ea90;
        if (memcmp(entry, expectedPrologue, sizeof(expectedPrologue)) != 0) return NO;
        gSendKey = (CBNativeSendKey)entry;
        return YES;
    }
    return NO;
}

static NSDictionary<NSString *, NSNumber *> *CBKeyDictionary(void) {
    static NSDictionary<NSString *, NSNumber *> *mapping = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        // macOS virtual key codes used by this port's native SendKey bridge.
        mapping = @{
            @"A": @0, @"S": @1, @"D": @2, @"F": @3, @"H": @4,
            @"G": @5, @"Z": @6, @"X": @7, @"C": @8, @"V": @9,
            @"B": @11, @"Q": @12, @"W": @13, @"E": @14, @"R": @15,
            @"Y": @16, @"T": @17, @"1": @18, @"2": @19,
            @"3": @20, @"4": @21, @"6": @22, @"5": @23,
            @"9": @25, @"7": @26, @"8": @28, @"0": @29,
            @"O": @31, @"U": @32, @"I": @34, @"P": @35,
            @"L": @37, @"J": @38, @"K": @40, @"N": @45, @"M": @46,
            @"TAB": @48, @"SPACE": @49, @"ENTER": @36, @"ESC": @53,
            @"SHIFT": @56, @"CTRL": @59, @"CONTROL": @59, @"ALT": @58,
            @"F1": @122, @"F2": @120, @"F3": @99, @"F4": @118,
            @"F5": @96, @"F6": @97, @"F7": @98, @"F8": @100,
            @"F9": @101, @"F10": @109, @"F11": @103, @"F12": @111,
            @"UP": @126, @"DOWN": @125, @"LEFT": @123, @"RIGHT": @124
        };
    });
    return mapping;
}

static NSArray<NSNumber *> *CBParseKeys(NSString *expression) {
    if (![expression isKindOfClass:[NSString class]]) return @[];
    NSArray<NSString *> *tokens = [[expression uppercaseString] componentsSeparatedByString:@"+"];
    if (tokens.count < 1 || tokens.count > 4) return @[];
    NSMutableArray<NSNumber *> *result = [NSMutableArray array];
    for (NSString *token in tokens) {
        NSString *trimmed = [token stringByTrimmingCharactersInSet:
                             [NSCharacterSet whitespaceAndNewlineCharacterSet]];
        NSNumber *code = CBKeyDictionary()[trimmed];
        if (!code || [result containsObject:code]) return @[];
        [result addObject:code];
    }
    return result;
}

@interface CBPassthroughView : UIView
@end

@implementation CBPassthroughView
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    if (self.hidden || self.alpha < 0.02 || !self.userInteractionEnabled) return nil;
    for (UIView *view in [self.subviews reverseObjectEnumerator]) {
        if (view.hidden || view.alpha < 0.02 || !view.userInteractionEnabled) continue;
        CGPoint converted = [self convertPoint:point toView:view];
        if ([view pointInside:converted withEvent:event]) {
            UIView *hit = [view hitTest:converted withEvent:event];
            if (hit) return hit;
        }
    }
    // Outside our actual custom buttons: let game's own touch overlay handle it.
    return nil;
}
@end

@class CBManager;
@interface CBButton : UIButton
@property(nonatomic, copy) NSString *buttonID;
@property(nonatomic, copy) NSArray<NSNumber *> *keyCodes;
@property(nonatomic, assign) BOOL keyHeld;
@end
@implementation CBButton
@end

@interface CBManager : NSObject
@property(nonatomic, strong) CBPassthroughView *overlay;
@property(nonatomic, strong) UIButton *plus;
@property(nonatomic, strong) NSMutableArray<NSMutableDictionary *> *models;
@property(nonatomic, strong) NSMutableDictionary<NSString *, CBButton *> *views;
@property(nonatomic, assign) BOOL editing;
@property(nonatomic, assign) NSInteger gameContext;
@property(nonatomic, weak) UIWindow *attachedWindow;
- (void)start;
@end

@implementation CBManager

- (instancetype)init {
    if ((self = [super init])) {
        _models = [NSMutableArray array];
        _views = [NSMutableDictionary dictionary];
        NSArray *saved = [[NSUserDefaults standardUserDefaults] arrayForKey:kCBDefaultsKey];
        for (id object in saved) {
            if (![object isKindOfClass:[NSDictionary class]]) continue;
            NSDictionary *value = (NSDictionary *)object;
            if (![value[kCBIdentifier] isKindOfClass:[NSString class]] ||
                ![value[kCBTitle] isKindOfClass:[NSString class]] ||
                ![value[kCBKeys] isKindOfClass:[NSString class]] ||
                CBParseKeys(value[kCBKeys]).count == 0) continue;
            [_models addObject:[value mutableCopy]];
        }
    }
    return self;
}

- (void)start {
    [NSTimer scheduledTimerWithTimeInterval:1.0 target:self
                                   selector:@selector(tick:) userInfo:nil repeats:YES];
    [self tick:nil];
}

- (void)save {
    [[NSUserDefaults standardUserDefaults] setObject:[self.models copy]
                                              forKey:kCBDefaultsKey];
}

- (UIView *)findNativeTouchOverlay:(UIView *)candidate {
    Class cls = NSClassFromString(@"TCOverlay");
    if (cls && [candidate isKindOfClass:cls]) return candidate;
    for (UIView *subview in candidate.subviews) {
        UIView *match = [self findNativeTouchOverlay:subview];
        if (match) return match;
    }
    return nil;
}

- (NSInteger)contextForNativeOverlay:(UIView *)view {
    Ivar ivar = class_getInstanceVariable([view class], "_context");
    if (!ivar || strcmp(ivar_getTypeEncoding(ivar), "i") != 0) return 0;
    const uintptr_t address = (uintptr_t)(__bridge void *)view + ivar_getOffset(ivar);
    return (NSInteger)(*(const int *)address);
}

- (void)tick:(NSTimer *)timer {
    // Main thread only. Never touch the game's private UIKit objects off-thread.
    NSArray<UIScene *> *scenes = [[UIApplication sharedApplication].connectedScenes allObjects];
    NSMutableArray<UIWindow *> *windows = [NSMutableArray array];
    for (UIScene *scene in scenes) {
        if (![scene isKindOfClass:[UIWindowScene class]]) continue;
        [windows addObjectsFromArray:((UIWindowScene *)scene).windows];
    }
    if (windows.count == 0) [windows addObjectsFromArray:UIApplication.sharedApplication.windows];

    UIWindow *window = nil;
    UIView *native = nil;
    for (UIWindow *candidate in windows) {
        if (candidate.hidden || candidate.bounds.size.width <= 0) continue;
        native = [self findNativeTouchOverlay:candidate];
        if (native) { window = candidate; break; }
    }
    NSInteger context = native ? [self contextForNativeOverlay:native] : 0;
    BOOL show = window && (context == 1 || context == 2) && CBResolveSendKey();
    if (!show) {
        [self releaseAllKeys];
        self.overlay.hidden = YES;
        return;
    }
    if (self.attachedWindow != window) {
        [self.overlay removeFromSuperview];
        self.attachedWindow = window;
        self.overlay = nil;
        self.plus = nil;
        [self.views removeAllObjects];
    }
    if (!self.overlay) [self buildOverlayIn:window];
    if (self.gameContext != context) {
        [self releaseAllKeys];
        self.gameContext = context;
        [self syncButtons];
    }
    self.overlay.hidden = NO;
    self.overlay.frame = window.bounds;
    [window bringSubviewToFront:self.overlay];
    [self updateFrames];
}

- (void)buildOverlayIn:(UIWindow *)window {
    CBPassthroughView *overlay = [[CBPassthroughView alloc] initWithFrame:window.bounds];
    overlay.backgroundColor = [UIColor clearColor];
    overlay.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    overlay.accessibilityIdentifier = @"gtav.custom.overlay";
    [window addSubview:overlay];
    self.overlay = overlay;

    UIButton *plus = [UIButton buttonWithType:UIButtonTypeSystem];
    [plus setTitle:@"＋" forState:UIControlStateNormal];
    plus.titleLabel.font = [UIFont boldSystemFontOfSize:23];
    plus.backgroundColor = [[UIColor blackColor] colorWithAlphaComponent:0.7];
    [plus setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    plus.layer.cornerRadius = 20;
    plus.layer.borderWidth = 1;
    plus.layer.borderColor = UIColor.whiteColor.CGColor;
    plus.accessibilityLabel = @"Thêm nút Custom";
    [plus addTarget:self action:@selector(showMainMenu:) forControlEvents:UIControlEventTouchUpInside];
    UIPanGestureRecognizer *plusPan = [[UIPanGestureRecognizer alloc]
                                      initWithTarget:self action:@selector(dragPlus:)];
    [plus addGestureRecognizer:plusPan];
    [overlay addSubview:plus];
    self.plus = plus;
    [self syncButtons];
}

- (NSMutableDictionary *)modelForID:(NSString *)identifier {
    for (NSMutableDictionary *model in self.models) {
        if ([model[kCBIdentifier] isEqual:identifier]) return model;
    }
    return nil;
}

- (void)syncButtons {
    for (CBButton *button in self.views.allValues) {
        [self sendKeysForButton:button down:NO];
        [button removeFromSuperview];
    }
    [self.views removeAllObjects];
    if (!self.overlay) return;
    for (NSMutableDictionary *model in self.models) {
        NSInteger context = [model[kCBContext] integerValue];
        if (context != 0 && context != self.gameContext) continue;
        NSArray<NSNumber *> *codes = CBParseKeys(model[kCBKeys]);
        if (codes.count == 0) continue;
        CBButton *button = [CBButton buttonWithType:UIButtonTypeCustom];
        button.buttonID = model[kCBIdentifier];
        button.keyCodes = codes;
        button.keyHeld = NO;
        button.accessibilityIdentifier = button.buttonID;
        [button setTitle:model[kCBTitle] forState:UIControlStateNormal];
        [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
        button.titleLabel.font = [UIFont boldSystemFontOfSize:14];
        button.titleLabel.adjustsFontSizeToFitWidth = YES;
        button.backgroundColor = [[UIColor darkGrayColor] colorWithAlphaComponent:0.85];
        button.layer.borderWidth = 1;
        button.layer.borderColor = UIColor.whiteColor.CGColor;
        [button addTarget:self action:@selector(buttonDown:) forControlEvents:UIControlEventTouchDown];
        [button addTarget:self action:@selector(buttonUp:)
         forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside |
                          UIControlEventTouchCancel | UIControlEventTouchDragExit];
        UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
                                     initWithTarget:self action:@selector(dragButton:)];
        pan.minimumNumberOfTouches = 1;
        [button addGestureRecognizer:pan];
        [self.overlay addSubview:button];
        self.views[button.buttonID] = button;
    }
    [self.overlay bringSubviewToFront:self.plus];
    [self updateFrames];
}

- (void)updateFrames {
    if (!self.overlay) return;
    CGSize bounds = self.overlay.bounds.size;
    if (bounds.width < 1 || bounds.height < 1) return;
    NSDictionary *plusPosition = [[NSUserDefaults standardUserDefaults]
                                  dictionaryForKey:kCBPlusPositionKey];
    CGFloat plusX = plusPosition ? [plusPosition[kCBX] doubleValue] : 0.94;
    CGFloat plusY = plusPosition ? [plusPosition[kCBY] doubleValue] : 0.10;
    CGFloat centerX = MAX(24, MIN(bounds.width - 24, bounds.width * plusX));
    CGFloat centerY = MAX(24, MIN(bounds.height - 24, bounds.height * plusY));
    self.plus.frame = CGRectMake(centerX - 20, centerY - 20, 40, 40);
    for (NSString *identifier in self.views) {
        CBButton *button = self.views[identifier];
        NSDictionary *model = [self modelForID:identifier];
        for (UIGestureRecognizer *gesture in button.gestureRecognizers) {
            if ([gesture isKindOfClass:[UIPanGestureRecognizer class]])
                gesture.enabled = self.editing;
        }
        CGFloat size = MAX(32, MIN(100, [model[kCBSize] doubleValue]));
        if (size < 34) size = 54;
        CGFloat x = MAX(size / 2, MIN(bounds.width - size / 2,
                                      bounds.width * [model[kCBX] doubleValue]));
        CGFloat y = MAX(size / 2, MIN(bounds.height - size / 2,
                                      bounds.height * [model[kCBY] doubleValue]));
        button.frame = CGRectMake(x - size / 2, y - size / 2, size, size);
        button.layer.cornerRadius = size / 2;
        CGFloat alpha = [model[kCBAlpha] doubleValue];
        button.alpha = MAX(0.2, MIN(1, alpha <= 0 ? 0.75 : alpha));
        button.layer.borderColor = (self.editing ? UIColor.systemYellowColor :
                                    UIColor.whiteColor).CGColor;
    }
    for (UIGestureRecognizer *gesture in self.plus.gestureRecognizers) {
        if ([gesture isKindOfClass:[UIPanGestureRecognizer class]])
            gesture.enabled = self.editing;
    }
}

- (void)sendKeysForButton:(CBButton *)button down:(BOOL)down {
    if (!button || button.keyHeld == down) return;
    if (!CBResolveSendKey()) return;
    button.keyHeld = down;
    NSArray<NSNumber *> *sequence = down ? button.keyCodes :
        [[button.keyCodes reverseObjectEnumerator] allObjects];
    for (NSNumber *code in sequence) gSendKey((unsigned char)code.unsignedCharValue, down);
}

- (void)releaseAllKeys {
    for (CBButton *button in self.views.allValues) [self sendKeysForButton:button down:NO];
}

- (void)buttonDown:(CBButton *)button {
    if (self.editing) return;
    [self sendKeysForButton:button down:YES];
}
- (void)buttonUp:(CBButton *)button {
    [self sendKeysForButton:button down:NO];
    if (self.editing) [self editButton:button];
}

- (void)dragPlus:(UIPanGestureRecognizer *)gesture {
    if (!self.editing) return;
    CGPoint delta = [gesture translationInView:self.overlay];
    CGSize bounds = self.overlay.bounds.size;
    if (bounds.width < 1 || bounds.height < 1) return;
    NSUserDefaults *prefs = [NSUserDefaults standardUserDefaults];
    NSDictionary *saved = [prefs dictionaryForKey:kCBPlusPositionKey];
    CGFloat x = saved ? [saved[kCBX] doubleValue] : 0.94;
    CGFloat y = saved ? [saved[kCBY] doubleValue] : 0.10;
    x = MAX(0.03, MIN(0.97, x + delta.x / bounds.width));
    y = MAX(0.03, MIN(0.97, y + delta.y / bounds.height));
    [prefs setObject:@{kCBX: @(x), kCBY: @(y)} forKey:kCBPlusPositionKey];
    [gesture setTranslation:CGPointZero inView:self.overlay];
    [self updateFrames];
}

- (void)dragButton:(UIPanGestureRecognizer *)gesture {
    if (!self.editing) return;
    CBButton *button = (CBButton *)gesture.view;
    NSMutableDictionary *model = [self modelForID:button.buttonID];
    if (!model) return;
    CGPoint change = [gesture translationInView:self.overlay];
    CGFloat width = MAX(self.overlay.bounds.size.width, 1);
    CGFloat height = MAX(self.overlay.bounds.size.height, 1);
    model[kCBX] = @(MAX(0, MIN(1, [model[kCBX] doubleValue] + change.x / width)));
    model[kCBY] = @(MAX(0, MIN(1, [model[kCBY] doubleValue] + change.y / height)));
    [gesture setTranslation:CGPointZero inView:self.overlay];
    [self updateFrames];
    if (gesture.state == UIGestureRecognizerStateEnded) [self save];
}

- (UIViewController *)topViewController {
    UIViewController *current = self.attachedWindow.rootViewController;
    for (unsigned n = 0; n < 12 && current; n++) {
        UIViewController *next = current.presentedViewController;
        if (!next && [current isKindOfClass:[UINavigationController class]])
            next = ((UINavigationController *)current).visibleViewController;
        if (!next && [current isKindOfClass:[UITabBarController class]])
            next = ((UITabBarController *)current).selectedViewController;
        if (!next || next == current) break;
        current = next;
    }
    return current;
}

- (void)present:(UIAlertController *)alert from:(UIView *)source {
    UIViewController *vc = [self topViewController];
    if (!vc || [vc isKindOfClass:[UIAlertController class]]) return;
    UIPopoverPresentationController *pop = alert.popoverPresentationController;
    if (pop) { pop.sourceView = source ?: self.plus; pop.sourceRect = (source ?: self.plus).bounds; }
    [vc presentViewController:alert animated:YES completion:nil];
}

- (void)showMainMenu:(UIButton *)sender {
    [self releaseAllKeys];
    UIAlertController *menu = [UIAlertController alertControllerWithTitle:@"Nút Custom"
                         message:@"Tạo nhiều nút. Bật chế độ chỉnh, chạm nút để đổi phím hoặc kéo để di chuyển."
                  preferredStyle:UIAlertControllerStyleActionSheet];
    [menu addAction:[UIAlertAction actionWithTitle:@"＋ Thêm nút mới"
          style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) { [self addButton]; }]];
    NSString *editTitle = self.editing ? @"✓ Hoàn tất chỉnh vị trí" : @"✥ Kéo để chỉnh vị trí";
    [menu addAction:[UIAlertAction actionWithTitle:editTitle
          style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
        self.editing = !self.editing;
        if (!self.editing) [self save];
        [self updateFrames];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Đặt lại vị trí nút ＋"
          style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
        [[NSUserDefaults standardUserDefaults] removeObjectForKey:kCBPlusPositionKey];
        [self updateFrames];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Đóng" style:UIAlertActionStyleCancel handler:nil]];
    [self present:menu from:sender];
}

- (void)addButton {
    UIAlertController *prompt = [UIAlertController alertControllerWithTitle:@"Thêm nút Custom"
        message:@"Ví dụ: tên 'Menyoo', phím 'F8' hoặc 'SHIFT+E'."
        preferredStyle:UIAlertControllerStyleAlert];
    [prompt addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"Tên nút (ví dụ Menyoo)";
        field.text = @"Custom";
        field.autocapitalizationType = UITextAutocapitalizationTypeSentences;
    }];
    [prompt addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"Phím (ví dụ F8 hoặc SHIFT+E)";
        field.text = @"F8";
        field.autocapitalizationType = UITextAutocapitalizationTypeAllCharacters;
    }];
    [prompt addAction:[UIAlertAction actionWithTitle:@"Hủy" style:UIAlertActionStyleCancel handler:nil]];
    [prompt addAction:[UIAlertAction actionWithTitle:@"Tiếp tục" style:UIAlertActionStyleDefault
       handler:^(__unused UIAlertAction *action) {
        NSString *name = prompt.textFields.firstObject.text ?: @"Custom";
        NSString *keys = prompt.textFields.lastObject.text ?: @"F8";
        if (CBParseKeys(keys).count == 0) { [self showInvalidKeys]; return; }
        [self chooseContextForName:name keys:keys];
    }]];
    [self present:prompt from:self.plus];
}

- (void)showInvalidKeys {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Phím không hợp lệ"
        message:@"Dùng F7/F8/F9/F10, E, SPACE, hoặc SHIFT+E, CTRL+F8, v.v."
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleCancel handler:nil]];
    [self present:alert from:self.plus];
}

- (void)chooseContextForName:(NSString *)name keys:(NSString *)keys {
    UIAlertController *menu = [UIAlertController alertControllerWithTitle:@"Hiển thị ở đâu?"
        message:@"Nút sẽ không che màn hình bản đồ/Pause nếu game đổi ngữ cảnh cảm ứng."
        preferredStyle:UIAlertControllerStyleActionSheet];
    NSArray<NSString *> *titles = @[@"Cả đi bộ và lái xe", @"Chỉ khi đi bộ", @"Chỉ khi lái xe"];
    for (NSInteger index = 0; index < 3; index++) {
        [menu addAction:[UIAlertAction actionWithTitle:titles[index]
              style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
            NSInteger context = index == 0 ? 0 : index;
            NSMutableDictionary *model = [@{
                kCBIdentifier: NSUUID.UUID.UUIDString,
                kCBTitle: name.length ? [name substringToIndex:MIN(name.length, 18)] : @"Custom",
                kCBKeys: [keys uppercaseString],
                kCBContext: @(context),
                kCBX: @0.54, kCBY: @0.20,
                kCBSize: @54, kCBAlpha: @0.78
            } mutableCopy];
            [self.models addObject:model];
            [self save];
            [self syncButtons];
            self.editing = YES;
            [self updateFrames];
        }]];
    }
    [menu addAction:[UIAlertAction actionWithTitle:@"Hủy" style:UIAlertActionStyleCancel handler:nil]];
    [self present:menu from:self.plus];
}

- (void)editButton:(CBButton *)button {
    NSMutableDictionary *model = [self modelForID:button.buttonID];
    if (!model) return;
    [self releaseAllKeys];
    UIAlertController *menu = [UIAlertController alertControllerWithTitle:model[kCBTitle]
        message:[NSString stringWithFormat:@"Gán phím: %@", model[kCBKeys]]
        preferredStyle:UIAlertControllerStyleActionSheet];
    [menu addAction:[UIAlertAction actionWithTitle:@"Đổi tên / phím"
         style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        [self renameButton:button];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Tăng kích thước"
         style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        model[kCBSize] = @(MIN(100, [model[kCBSize] doubleValue] + 8));
        [self save]; [self updateFrames];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Giảm kích thước"
         style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        model[kCBSize] = @(MAX(32, [model[kCBSize] doubleValue] - 8));
        [self save]; [self updateFrames];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Đổi độ mờ"
         style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        CGFloat a = [model[kCBAlpha] doubleValue];
        model[kCBAlpha] = @(a >= 0.9 ? 0.3 : a + 0.2);
        [self save]; [self updateFrames];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Xóa nút"
         style:UIAlertActionStyleDestructive handler:^(__unused UIAlertAction *action) {
        [self sendKeysForButton:button down:NO];
        [self.models removeObject:model];
        [self save]; [self syncButtons];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Hủy" style:UIAlertActionStyleCancel handler:nil]];
    [self present:menu from:button];
}

- (void)renameButton:(CBButton *)button {
    NSMutableDictionary *model = [self modelForID:button.buttonID];
    if (!model) return;
    UIAlertController *prompt = [UIAlertController alertControllerWithTitle:@"Đổi nút Custom"
        message:@"Các phím nối bằng dấu +, ví dụ SHIFT+E."
        preferredStyle:UIAlertControllerStyleAlert];
    [prompt addTextFieldWithConfigurationHandler:^(UITextField *field) { field.text = model[kCBTitle]; }];
    [prompt addTextFieldWithConfigurationHandler:^(UITextField *field) { field.text = model[kCBKeys]; }];
    [prompt addAction:[UIAlertAction actionWithTitle:@"Hủy" style:UIAlertActionStyleCancel handler:nil]];
    [prompt addAction:[UIAlertAction actionWithTitle:@"Lưu" style:UIAlertActionStyleDefault
       handler:^(__unused UIAlertAction *action) {
        NSString *title = prompt.textFields.firstObject.text ?: @"Custom";
        NSString *keys = prompt.textFields.lastObject.text ?: @"";
        if (CBParseKeys(keys).count == 0) { [self showInvalidKeys]; return; }
        model[kCBTitle] = title.length ? [title substringToIndex:MIN(title.length, 18)] : @"Custom";
        model[kCBKeys] = [keys uppercaseString];
        [self save]; [self syncButtons];
    }]];
    [self present:prompt from:button];
}

@end

static CBManager *gCBManager;
__attribute__((constructor)) static void CBInstall(void) {
    dispatch_async(dispatch_get_main_queue(), ^{
        gCBManager = [CBManager new];
        [gCBManager start];
    });
}

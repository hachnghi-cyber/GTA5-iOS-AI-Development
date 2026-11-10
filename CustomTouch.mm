// GTA V iOS v11.3 — experimental, opt-in touch overlay.
// This does not alter libgtacompat's existing TCOverlay or its touch layout.
// Input is routed through Apple's GCVirtualController API. Compatibility with
// the game's controller selection MUST be verified on an actual device.

#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <GameController/GameController.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import <mach-o/loader.h>
#include <stdint.h>
#include <string.h>

static NSString * const kStorageKey = @"hachnghi.customtouch.v113.buttons";
static NSString * const kEnabledKey = @"hachnghi.customtouch.v113.enabled";

// This is a v11.3-specific private input bridge, NOT a public iOS keyboard
// injection API. Verified by static Mach-O symbol-table inspection of the
// user-supplied libgtacompat.dylib. A different build must fail closed.
// C++ local symbol: __ZL7SendKeyhb = SendKey(unsigned char, bool).
typedef void (*HCCSendKeyFunction)(unsigned char, bool);
static HCCSendKeyFunction gHCCSendKey;
static const uintptr_t kHCCSendKeyVMAddr = 0x152e3c;
static const uint8_t kHCCCompatUUID[16] = {
    0x07, 0xe7, 0x11, 0x8e, 0xc3, 0xa1, 0x38, 0x0e,
    0x91, 0x92, 0x58, 0xbc, 0xf3, 0xd3, 0x0d, 0xd7
};
static const uint32_t kHCCSendKeyStart[4] = {
    0xd10243ff, 0xa9074ff4, 0xa9087bfd, 0x910203fd
};

static HCCSendKeyFunction HCCResolveSendKey(void) {
    if (gHCCSendKey) return gHCCSendKey;
    const uint32_t count = _dyld_image_count();
    for (uint32_t i = 0; i < count; ++i) {
        const char *name = _dyld_get_image_name(i);
        if (!name) continue;
        const char *tail = "/libgtacompat.dylib";
        size_t size = strlen(name), tailSize = strlen(tail);
        if (size < tailSize || strcmp(name + size - tailSize, tail) != 0) continue;
        const struct mach_header *header = _dyld_get_image_header(i);
        if (!header || header->magic != MH_MAGIC_64 || header->cputype != CPU_TYPE_ARM64) continue;
        const struct mach_header_64 *h64 = (const struct mach_header_64 *)header;
        BOOL uuidMatches = NO;
        const uint8_t *commandPointer = (const uint8_t *)h64 + sizeof(*h64);
        size_t remaining = h64->sizeofcmds;
        for (uint32_t n = 0; n < h64->ncmds; ++n) {
            if (remaining < sizeof(struct load_command)) break;
            const struct load_command *cmd = (const struct load_command *)commandPointer;
            if (cmd->cmdsize < sizeof(*cmd) || cmd->cmdsize > remaining) break;
            if (cmd->cmd == LC_UUID && cmd->cmdsize >= sizeof(struct uuid_command)) {
                const struct uuid_command *uuid = (const struct uuid_command *)cmd;
                uuidMatches = (memcmp(uuid->uuid, kHCCCompatUUID, 16) == 0);
                break;
            }
            commandPointer += cmd->cmdsize;
            remaining -= cmd->cmdsize;
        }
        if (!uuidMatches) return NULL;
        const uint8_t *target = (const uint8_t *)(_dyld_get_image_vmaddr_slide(i) + kHCCSendKeyVMAddr);
        if (memcmp(target, kHCCSendKeyStart, sizeof(kHCCSendKeyStart)) != 0) return NULL;
        gHCCSendKey = (HCCSendKeyFunction)(uintptr_t)target;
        return gHCCSendKey;
    }
    return NULL;
}

// USB HID usages, matching the GCKeyboard codes that libgtacompat passes to
// SendKey. These are NOT Windows virtual key codes.
static uint8_t HCCKeyUsage(NSString *name) {
    if (name.length == 1) {
        unichar c = [name characterAtIndex:0];
        if (c >= 'A' && c <= 'Z') return (uint8_t)(4 + c - 'A');
        if (c >= '1' && c <= '9') return (uint8_t)(0x1e + c - '1');
        if (c == '0') return 0x27;
    }
    if ([name hasPrefix:@"F"] && name.length <= 3) {
        NSString *digits = [name substringFromIndex:1];
        NSCharacterSet *notNumbers = [[NSCharacterSet decimalDigitCharacterSet] invertedSet];
        if ([digits rangeOfCharacterFromSet:notNumbers].location != NSNotFound) return 0;
        NSInteger number = [digits integerValue];
        if (number >= 1 && number <= 12) return (uint8_t)(0x3a + number - 1);
    }
    NSDictionary<NSString *,NSNumber *> *special = @{
        @"SPACE":@0x2c, @"ENTER":@0x28, @"ESC":@0x29, @"BACKSPACE":@0x2a,
        @"TAB":@0x2b, @"CAPSLOCK":@0x39, @"DELETE":@0x4c, @"INSERT":@0x49,
        @"HOME":@0x4a, @"END":@0x4d, @"PAGEUP":@0x4b, @"PAGEDOWN":@0x4e,
        @"LEFT":@0x50, @"RIGHT":@0x4f, @"UP":@0x52, @"DOWN":@0x51,
        @"NUM0":@0x62, @"NUM1":@0x59, @"NUM2":@0x5a, @"NUM3":@0x5b,
        @"NUM4":@0x5c, @"NUM5":@0x5d, @"NUM6":@0x5e, @"NUM7":@0x5f,
        @"NUM8":@0x60, @"NUM9":@0x61, @"NUMENTER":@0x58, @"NUMPLUS":@0x57,
        @"NUMMINUS":@0x56, @"NUMMULTIPLY":@0x55, @"NUMDIVIDE":@0x54,
        @"NUMDOT":@0x63, @"CTRL":@0xe0, @"SHIFT":@0xe1, @"ALT":@0xe2
    };
    if (special[name]) return special[name].unsignedCharValue;
    return 0;
}

static NSArray<NSNumber *> *HCCKeySequence(NSString *mapping) {
    if (![mapping hasPrefix:@"KEY_"]) return @[];
    NSString *expression = [mapping substringFromIndex:4];
    NSArray<NSString *> *tokens = [expression componentsSeparatedByString:@"+"];
    if (!tokens.count || tokens.count > 4) return @[];
    NSMutableArray<NSNumber *> *usages = [NSMutableArray array];
    NSMutableSet<NSNumber *> *uniques = [NSMutableSet set];
    for (NSUInteger i = 0; i < tokens.count; ++i) {
        NSString *name = [tokens[i] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
        uint8_t usage = HCCKeyUsage(name);
        BOOL modifier = (usage >= 0xe0 && usage <= 0xe7);
        if (!usage || [uniques containsObject:@(usage)]) return @[];
        if (i + 1 < tokens.count && !modifier) return @[];
        [uniques addObject:@(usage)];
        [usages addObject:@(usage)];
    }
    return usages;
}

static BOOL HCCSendKeyboardUsage(uint8_t usage, BOOL down) {
    HCCSendKeyFunction sender = HCCResolveSendKey();
    if (!sender) {
        static BOOL warned = NO;
        if (!warned) {
            NSLog(@"[CustomTouch] keyboard bridge unavailable; no keyboard event sent");
            warned = YES;
        }
        return NO;
    }
    sender(usage, down);
    return YES;
}

@interface HCCPassThroughView : UIView
@end

@implementation HCCPassThroughView
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit = [super hitTest:point withEvent:event];
    return hit == self ? nil : hit;
}
@end

@interface HCCOverlay : NSObject <UIGestureRecognizerDelegate>
@property(nonatomic, strong) HCCPassThroughView *view;
@property(nonatomic, strong) UIButton *toggle;
@property(nonatomic, strong) UIButton *editor;
@property(nonatomic, strong) UIButton *adder;
@property(nonatomic, strong) NSMutableArray<UIButton *> *buttons;
@property(nonatomic, strong) NSMutableArray<NSMutableDictionary *> *settings;
@property(nonatomic, strong) NSMutableSet<NSNumber *> *pressed;
@property(nonatomic, strong) NSMutableSet<NSNumber *> *keyboardHeld;
@property(nonatomic, strong) GCVirtualController *virtualPad;
@property(nonatomic, assign) BOOL connected;
@property(nonatomic, assign) BOOL editing;
@property(nonatomic, assign) BOOL enabled;
@end

@implementation HCCOverlay

- (instancetype)init {
    self = [super init];
    if (!self) return nil;
    _buttons = [NSMutableArray array];
    _pressed = [NSMutableSet set];
    _keyboardHeld = [NSMutableSet set];
    _settings = [NSMutableArray array];
    NSArray *saved = [NSUserDefaults.standardUserDefaults arrayForKey:kStorageKey];
    NSArray *defaults = @[
        @{ @"label":@"J", @"key":@"KEY_J", @"x":@0.72, @"y":@0.37, @"size":@48, @"opacity":@0.60 },
        @{ @"label":@"K", @"key":@"KEY_K", @"x":@0.85, @"y":@0.37, @"size":@48, @"opacity":@0.60 },
        @{ @"label":@"L", @"key":@"KEY_L", @"x":@0.72, @"y":@0.55, @"size":@48, @"opacity":@0.60 },
        @{ @"label":@"M", @"key":@"KEY_M", @"x":@0.85, @"y":@0.55, @"size":@48, @"opacity":@0.60 }
    ];
    NSArray *source = ([saved isKindOfClass:NSArray.class] && saved.count <= 24) ? saved : defaults;
    NSMutableSet<NSString *> *validMappings = [NSMutableSet setWithArray:@[@"A",@"B",@"X",@"Y",@"LB",@"RB",@"LT",@"RT",@"UP",@"DOWN",@"LEFT",@"RIGHT",@"MENYOO"]];
    for (NSUInteger i = 0; i < source.count; ++i) {
        NSDictionary *fallback = defaults[MIN(i, defaults.count - 1)];
        NSDictionary *entry = [source[i] isKindOfClass:NSDictionary.class] ? source[i] : fallback;
        NSString *mapping = [entry[@"key"] isKindOfClass:NSString.class] ? entry[@"key"] : fallback[@"key"];
        if (![validMappings containsObject:mapping] && HCCKeySequence(mapping).count == 0) mapping = fallback[@"key"];
        NSString *label = [entry[@"label"] isKindOfClass:NSString.class] ? entry[@"label"] : fallback[@"label"];
        if (label.length > 8) label = [label substringToIndex:8];
        double x = [entry[@"x"] respondsToSelector:@selector(doubleValue)] ? [entry[@"x"] doubleValue] : [fallback[@"x"] doubleValue];
        double y = [entry[@"y"] respondsToSelector:@selector(doubleValue)] ? [entry[@"y"] doubleValue] : [fallback[@"y"] doubleValue];
        double size = [entry[@"size"] respondsToSelector:@selector(doubleValue)] ? [entry[@"size"] doubleValue] : 48;
        double opacity = [entry[@"opacity"] respondsToSelector:@selector(doubleValue)] ? [entry[@"opacity"] doubleValue] : 0.6;
        [_settings addObject:[@{ @"label": label, @"key": mapping,
                                 @"x": @(MAX(0.04, MIN(0.96, x))), @"y": @(MAX(0.08, MIN(0.92, y))),
                                 @"size": @(MAX(32, MIN(100, size))), @"opacity": @(MAX(0.15, MIN(1.0, opacity))) } mutableCopy]];
    }
    // Intentionally off after first installation: do not hijack the game's
    // controller selection without a positive user action.
    _enabled = [NSUserDefaults.standardUserDefaults boolForKey:kEnabledKey];
    return self;
}

- (UIButton *)makeButton:(NSString *)title action:(SEL)action {
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    button.backgroundColor = [UIColor colorWithRed:0.10 green:0.20 blue:0.38 alpha:0.80];
    [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [button setTitle:title forState:UIControlStateNormal];
    button.titleLabel.font = [UIFont boldSystemFontOfSize:12];
    button.layer.cornerRadius = 15;
    button.layer.borderColor = UIColor.whiteColor.CGColor;
    button.layer.borderWidth = 1;
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    return button;
}

- (void)attachToView:(UIView *)host {
    if (_view.superview == host) { [self layout]; return; }
    [_view removeFromSuperview];
    if (!host) return;
    if (!_view) {
        _view = [[HCCPassThroughView alloc] initWithFrame:host.bounds];
        _view.backgroundColor = UIColor.clearColor;
        _view.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        _toggle = [self makeButton:@"C+" action:@selector(toggleTapped:)];
        [_view addSubview:_toggle];
        _editor = [self makeButton:@"Sửa" action:@selector(editTapped:)];
        [_view addSubview:_editor];
        _adder = [self makeButton:@"+" action:@selector(addTapped:)];
        [_view addSubview:_adder];
        for (NSUInteger i = 0; i < _settings.count; ++i) [self installButtonForIndex:i];
    }
    [host addSubview:_view];
    [self layout];
}

- (void)installButtonForIndex:(NSUInteger)index {
    if (!_view || index >= _settings.count) return;
    UIButton *button = [self makeButton:_settings[index][@"label"] action:@selector(customTapped:)];
    button.tag = (NSInteger)index;
    [button addTarget:self action:@selector(customDown:) forControlEvents:UIControlEventTouchDown];
    [button addTarget:self action:@selector(customUp:) forControlEvents:
        (UIControlEventTouchUpOutside | UIControlEventTouchCancel | UIControlEventTouchDragExit | UIControlEventTouchUpInside)];
    UIPanGestureRecognizer *drag = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(dragged:)];
    drag.delegate = self;
    [button addGestureRecognizer:drag];
    UILongPressGestureRecognizer *edit = [[UILongPressGestureRecognizer alloc] initWithTarget:self action:@selector(longPressed:)];
    edit.numberOfTouchesRequired = 2;
    edit.minimumPressDuration = 0.6;
    [button addGestureRecognizer:edit];
    [_buttons addObject:button];
    [_view addSubview:button];
}

- (void)layout {
    if (!_view) return;
    CGFloat width = MAX(1, _view.bounds.size.width), height = MAX(1, _view.bounds.size.height);
    _toggle.frame = CGRectMake(width - 40, 6, 34, 30);
    _editor.frame = CGRectMake(width - 84, 6, 40, 30);
    _adder.frame = CGRectMake(width - 128, 6, 40, 30);
    _editor.hidden = !_enabled;
    _adder.hidden = !_enabled || !_editing || _settings.count >= 24;
    [_toggle setTitle:_enabled ? @"C−" : @"C+" forState:UIControlStateNormal];
    for (NSUInteger i = 0; i < _buttons.count; ++i) {
        UIButton *b = _buttons[i];
        NSDictionary *s = _settings[i];
        CGFloat size = [s[@"size"] doubleValue];
        b.frame = CGRectMake([s[@"x"] doubleValue] * width - size / 2,
                             [s[@"y"] doubleValue] * height - size / 2, size, size);
        b.layer.cornerRadius = size / 2;
        b.alpha = _editing ? 0.95 : [s[@"opacity"] doubleValue];
        b.hidden = !_enabled;
        [b setTitle:s[@"label"] forState:UIControlStateNormal];
        b.layer.borderColor = _editing ? UIColor.systemYellowColor.CGColor : UIColor.whiteColor.CGColor;
    }
}

- (void)addTapped:(id)sender {
    if (!_enabled || !_editing || _settings.count >= 24) return;
    [self releaseAll];
    NSUInteger i = _settings.count;
    // Each new button is independent of the game's original touch layout.
    [_settings addObject:[@{ @"label": @"SPACE", @"key": @"KEY_SPACE",
                             @"x": @(0.58 + 0.08 * (i % 4)),
                             @"y": @(0.31 + 0.11 * ((i / 4) % 5)),
                             @"size": @48, @"opacity": @0.60 } mutableCopy]];
    [self installButtonForIndex:i];
    [self layout];
    [self save];
}

- (void)removeButtonAtIndex:(NSUInteger)index {
    if (!_editing || index >= _settings.count || index >= _buttons.count) return;
    [self releaseAll];
    [_buttons[index] removeFromSuperview];
    [_buttons removeObjectAtIndex:index];
    [_settings removeObjectAtIndex:index];
    for (NSUInteger i = index; i < _buttons.count; ++i) _buttons[i].tag = (NSInteger)i;
    [self refreshVirtualPad];
    [self layout];
    [self save];
}

- (void)save {
    [NSUserDefaults.standardUserDefaults setObject:_settings forKey:kStorageKey];
    [NSUserDefaults.standardUserDefaults setBool:_enabled forKey:kEnabledKey];
}

- (void)toggleTapped:(id)sender {
    if (_enabled) {
        [self releaseAll];
        [_virtualPad disconnect];
        _virtualPad = nil;
        _connected = NO;
        _enabled = NO;
        _editing = NO;
    } else {
        _enabled = YES;
        if ([self needsVirtualPad]) [self connectPad];
    }
    [self save];
    [self layout];
}

- (BOOL)needsVirtualPad {
    for (NSDictionary *setting in _settings) {
        if (![setting[@"key"] hasPrefix:@"KEY_"]) return YES;
    }
    return NO;
}

- (void)refreshVirtualPad {
    if (!_enabled) return;
    if ([self needsVirtualPad]) {
        if (!_virtualPad) [self connectPad];
    } else if (_virtualPad) {
        [self releaseAll];
        [_virtualPad disconnect];
        _virtualPad = nil;
        _connected = NO;
    }
}

- (void)connectPad {
    if (_virtualPad) return;
    GCVirtualControllerConfiguration *config = [[GCVirtualControllerConfiguration alloc] init];
    config.hidden = YES;
    config.elements = [NSSet setWithArray:@[
        GCInputButtonA, GCInputButtonB, GCInputButtonX, GCInputButtonY,
        GCInputLeftShoulder, GCInputRightShoulder, GCInputLeftTrigger, GCInputRightTrigger,
        GCInputDirectionPad
    ]];
    GCVirtualController *pad = [[GCVirtualController alloc] initWithConfiguration:config];
    _virtualPad = pad;
    __weak typeof(self) weakSelf = self;
    [pad connectWithReplyHandler:^(NSError *error) {
        dispatch_async(dispatch_get_main_queue(), ^{
            typeof(self) strongSelf = weakSelf;
            if (!strongSelf || strongSelf.virtualPad != pad) return;
            strongSelf.connected = !error;
            if (error) {
                NSLog(@"[CustomTouch] virtual controller failed: %@", error);
                strongSelf.enabled = NO;
                [strongSelf.virtualPad disconnect];
                strongSelf.virtualPad = nil;
                [strongSelf save];
                [strongSelf layout];
            }
        });
    }];
}

- (void)editTapped:(id)sender {
    _editing = !_editing;
    if (_editing) [self releaseAll];
    [_editor setTitle:_editing ? @"Xong" : @"Sửa" forState:UIControlStateNormal];
    [self layout];
    [self save];
}

- (BOOL)gestureRecognizerShouldBegin:(UIGestureRecognizer *)gestureRecognizer {
    if ([gestureRecognizer isKindOfClass:UIPanGestureRecognizer.class]) return _editing;
    return YES;
}

- (void)longPressed:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state == UIGestureRecognizerStateBegan) [self editTapped:nil];
}

- (void)dragged:(UIPanGestureRecognizer *)gesture {
    if (!_editing || !_view) return;
    UIButton *button = (UIButton *)gesture.view;
    if (![button isKindOfClass:UIButton.class]) return;
    NSInteger index = button.tag;
    if (index < 0 || (NSUInteger)index >= _settings.count) return;
    CGPoint delta = [gesture translationInView:_view];
    CGPoint center = button.center;
    center.x = MAX(20, MIN(_view.bounds.size.width - 20, center.x + delta.x));
    center.y = MAX(40, MIN(_view.bounds.size.height - 20, center.y + delta.y));
    button.center = center;
    [gesture setTranslation:CGPointZero inView:_view];
    if (gesture.state == UIGestureRecognizerStateEnded) {
        _settings[index][@"x"] = @(center.x / MAX(1, _view.bounds.size.width));
        _settings[index][@"y"] = @(center.y / MAX(1, _view.bounds.size.height));
        [self save];
    }
}

- (UIViewController *)visibleController {
    UIResponder *responder = _view;
    while (responder && ![responder isKindOfClass:UIViewController.class]) responder = responder.nextResponder;
    UIViewController *vc = (UIViewController *)responder;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

- (void)customTapped:(UIButton *)button {
    if (!_editing) return;
    NSInteger index = button.tag;
    if (index < 0 || (NSUInteger)index >= _settings.count) return;
    UIViewController *vc = [self visibleController];
    if (!vc) return;
    UIAlertController *menu = [UIAlertController alertControllerWithTitle:[NSString stringWithFormat:@"Nút Custom %ld", (long)(index + 1)]
        message:@"Chọn phím bàn phím PC, chức năng tay cầm hoặc vị trí/kích thước." preferredStyle:UIAlertControllerStyleActionSheet];
    for (NSString *name in @[@"J", @"K", @"L", @"M", @"SPACE", @"F10", @"NUM0", @"ENTER", @"TAB"]) {
        NSString *key = [@"KEY_" stringByAppendingString:name];
        [menu addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Phím PC %@", name] style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
            self.settings[index][@"key"] = key;
            self.settings[index][@"label"] = name;
            [self refreshVirtualPad];
            [self save]; [self layout];
        }]];
    }
    [menu addAction:[UIAlertAction actionWithTitle:@"Tự nhập phím PC / tổ hợp" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        UIAlertController *entry = [UIAlertController alertControllerWithTitle:@"Phím PC"
            message:@"Ví dụ: J, SPACE, F10, NUM0, CTRL+J hoặc SHIFT+F10" preferredStyle:UIAlertControllerStyleAlert];
        [entry addTextFieldWithConfigurationHandler:^(UITextField *field) {
            NSString *old = self.settings[index][@"key"];
            field.text = [old hasPrefix:@"KEY_"] ? [old substringFromIndex:4] : @"J";
            field.autocapitalizationType = UITextAutocapitalizationTypeAllCharacters;
        }];
        [entry addAction:[UIAlertAction actionWithTitle:@"Lưu" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
            NSString *name = [entry.textFields.firstObject.text.uppercaseString stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
            NSString *key = [@"KEY_" stringByAppendingString:name ?: @""];
            if (HCCKeySequence(key).count) {
                self.settings[index][@"key"] = key;
                self.settings[index][@"label"] = [name substringToIndex:MIN(8, name.length)];
                [self refreshVirtualPad];
                [self save]; [self layout];
            } else {
                UIAlertController *error = [UIAlertController alertControllerWithTitle:@"Phím chưa hỗ trợ"
                    message:@"Hãy nhập A–Z, 0–9, F1–F12, SPACE, ENTER, TAB, ESC, NUM0–NUM9 hoặc tổ hợp CTRL/SHIFT/ALT + phím."
                    preferredStyle:UIAlertControllerStyleAlert];
                [error addAction:[UIAlertAction actionWithTitle:@"Đã hiểu" style:UIAlertActionStyleCancel handler:nil]];
                [vc presentViewController:error animated:YES completion:nil];
            }
        }]];
        [entry addAction:[UIAlertAction actionWithTitle:@"Huỷ" style:UIAlertActionStyleCancel handler:nil]];
        [vc presentViewController:entry animated:YES completion:nil];
    }]];
    NSArray<NSString *> *choices = @[@"A",@"B",@"X",@"Y",@"LB",@"RB",@"LT",@"RT",@"UP",@"DOWN",@"LEFT",@"RIGHT",@"MENYOO"];
    for (NSString *key in choices) {
        NSString *title = [NSString stringWithFormat:@"%@%@", [key isEqualToString:_settings[index][@"key"]] ? @"✓ " : @"", key];
        [menu addAction:[UIAlertAction actionWithTitle:title style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
            self.settings[index][@"key"] = key;
            self.settings[index][@"label"] = key;
            [self refreshVirtualPad];
            [self save]; [self layout];
        }]];
    }
    [menu addAction:[UIAlertAction actionWithTitle:@"Đổi tên" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        UIAlertController *name = [UIAlertController alertControllerWithTitle:@"Tên nút" message:@"Tối đa 8 ký tự" preferredStyle:UIAlertControllerStyleAlert];
        [name addTextFieldWithConfigurationHandler:^(UITextField *field) { field.text = self.settings[index][@"label"]; }];
        [name addAction:[UIAlertAction actionWithTitle:@"Lưu" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
            NSString *label = name.textFields.firstObject.text ?: @"C";
            self.settings[index][@"label"] = [label substringToIndex:MIN(8, label.length)];
            [self save]; [self layout];
        }]];
        [name addAction:[UIAlertAction actionWithTitle:@"Huỷ" style:UIAlertActionStyleCancel handler:nil]];
        [vc presentViewController:name animated:YES completion:nil];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"To hơn" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
        self.settings[index][@"size"] = @(MIN(100, [self.settings[index][@"size"] doubleValue] + 8)); [self layout]; [self save];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Nhỏ hơn" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
        self.settings[index][@"size"] = @(MAX(32, [self.settings[index][@"size"] doubleValue] - 8)); [self layout]; [self save];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Mờ hơn" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
        self.settings[index][@"opacity"] = @(MAX(0.15, [self.settings[index][@"opacity"] doubleValue] - 0.15)); [self layout]; [self save];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Rõ hơn" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *a) {
        self.settings[index][@"opacity"] = @(MIN(1.0, [self.settings[index][@"opacity"] doubleValue] + 0.15)); [self layout]; [self save];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Xoá nút này" style:UIAlertActionStyleDestructive handler:^(__unused UIAlertAction *a) {
        UIAlertController *confirm = [UIAlertController alertControllerWithTitle:@"Xoá nút Custom?"
            message:@"Chỉ xoá nút tuỳ chỉnh này, không xoá nút gốc của game."
            preferredStyle:UIAlertControllerStyleAlert];
        [confirm addAction:[UIAlertAction actionWithTitle:@"Xoá" style:UIAlertActionStyleDestructive handler:^(__unused UIAlertAction *action) {
            [self removeButtonAtIndex:(NSUInteger)index];
        }]];
        [confirm addAction:[UIAlertAction actionWithTitle:@"Huỷ" style:UIAlertActionStyleCancel handler:nil]];
        [vc presentViewController:confirm animated:YES completion:nil];
    }]];
    [menu addAction:[UIAlertAction actionWithTitle:@"Đóng" style:UIAlertActionStyleCancel handler:nil]];
    UIPopoverPresentationController *popover = menu.popoverPresentationController;
    if (popover) { popover.sourceView = button; popover.sourceRect = button.bounds; }
    [vc presentViewController:menu animated:YES completion:nil];
}

- (void)customDown:(UIButton *)button {
    if (_editing || !_enabled) return;
    if (button.tag < 0 || (NSUInteger)button.tag >= _settings.count) return;
    NSString *key = _settings[button.tag][@"key"];
    if ([key hasPrefix:@"KEY_"]) {
        if (!HCCResolveSendKey() || !HCCKeySequence(key).count) return;
        [_pressed addObject:@(button.tag)];
        [self updateKeyboard];
        return;
    }
    if (!_connected) return;
    [_pressed addObject:@(button.tag)];
    [self updatePad];
}

- (void)customUp:(UIButton *)button {
    [_pressed removeObject:@(button.tag)];
    [self updateKeyboard];
    [self updatePad];
}

- (void)releaseAll {
    [_pressed removeAllObjects];
    [self updateKeyboard];
    [self updatePad];
}

- (void)updateKeyboard {
    // Union active keys across buttons so e.g. CTRL+J and J can be held
    // simultaneously without releasing a shared key prematurely.
    NSMutableSet<NSNumber *> *desired = [NSMutableSet set];
    for (NSNumber *number in _pressed) {
        if (number.unsignedIntegerValue >= _settings.count) continue;
        NSString *key = _settings[number.unsignedIntegerValue][@"key"];
        for (NSNumber *usage in HCCKeySequence(key)) [desired addObject:usage];
    }
    // Release ordinary keys first, then modifiers; press modifiers first.
    for (NSUInteger pass = 0; pass < 2; ++pass) {
        for (NSNumber *usage in [_keyboardHeld allObjects]) {
            BOOL modifier = usage.unsignedIntegerValue >= 0xe0;
            if ([desired containsObject:usage] || modifier != (pass == 1)) continue;
            HCCSendKeyboardUsage(usage.unsignedCharValue, NO);
            [_keyboardHeld removeObject:usage];
        }
    }
    for (NSUInteger pass = 0; pass < 2; ++pass) {
        NSArray<NSNumber *> *ordered = [[desired allObjects] sortedArrayUsingSelector:@selector(compare:)];
        for (NSNumber *usage in ordered) {
            BOOL modifier = usage.unsignedIntegerValue >= 0xe0;
            if ([_keyboardHeld containsObject:usage] || modifier != (pass == 0)) continue;
            if (HCCSendKeyboardUsage(usage.unsignedCharValue, YES)) [_keyboardHeld addObject:usage];
        }
    }
}

- (void)updatePad {
    if (!_virtualPad || !_connected) return;
    NSMutableSet<NSString *> *active = [NSMutableSet set];
    for (NSNumber *number in _pressed) {
        if (number.unsignedIntegerValue >= _settings.count) continue;
        NSString *key = _settings[number.integerValue][@"key"];
        if ([key hasPrefix:@"KEY_"]) continue;
        if ([key isEqualToString:@"MENYOO"]) {
            [active addObject:@"RB"];
            [active addObject:@"LEFT"];
        } else {
            [active addObject:key];
        }
    }
    NSDictionary<NSString *,NSString *> *padKeys = @{
        @"A":GCInputButtonA, @"B":GCInputButtonB, @"X":GCInputButtonX, @"Y":GCInputButtonY,
        @"LB":GCInputLeftShoulder, @"RB":GCInputRightShoulder,
        @"LT":GCInputLeftTrigger, @"RT":GCInputRightTrigger
    };
    for (NSString *key in padKeys) {
        [_virtualPad setValue:[active containsObject:key] ? 1 : 0 forButtonElement:padKeys[key]];
    }
    CGFloat dx = ([active containsObject:@"RIGHT"] ? 1 : 0) - ([active containsObject:@"LEFT"] ? 1 : 0);
    CGFloat dy = ([active containsObject:@"UP"] ? 1 : 0) - ([active containsObject:@"DOWN"] ? 1 : 0);
    [_virtualPad setPosition:CGPointMake(dx, dy) forDirectionPadElement:GCInputDirectionPad];
}

@end

static HCCOverlay *gCustomTouch;

static BOOL HCCViewControllerIsGame(UIViewController *vc) {
    if (!vc) return NO;
    if ([NSStringFromClass(vc.class) containsString:@"MacwinViewController"]) return YES;
    for (UIViewController *child in vc.childViewControllers) if (HCCViewControllerIsGame(child)) return YES;
    return NO;
}

static void HCCAttachIfReady(void) {
    if (!gCustomTouch) gCustomTouch = [[HCCOverlay alloc] init];
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class]) continue;
        for (UIWindow *window in ((UIWindowScene *)scene).windows) {
            if (!window.hidden && HCCViewControllerIsGame(window.rootViewController)) {
                [gCustomTouch attachToView:window.rootViewController.view];
                if (gCustomTouch.enabled && [gCustomTouch needsVirtualPad] && !gCustomTouch.virtualPad) [gCustomTouch connectPad];
                return;
            }
        }
    }
    // Never place controls over the launcher, login, or unrelated UI.
    [gCustomTouch releaseAll];
    if (gCustomTouch.virtualPad) {
        [gCustomTouch.virtualPad disconnect];
        gCustomTouch.virtualPad = nil;
        gCustomTouch.connected = NO;
    }
    [gCustomTouch.view removeFromSuperview];
}

__attribute__((constructor)) static void HCCInitialize(void) {
    dispatch_async(dispatch_get_main_queue(), ^{
        [NSNotificationCenter.defaultCenter addObserverForName:UIApplicationDidBecomeActiveNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(__unused NSNotification *notice) {
            HCCAttachIfReady();
        }];
        [NSNotificationCenter.defaultCenter addObserverForName:UIApplicationWillResignActiveNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(__unused NSNotification *notice) {
            [gCustomTouch releaseAll];
        }];
        [NSTimer scheduledTimerWithTimeInterval:1.5 repeats:YES block:^(__unused NSTimer *timer) {
            HCCAttachIfReady();
        }];
        HCCAttachIfReady();
    });
}

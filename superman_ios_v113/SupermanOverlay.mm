#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <AVFoundation/AVFoundation.h>

#import <dlfcn.h>
#include <atomic>
#include <cmath>
#include <cstring>

#include "GameplayCore.hpp"

@interface SMPassThroughView : UIView
@end

@implementation SMPassThroughView
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit = [super hitTest:point withEvent:event];
    return hit == self ? nil : hit;
}
@end

@interface SMOverlay : NSObject
@property(nonatomic, strong) SMPassThroughView *panel;
@property(nonatomic, strong) UIButton *toggle;
@property(nonatomic, strong) NSMutableArray<UIButton *> *buttons;
@property(nonatomic, strong) NSMutableDictionary<NSString *,NSNumber *> *positions;
@property(nonatomic, strong) AVAudioPlayer *audio;
@property(nonatomic, assign) BOOL editMode;
@property(nonatomic, assign) CGSize lastLayoutSize;
@end

@implementation SMOverlay

+ (instancetype)shared {
    static SMOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[SMOverlay alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (!self) return nil;
    _buttons = [NSMutableArray array];
    NSDictionary *saved = [[NSUserDefaults standardUserDefaults] dictionaryForKey:@"SupermanIOS.v113.positions"];
    _positions = saved ? [saved mutableCopy] : [NSMutableDictionary dictionary];
    return self;
}

- (UIButton *)addButton:(NSString *)title action:(SupermanAction)action hold:(BOOL)hold {
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    [button setTitle:title forState:UIControlStateNormal];
    [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    button.titleLabel.font = [UIFont boldSystemFontOfSize:12];
    button.backgroundColor = [UIColor colorWithRed:0.10 green:0.18 blue:0.30 alpha:0.76];
    button.layer.cornerRadius = 18;
    button.layer.borderWidth = 1;
    button.layer.borderColor = [UIColor colorWithWhite:0.9 alpha:0.5].CGColor;
    button.tag = (NSInteger)action;
    button.accessibilityLabel = title;
    if (hold) {
        [button addTarget:self action:@selector(pressed:) forControlEvents:UIControlEventTouchDown];
        [button addTarget:self action:@selector(released:) forControlEvents:(UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel | UIControlEventTouchDragExit)];
    } else {
        [button addTarget:self action:@selector(tapped:) forControlEvents:UIControlEventTouchUpInside];
    }
    UIPanGestureRecognizer *drag = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(drag:)];
    drag.minimumNumberOfTouches = 1;
    drag.maximumNumberOfTouches = 1;
    drag.enabled = NO;
    [button addGestureRecognizer:drag];
    [_buttons addObject:button];
    [_panel addSubview:button];
    return button;
}

- (void)tapped:(UIButton *)sender {
    if (_editMode) return;
    if (!gSMScriptRunning.load(std::memory_order_relaxed)) return;
    SMButtonClick((uint32_t)sender.tag);
}
- (void)pressed:(UIButton *)sender {
    if (_editMode || !gSMScriptRunning.load(std::memory_order_relaxed)) return;
    SMButtonHold((uint32_t)sender.tag, true);
    sender.alpha = 0.55;
}
- (void)released:(UIButton *)sender {
    SMButtonHold((uint32_t)sender.tag, false);
    sender.alpha = 1;
}

- (void)toggleEdit:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state != UIGestureRecognizerStateBegan) return;
    _editMode = !_editMode;
    for (UIButton *button in _buttons) {
        for (UIGestureRecognizer *recognizer in button.gestureRecognizers) {
            if ([recognizer isKindOfClass:UIPanGestureRecognizer.class]) recognizer.enabled = _editMode;
        }
    }
    [_toggle setTitle:_editMode ? @"XONG" : @"S" forState:UIControlStateNormal];
    gSMHolds.store(0, std::memory_order_relaxed);
}

- (void)drag:(UIPanGestureRecognizer *)gesture {
    if (!_editMode || !_panel) return;
    UIView *button = gesture.view;
    CGPoint delta = [gesture translationInView:_panel];
    CGFloat width = MAX(_panel.bounds.size.width, 1), height = MAX(_panel.bounds.size.height, 1);
    CGPoint center = button.center;
    center.x = MIN(width - 23, MAX(23, center.x + delta.x));
    center.y = MIN(height - 23, MAX(23, center.y + delta.y));
    button.center = center;
    [gesture setTranslation:CGPointZero inView:_panel];
    if (gesture.state == UIGestureRecognizerStateEnded) {
        NSString *key = [NSString stringWithFormat:@"%ld", (long)button.tag];
        _positions[[key stringByAppendingString:@".x"]] = @(center.x / width);
        _positions[[key stringByAppendingString:@".y"]] = @(center.y / height);
        [[NSUserDefaults standardUserDefaults] setObject:_positions forKey:@"SupermanIOS.v113.positions"];
    }
}

- (void)makePanel {
    _panel = [[SMPassThroughView alloc] initWithFrame:CGRectZero];
    _panel.backgroundColor = UIColor.clearColor;
    _panel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    _toggle = [self addButton:@"S" action:SM_TOGGLE hold:NO];
    UILongPressGestureRecognizer *edit = [[UILongPressGestureRecognizer alloc] initWithTarget:self action:@selector(toggleEdit:)];
    edit.minimumPressDuration = 0.6;
    [_toggle addGestureRecognizer:edit];
    [self addButton:@"BAY" action:SM_FLIGHT hold:NO];
    [self addButton:@"TIẾN" action:SM_FORWARD hold:YES];
    [self addButton:@"LÊN" action:SM_UP hold:YES];
    [self addButton:@"XUỐNG" action:SM_DOWN hold:YES];
    [self addButton:@"HEAT" action:SM_HEAT hold:YES];
    [self addButton:@"SÓNG" action:SM_SHOCK hold:NO];
    [self addButton:@"NHANH" action:SM_BOOST hold:YES];
    [self addButton:@"NỆN" action:SM_GROUND hold:NO];
}

- (void)layoutForHost:(UIView *)host {
    if (!_panel) [self makePanel];
    BOOL needsLayout = (_panel.superview != host || !CGSizeEqualToSize(_lastLayoutSize, host.bounds.size));
    if (_panel.superview != host) {
        [_panel removeFromSuperview];
        _panel.frame = host.bounds;
        [host addSubview:_panel];
    }
    if (!needsLayout) return;
    _lastLayoutSize = host.bounds.size;
    const CGPoint defaults[] = {
        {0.50, 0.10}, {0.69, 0.23}, {0.81, 0.41}, {0.91, 0.36},
        {0.91, 0.57}, {0.80, 0.23}, {0.69, 0.43}, {0.90, 0.23},
        {0.69, 0.61}
    };
    CGFloat width = MAX(_panel.bounds.size.width, 1), height = MAX(_panel.bounds.size.height, 1);
    for (NSUInteger i = 0; i < _buttons.count && i < 9; ++i) {
        UIButton *button = _buttons[i];
        NSString *key = [NSString stringWithFormat:@"%ld", (long)button.tag];
        NSNumber *x = _positions[[key stringByAppendingString:@".x"]];
        NSNumber *y = _positions[[key stringByAppendingString:@".y"]];
        CGFloat posX = x ? x.doubleValue : defaults[i].x;
        CGFloat posY = y ? y.doubleValue : defaults[i].y;
        posX = MAX(0.04, MIN(posX, 0.96));
        posY = MAX(0.08, MIN(posY, 0.92));
        button.frame = CGRectMake(posX * width - 23, posY * height - 18, 46, 36);
    }
}

- (void)refresh {
    UIWindow *front = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class] || scene.activationState != UISceneActivationStateForegroundActive) continue;
        for (UIWindow *window in ((UIWindowScene *)scene).windows) {
            if (window.isKeyWindow && !window.hidden) { front = window; break; }
        }
        if (front) break;
    }
    if (!front) return;
    [self layoutForHost:front];

    const bool registered = gSMScriptRunning.load(std::memory_order_relaxed);
    const bool enabled = gSMEnabled.load(std::memory_order_relaxed);
    _toggle.enabled = registered;
    [_toggle setTitle:_editMode ? @"XONG" : (registered ? (enabled ? @"S ON" : @"S") : @"S...") forState:UIControlStateNormal];
    _toggle.backgroundColor = enabled ? [UIColor colorWithRed:0.1 green:0.5 blue:0.2 alpha:0.85] :
                                        [UIColor colorWithRed:0.20 green:0.25 blue:0.4 alpha:0.75];
    for (UIButton *button in _buttons) {
        button.hidden = (button != _toggle && !enabled && !_editMode);
        if (!enabled && button != _toggle) SMButtonHold((uint32_t)button.tag, false);
    }
}

- (void)playSound:(NSString *)name {
    static NSSet<NSString *> *allowed;
    static dispatch_once_t token;
    dispatch_once(&token, ^{
        allowed = [NSSet setWithArray:@[@"takeoff", @"heat_vision", @"thunder_clap", @"ground_pound"]];
    });
    if (![allowed containsObject:name]) return;
    NSString *path = [NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:
                      [NSString stringWithFormat:@"Frameworks/Superman_SFX/%@.wav", name]];
    if (![[NSFileManager defaultManager] isReadableFileAtPath:path]) return;
    NSURL *url = [NSURL fileURLWithPath:path];
    NSError *error = nil;
    AVAudioPlayer *player = [[AVAudioPlayer alloc] initWithContentsOfURL:url error:&error];
    if (error || !player) return;
    _audio = player;
    [_audio prepareToPlay];
    [_audio play];
}
@end

extern "C" void SMPlaySound(const char *name) {
    if (!name || strlen(name) > 32) return;
    NSString *sound = [NSString stringWithUTF8String:name];
    dispatch_async(dispatch_get_main_queue(), ^{ [[SMOverlay shared] playSound:sound]; });
}

static void SMReadConfig(void) {
    NSString *path = [NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"Frameworks/Superman_iOS.json"];
    NSData *data = [NSData dataWithContentsOfFile:path];
    NSDictionary *config = [NSJSONSerialization JSONObjectWithData:data ?: [NSData data] options:0 error:NULL];
    if (![config isKindOfClass:NSDictionary.class]) return;
    SMSettings s;
#define SM_CONFIG_FLOAT(name, field) if ([config[@name] respondsToSelector:@selector(floatValue)]) s.field = [config[@name] floatValue]
#define SM_CONFIG_INT(name, field) if ([config[@name] respondsToSelector:@selector(intValue)]) s.field = [config[@name] intValue]
    SM_CONFIG_FLOAT("cruise_speed", cruiseSpeed);
    SM_CONFIG_FLOAT("boost_speed", boostSpeed);
    SM_CONFIG_FLOAT("vertical_speed", verticalSpeed);
    SM_CONFIG_FLOAT("heat_range", heatRange);
    SM_CONFIG_FLOAT("shock_radius", shockRadius);
    SM_CONFIG_FLOAT("shock_force", shockForce);
    SM_CONFIG_FLOAT("shock_lift", shockLift);
    SM_CONFIG_INT("heat_damage", heatDamage);
    SM_CONFIG_INT("heat_interval_ms", heatIntervalMs);
    SM_CONFIG_INT("shock_cooldown_ms", shockCooldownMs);
#undef SM_CONFIG_FLOAT
#undef SM_CONFIG_INT
    SMSetSettings(s);
}

static void *gSMModuleHandle = nullptr;
typedef void (*SMRegister)(void *, void (*)());

static void SMTryRegister(void) {
    if (gSMScriptRegistered.load(std::memory_order_relaxed)) return;
    SMRegister reg = reinterpret_cast<SMRegister>(dlsym(RTLD_DEFAULT, "scriptRegister"));
    if (!reg || !dlsym(RTLD_DEFAULT, "scriptWait") || !dlsym(RTLD_DEFAULT, "nativeCall")) return;
    Dl_info info;
    if (!dladdr(reinterpret_cast<const void *>(&SMGameplayMain), &info) || !info.dli_fbase) return;
    gSMModuleHandle = info.dli_fbase;
    SMReadConfig();
    reg(gSMModuleHandle, &SMGameplayMain);
    gSMScriptRegistered.store(true, std::memory_order_relaxed);
    NSLog(@"[Superman iOS] Script registered with ScriptHookV; gameplay disabled by default");
}

__attribute__((constructor)) static void SMStartup(void) {
    dispatch_async(dispatch_get_main_queue(), ^{
        [NSTimer scheduledTimerWithTimeInterval:1.2 repeats:YES block:^(NSTimer *timer) {
            SMTryRegister();
            [[SMOverlay shared] refresh];
        }];
    });
}

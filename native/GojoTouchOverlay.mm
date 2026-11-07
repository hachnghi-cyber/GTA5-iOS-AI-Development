// EXPERIMENTAL UIKit layer for the GTA V iOS v11 TCOverlay class.
// Not compiled or validated on an iOS device. Requires an iOS toolchain,
// legitimate signing, and an app-approved library loading path.
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#include <atomic>
#include "GojoTouchQueue.h"

static std::atomic_bool gEnabled{false};
static char kGojoOverlayAssociation;
static IMP gOriginalInit = NULL;
static NSHashTable<UIView *> *gGojoContainers;

@interface GojoTouchTarget : NSObject
- (void)pressed:(UIButton *)sender;
@end

@implementation GojoTouchTarget
- (void)pressed:(UIButton *)sender
{
    if (!gEnabled.load(std::memory_order_acquire)) return;
    NSInteger action = sender.tag;
    if (action >= 0 && action < 5) gojo_touch_press((unsigned int)action);
}
@end

static GojoTouchTarget *gTarget;

static UIButton *GojoMakeButton(NSString *title, NSInteger index)
{
    UIButton *button = [UIButton buttonWithType:UIButtonTypeCustom];
    button.tag = index;
    [button setTitle:title forState:UIControlStateNormal];
    [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    button.titleLabel.font = [UIFont boldSystemFontOfSize:12.0];
    button.backgroundColor = [[UIColor blackColor] colorWithAlphaComponent:0.62];
    button.layer.cornerRadius = 10.0;
    button.layer.borderWidth = 1.0;
    button.layer.borderColor = [[UIColor whiteColor] colorWithAlphaComponent:0.4].CGColor;
    [button addTarget:gTarget action:@selector(pressed:) forControlEvents:UIControlEventTouchUpInside];
    button.translatesAutoresizingMaskIntoConstraints = NO;
    return button;
}

static void GojoAttachToOverlay(UIView *host)
{
    if (!host || objc_getAssociatedObject(host, &kGojoOverlayAssociation)) return;
    if (!gTarget) gTarget = [GojoTouchTarget new];
    if (!gGojoContainers) gGojoContainers = [NSHashTable weakObjectsHashTable];

    // It is important that this remains a child view of the actual touch
    // overlay. The controller, pause, and Menyoo buttons stay untouched.
    UIView *container = [UIView new];
    container.translatesAutoresizingMaskIntoConstraints = NO;
    container.userInteractionEnabled = YES;
    container.hidden = !gEnabled.load(std::memory_order_acquire);

    UIStackView *stack = [[UIStackView alloc] initWithFrame:CGRectZero];
    stack.axis = UILayoutConstraintAxisVertical;
    stack.spacing = 5;
    stack.distribution = UIStackViewDistributionFillEqually;
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    NSArray<NSString *> *titles = @[@"INFINITY", @"RED", @"BLUE", @"PURPLE", @"VOID"];
    for (NSInteger i = 0; i < titles.count; ++i)
        [stack addArrangedSubview:GojoMakeButton(titles[i], i)];

    [container addSubview:stack];
    [host addSubview:container];
    [NSLayoutConstraint activateConstraints:@[
        [container.trailingAnchor constraintEqualToAnchor:host.safeAreaLayoutGuide.trailingAnchor constant:-9],
        [container.centerYAnchor constraintEqualToAnchor:host.centerYAnchor],
        [container.widthAnchor constraintEqualToConstant:68],
        [container.heightAnchor constraintEqualToConstant:246],
        [stack.topAnchor constraintEqualToAnchor:container.topAnchor],
        [stack.bottomAnchor constraintEqualToAnchor:container.bottomAnchor],
        [stack.leadingAnchor constraintEqualToAnchor:container.leadingAnchor],
        [stack.trailingAnchor constraintEqualToAnchor:container.trailingAnchor],
    ]];

    objc_setAssociatedObject(host, &kGojoOverlayAssociation, container,
                             OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    [gGojoContainers addObject:container];
}

static void GojoFindExistingOverlays(UIView *root, Class overlayClass)
{
    if (!root || !overlayClass) return;
    if ([root isKindOfClass:overlayClass]) GojoAttachToOverlay(root);
    for (UIView *child in root.subviews) GojoFindExistingOverlays(child, overlayClass);
}

static void GojoRefreshAttachedOverlays(void)
{
    Class cls = NSClassFromString(@"TCOverlay");
    if (!cls) return;
    for (UIWindow *window in UIApplication.sharedApplication.windows)
        GojoFindExistingOverlays(window, cls);
}

static id GojoInitWithFrame(id self, SEL command, CGRect frame)
{
    typedef id (*OriginalInit)(id, SEL, CGRect);
    id view = ((OriginalInit)gOriginalInit)(self, command, frame);
    // initWithFrame: executes on the UIKit thread in this app; defer the UI
    // mutation in case TCOverlay has not finished setting up its own controls.
    dispatch_async(dispatch_get_main_queue(), ^{
        if ([view isKindOfClass:[UIView class]]) GojoAttachToOverlay((UIView *)view);
    });
    return view;
}

extern "C" GOJO_TOUCH_API void gojo_touch_set_enabled(int enabled)
{
    bool on = enabled != 0;
    gEnabled.store(on, std::memory_order_release);
    if (!on) gojo_touch_clear();
    dispatch_async(dispatch_get_main_queue(), ^{
        if (on) GojoRefreshAttachedOverlays();
        for (UIView *view in gGojoContainers.allObjects) view.hidden = !on;
    });
}

__attribute__((constructor)) static void GojoInstallUIKitHook(void)
{
    dispatch_async(dispatch_get_main_queue(), ^{
        Class overlay = NSClassFromString(@"TCOverlay");
        if (!overlay || gOriginalInit) return;
        Method init = class_getInstanceMethod(overlay, @selector(initWithFrame:));
        if (!init) return;
        gOriginalInit = method_getImplementation(init);
        if (gOriginalInit)
            method_setImplementation(init, (IMP)GojoInitWithFrame);
        GojoRefreshAttachedOverlays();
        [[NSNotificationCenter defaultCenter]
            addObserverForName:UIApplicationDidBecomeActiveNotification
                       object:nil
                        queue:NSOperationQueue.mainQueue
                   usingBlock:^(NSNotification *note) {
                       (void)note;
                       GojoRefreshAttachedOverlays();
                   }];
    });
}

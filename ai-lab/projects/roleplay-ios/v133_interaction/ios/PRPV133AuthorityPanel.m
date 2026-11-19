#import <UIKit/UIKit.h>
#import "PRPV133AuthorityClient.h"
#include "rp_v133_authority_social.h"

@interface PRPV133AuthorityPanel : NSObject
@property(nonatomic, strong) UIStackView *container;
@property(nonatomic, strong) UIStackView *panel;
@property(nonatomic, strong) UILabel *status;
@property(nonatomic, strong) UILabel *event;
@property(nonatomic, strong) UIButton *toggle;
@property(nonatomic, strong) UIButton *consent;
@property(nonatomic, strong) UIButton *greet;
@property(nonatomic, strong) UIButton *documents;
@property(nonatomic, strong) NSTimer *refreshTimer;
@property(nonatomic) BOOL optedIn;
@property(nonatomic) BOOL reading;
- (void)attach;
- (void)setOpen:(BOOL)open;
- (void)refresh;
@end

@implementation PRPV133AuthorityPanel
- (UIButton *)button:(NSString *)title action:(SEL)action {
    UIButtonConfiguration *style = [UIButtonConfiguration tintedButtonConfiguration];
    style.title = title;
    style.cornerStyle = UIButtonConfigurationCornerStyleMedium;
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    button.configuration = style;
    return button;
}

- (UILabel *)label {
    UILabel *label = [[UILabel alloc] init];
    label.font = [UIFont preferredFontForTextStyle:UIFontTextStyleFootnote];
    label.adjustsFontForContentSizeCategory = YES;
    label.numberOfLines = 2;
    return label;
}

- (instancetype)init {
    self = [super init];
    if (!self) return nil;
    self.toggle = [self button:@"RP riêng" action:@selector(togglePanel)];
    self.consent = [self button:@"Tham gia RP" action:@selector(changeConsent)];
    self.greet = [self button:@"Chào hỏi" action:@selector(sendGreet)];
    self.documents = [self button:@"Yêu cầu giấy tờ" action:@selector(sendDocuments)];
    self.consent.enabled = self.greet.enabled = self.documents.enabled = NO;
    self.status = [self label];
    self.event = [self label];
    self.panel = [[UIStackView alloc] initWithArrangedSubviews:
                  @[self.status, self.event, self.consent, self.greet, self.documents]];
    self.panel.axis = UILayoutConstraintAxisVertical;
    self.panel.spacing = 4;
    self.panel.layoutMarginsRelativeArrangement = YES;
    self.panel.layoutMargins = UIEdgeInsetsMake(8, 10, 8, 10);
    self.panel.backgroundColor = UIColor.systemBackgroundColor;
    self.panel.hidden = YES;
    [self.panel.widthAnchor constraintEqualToConstant:226].active = YES;
    self.container = [[UIStackView alloc] initWithArrangedSubviews:@[self.toggle, self.panel]];
    self.container.axis = UILayoutConstraintAxisVertical;
    self.container.alignment = UIStackViewAlignmentTrailing;
    self.container.spacing = 4;
    self.container.translatesAutoresizingMaskIntoConstraints = NO;
    NSNotificationCenter *notifications = NSNotificationCenter.defaultCenter;
    [notifications addObserver:self selector:@selector(windowChanged:)
                           name:UIApplicationDidBecomeActiveNotification object:nil];
    [notifications addObserver:self selector:@selector(windowChanged:)
                           name:UIWindowDidBecomeKeyNotification object:nil];
    [notifications addObserver:self selector:@selector(suspend:)
                           name:UIApplicationWillResignActiveNotification object:nil];
    return self;
}

- (void)windowChanged:(NSNotification *)notification {
    (void)notification;
    [self attach];
}

- (void)suspend:(NSNotification *)notification {
    (void)notification;
    [self setOpen:NO];
}

- (void)attach {
    if (UIApplication.sharedApplication.applicationState != UIApplicationStateActive) return;
    UIWindow *window = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (scene.activationState == UISceneActivationStateForegroundActive &&
            [scene isKindOfClass:UIWindowScene.class]) {
            window = ((UIWindowScene *)scene).keyWindow;
            if (window.windowLevel == UIWindowLevelNormal && window.rootViewController) break;
            window = nil;
        }
    }
    if (!window) {
        id<UIApplicationDelegate> delegate = UIApplication.sharedApplication.delegate;
        if ([delegate respondsToSelector:@selector(window)]) window = delegate.window;
    }
    if (!window || window.windowLevel != UIWindowLevelNormal ||
        !window.rootViewController || self.container.superview == window) return;
    [self.container removeFromSuperview];
    [window addSubview:self.container];
    UILayoutGuide *safe = window.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [self.container.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-10],
        [self.container.topAnchor constraintEqualToAnchor:safe.topAnchor constant:8],
    ]];
}

- (void)togglePanel { [self setOpen:self.panel.hidden]; }
- (void)changeConsent { prp_authority_panel_consent(!self.optedIn); }
- (void)sendGreet { prp_authority_panel_send(RP_V133_GREET); }
- (void)sendDocuments { prp_authority_panel_send(RP_V133_DOCUMENTS); }

- (void)setOpen:(BOOL)open {
    self.panel.hidden = !open;
    [self.refreshTimer invalidate];
    self.refreshTimer = nil;
    if (!open) return;
    [self refresh];
    __weak PRPV133AuthorityPanel *weakSelf = self;
    self.refreshTimer = [NSTimer scheduledTimerWithTimeInterval:0.5 repeats:YES
        block:^(NSTimer *timer) { (void)timer; [weakSelf refresh]; }];
}

- (void)refresh {
    if (self.reading) return;
    self.reading = YES;
    prp_authority_read_status(^(NSDictionary *state) {
        self.reading = NO;
        if (self.panel.hidden) return;
        BOOL ready = [state[@"panel_ready"] boolValue];
        BOOL busy = [state[@"pending"] boolValue] || [state[@"panel_social_pending"] boolValue];
        BOOL peer = [state[@"panel_peer_consented"] boolValue];
        self.optedIn = [state[@"panel_consented"] boolValue];
        UIButtonConfiguration *consentStyle = self.consent.configuration;
        consentStyle.title = self.optedIn ? @"Rời RP" : @"Tham gia RP";
        self.consent.configuration = consentStyle;
        self.consent.enabled = ready && !busy;
        self.greet.enabled = self.documents.enabled = ready && !busy && self.optedIn && peer;
        NSString *status;
        if (!ready) status = [state[@"connected"] boolValue] ? @"Đang đồng bộ" : @"Chưa kết nối server RP";
        else if (busy) status = @"Đang chờ phản hồi";
        else if (!self.optedIn) status = @"Bạn chưa tham gia RP";
        else if (!peer) status = @"Đang chờ người chơi kia tham gia";
        else status = @"Hai bên đã tham gia RP";
        self.status.text = status;
        NSString *event = state[@"panel_event"];
        NSString *receipt = nil;
        switch ([state[@"panel_receipt"] unsignedIntValue]) {
            case 1: receipt = @"Server từ chối yêu cầu"; break;
            case 2: receipt = @"Ứng dụng người nhận đã xác nhận"; break;
            case 3: receipt = @"Yêu cầu đã hủy hoặc quá hạn"; break;
        }
        self.event.text = event.length && receipt.length ?
            [@[event, receipt] componentsJoinedByString:@"\n"] : (receipt ?: event);
        self.event.hidden = !self.event.text.length;
    });
}
@end

void prp_install_authority_panel(void) {
    static PRPV133AuthorityPanel *panel;
    if (!panel) panel = [[PRPV133AuthorityPanel alloc] init];
    [panel attach];
}

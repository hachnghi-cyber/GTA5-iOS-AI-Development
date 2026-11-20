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
@property(nonatomic, strong) UIButton *login;
@property(nonatomic, strong) UIButton *signup;
@property(nonatomic, strong) UIButton *logout;
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
    self.login = [self button:@"Đăng nhập" action:@selector(showLogin)];
    self.signup = [self button:@"Tạo tài khoản" action:@selector(showSignup)];
    self.logout = [self button:@"Đăng xuất" action:@selector(logoutAccount)];
    self.login.hidden = self.signup.hidden = self.logout.hidden = YES;
    self.consent.enabled = self.greet.enabled = self.documents.enabled = NO;
    self.status = [self label];
    self.event = [self label];
    self.panel = [[UIStackView alloc] initWithArrangedSubviews:
                  @[self.status, self.event, self.login, self.signup, self.consent,
                    self.greet, self.documents, self.logout]];
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

- (void)showLogin { [self accountForm:NO]; }
- (void)showSignup { [self accountForm:YES]; }
- (void)logoutAccount { prp_authority_logout(); }

- (void)accountForm:(BOOL)create {
    UIViewController *presenter = self.container.window.rootViewController;
    while (presenter.presentedViewController) presenter = presenter.presentedViewController;
    if (!presenter || [presenter isKindOfClass:UIAlertController.class]) return;
    UIAlertController *form = [UIAlertController alertControllerWithTitle:create ? @"Tạo tài khoản RP" : @"Đăng nhập RP"
        message:create ? @"Tên gồm 3–32 chữ cái Latin, chữ số hoặc dấu gạch dưới. Mật khẩu từ 15 đến 128 ký tự."
                       : @"Nhập tài khoản của bạn trên server RP."
        preferredStyle:UIAlertControllerStyleAlert];
    [form addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"Tên tài khoản";
        field.textContentType = UITextContentTypeUsername;
        field.autocapitalizationType = UITextAutocapitalizationTypeNone;
        field.autocorrectionType = UITextAutocorrectionTypeNo;
        field.keyboardType = UIKeyboardTypeASCIICapable;
    }];
    [form addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"Mật khẩu";
        field.secureTextEntry = YES;
        field.textContentType = create ? UITextContentTypeNewPassword : UITextContentTypePassword;
    }];
    if (create) [form addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"Nhập lại mật khẩu";
        field.secureTextEntry = YES;
        field.textContentType = UITextContentTypeNewPassword;
    }];
    __weak UIAlertController *weakForm = form;
    UIAlertAction *submit = [UIAlertAction actionWithTitle:create ? @"Tạo tài khoản" : @"Đăng nhập"
        style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
            (void)action;
            NSArray<UITextField *> *fields = weakForm.textFields;
            prp_authority_account(create, fields[0].text, fields[1].text);
            for (UITextField *field in fields) field.text = @"";
        }];
    submit.enabled = NO;
    [form addAction:[UIAlertAction actionWithTitle:@"Hủy" style:UIAlertActionStyleCancel handler:nil]];
    [form addAction:submit];
    for (UITextField *field in form.textFields) {
        [field addAction:[UIAction actionWithHandler:^(__kindof UIAction *action) {
            (void)action;
            NSArray<UITextField *> *fields = weakForm.textFields;
            if (!fields) return;
            NSString *name = fields[0].text, *password = fields[1].text;
            NSRange match = [name rangeOfString:@"^[A-Za-z0-9_]{3,32}$" options:NSRegularExpressionSearch];
            NSUInteger length = [password lengthOfBytesUsingEncoding:NSUTF32LittleEndianStringEncoding] / 4;
            submit.enabled = name.length >= 3 && match.location == 0 && match.length == name.length &&
                length >= (create ? 15u : 1u) && length <= 128 &&
                (!create || [password isEqualToString:fields[2].text]);
        }] forControlEvents:UIControlEventEditingChanged];
    }
    [presenter presentViewController:form animated:YES completion:nil];
}

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
        BOOL account = [state[@"account_mode"] boolValue];
        BOOL active = [state[@"account_active"] boolValue];
        BOOL authBusy = [state[@"auth_busy"] boolValue];
        BOOL expired = [state[@"profile_expired"] boolValue];
        self.login.hidden = self.signup.hidden = !account || active;
        self.login.enabled = self.signup.enabled = !authBusy && !expired;
        self.logout.hidden = !account || !active;
        self.consent.hidden = self.greet.hidden = self.documents.hidden = account && !active;
        BOOL busy = [state[@"pending"] boolValue] || [state[@"panel_social_pending"] boolValue];
        BOOL peer = [state[@"panel_peer_consented"] boolValue];
        self.optedIn = [state[@"panel_consented"] boolValue];
        UIButtonConfiguration *consentStyle = self.consent.configuration;
        consentStyle.title = self.optedIn ? @"Rời RP" : @"Tham gia RP";
        self.consent.configuration = consentStyle;
        self.consent.enabled = ready && !busy;
        self.greet.enabled = self.documents.enabled = ready && !busy && self.optedIn && peer;
        NSString *status;
        NSString *result = state[@"result"];
        if (account && expired) status = @"Hồ sơ đã hết hạn. Hãy cập nhật hồ sơ RP.";
        else if (account && !active) {
            if (authBusy) status = @"Đang xác thực tài khoản…";
            else if ([result isEqual:@"account_denied"]) status = @"Server chưa chấp nhận. Kiểm tra tên, mật khẩu hoặc tài khoản đã có.";
            else if ([result isEqual:@"signed_out"]) status = @"Bạn đã đăng xuất.";
            else if (result.length && ![result isEqual:@"starting"]) status = @"Mất kết nối. Kiểm tra Wi-Fi và thử đăng nhập lại.";
            else status = @"Tài khoản Police RP";
        }
        else if (!ready) status = [state[@"connected"] boolValue] ? @"Đang đồng bộ" : @"Chưa kết nối server RP";
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

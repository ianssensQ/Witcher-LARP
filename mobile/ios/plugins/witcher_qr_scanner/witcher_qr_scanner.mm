#include "witcher_qr_scanner.h"

#include "core/version.h"

#if VERSION_MAJOR == 4
#include "core/object/class_db.h"
#else
#include "core/class_db.h"
#endif

#import <AVFoundation/AVFoundation.h>
#import <UIKit/UIKit.h>

static WitcherQrScanner *witcher_qr_scanner_instance = nullptr;

static String string_from_nsstring(NSString *value) {
	String result;
	if (value) {
		result.parse_utf8([value UTF8String]);
	}
	return result;
}

@interface GodotWitcherQrScanner : NSObject <AVCaptureMetadataOutputObjectsDelegate>

@property(nonatomic, strong) AVCaptureSession *captureSession;
@property(nonatomic, strong) AVCaptureVideoPreviewLayer *previewLayer;
@property(nonatomic, strong) dispatch_queue_t sessionQueue;
@property(nonatomic, strong) dispatch_queue_t metadataQueue;
@property(nonatomic, assign) CGRect normalizedFrame;
@property(nonatomic, assign) BOOL running;
@property(nonatomic, assign) BOOL didEmitScan;

- (void)startScanNormalizedX:(CGFloat)x y:(CGFloat)y width:(CGFloat)width height:(CGFloat)height;
- (void)stopScan;
- (void)requestCameraPermission;
- (BOOL)isScanning;

@end

@implementation GodotWitcherQrScanner

- (instancetype)init {
	self = [super init];
	if (self) {
		_sessionQueue = dispatch_queue_create("org.witcherlarp.qr.session", DISPATCH_QUEUE_SERIAL);
		_metadataQueue = dispatch_queue_create("org.witcherlarp.qr.metadata", DISPATCH_QUEUE_SERIAL);
		_normalizedFrame = CGRectMake(0.0, 0.0, 1.0, 1.0);
		_running = NO;
		_didEmitScan = NO;
	}
	return self;
}

- (void)startScanNormalizedX:(CGFloat)x y:(CGFloat)y width:(CGFloat)width height:(CGFloat)height {
	self.normalizedFrame = CGRectMake(
			MAX(0.0, MIN(1.0, x)),
			MAX(0.0, MIN(1.0, y)),
			MAX(0.05, MIN(1.0, width)),
			MAX(0.05, MIN(1.0, height)));
	self.didEmitScan = NO;

	AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
	if (status == AVAuthorizationStatusAuthorized) {
		[self startAuthorizedScan];
		return;
	}
	if (status == AVAuthorizationStatusNotDetermined) {
		[AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted) {
			dispatch_async(dispatch_get_main_queue(), ^{
				[self emitPermissionChanged:granted];
				if (granted) {
					[self startAuthorizedScan];
				} else {
					[self emitScannerError:@"camera_permission_denied"];
				}
			});
		}];
		return;
	}

	[self emitPermissionChanged:NO];
	[self emitScannerError:@"camera_permission_denied"];
}

- (void)startAuthorizedScan {
	dispatch_async(dispatch_get_main_queue(), ^{
		[self stopScan];

		UIViewController *rootController = [[UIApplication sharedApplication] delegate].window.rootViewController;
		UIView *rootView = rootController.view;
		if (!rootView) {
			[self emitScannerError:@"camera_root_view_missing"];
			return;
		}

		AVCaptureDevice *device = nil;
		if (@available(iOS 10.0, *)) {
			device = [AVCaptureDevice defaultDeviceWithDeviceType:AVCaptureDeviceTypeBuiltInWideAngleCamera
													   mediaType:AVMediaTypeVideo
														position:AVCaptureDevicePositionBack];
		}
		if (!device) {
			device = [AVCaptureDevice defaultDeviceWithMediaType:AVMediaTypeVideo];
		}
		if (!device) {
			[self emitScannerError:@"camera_device_missing"];
			return;
		}

		NSError *inputError = nil;
		AVCaptureDeviceInput *input = [AVCaptureDeviceInput deviceInputWithDevice:device error:&inputError];
		if (!input || inputError) {
			[self emitScannerError:@"camera_input_failed"];
			return;
		}

		AVCaptureSession *session = [[AVCaptureSession alloc] init];
		session.sessionPreset = AVCaptureSessionPresetHigh;
		if ([session canAddInput:input]) {
			[session addInput:input];
		} else {
			[self emitScannerError:@"camera_input_rejected"];
			return;
		}

		AVCaptureMetadataOutput *metadataOutput = [[AVCaptureMetadataOutput alloc] init];
		if ([session canAddOutput:metadataOutput]) {
			[session addOutput:metadataOutput];
			[metadataOutput setMetadataObjectsDelegate:self queue:self.metadataQueue];
			if ([metadataOutput.availableMetadataObjectTypes containsObject:AVMetadataObjectTypeQRCode]) {
				metadataOutput.metadataObjectTypes = @[ AVMetadataObjectTypeQRCode ];
			} else {
				[self emitScannerError:@"qr_metadata_not_available"];
				return;
			}
		} else {
			[self emitScannerError:@"metadata_output_rejected"];
			return;
		}

		CGRect bounds = rootView.bounds;
		CGRect frame = CGRectMake(
				CGRectGetWidth(bounds) * self.normalizedFrame.origin.x,
				CGRectGetHeight(bounds) * self.normalizedFrame.origin.y,
				CGRectGetWidth(bounds) * self.normalizedFrame.size.width,
				CGRectGetHeight(bounds) * self.normalizedFrame.size.height);

		AVCaptureVideoPreviewLayer *previewLayer = [AVCaptureVideoPreviewLayer layerWithSession:session];
		previewLayer.videoGravity = AVLayerVideoGravityResizeAspectFill;
		previewLayer.frame = frame;
		previewLayer.masksToBounds = YES;
		[rootView.layer addSublayer:previewLayer];

		self.captureSession = session;
		self.previewLayer = previewLayer;
		self.running = YES;
		[self emitPermissionChanged:YES];

		dispatch_async(self.sessionQueue, ^{
			[self.captureSession startRunning];
		});
	});
}

- (void)stopScan {
	AVCaptureSession *session = self.captureSession;
	AVCaptureVideoPreviewLayer *layer = self.previewLayer;
	self.captureSession = nil;
	self.previewLayer = nil;
	self.running = NO;

	if (layer) {
		dispatch_async(dispatch_get_main_queue(), ^{
			[layer removeFromSuperlayer];
		});
	}

	if (session) {
		dispatch_async(self.sessionQueue, ^{
			[session stopRunning];
		});
	}
}

- (void)requestCameraPermission {
	AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
	if (status == AVAuthorizationStatusAuthorized) {
		[self emitPermissionChanged:YES];
		return;
	}
	if (status == AVAuthorizationStatusNotDetermined) {
		[AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted) {
			dispatch_async(dispatch_get_main_queue(), ^{
				[self emitPermissionChanged:granted];
			});
		}];
		return;
	}
	[self emitPermissionChanged:NO];
}

- (BOOL)isScanning {
	return self.running;
}

- (void)captureOutput:(AVCaptureOutput *)output
		didOutputMetadataObjects:(NSArray<__kindof AVMetadataObject *> *)metadataObjects
		fromConnection:(AVCaptureConnection *)connection {
	if (self.didEmitScan) {
		return;
	}

	for (AVMetadataObject *metadataObject in metadataObjects) {
		if (![metadataObject.type isEqualToString:AVMetadataObjectTypeQRCode]) {
			continue;
		}
		AVMetadataMachineReadableCodeObject *codeObject = (AVMetadataMachineReadableCodeObject *)metadataObject;
		NSString *value = codeObject.stringValue;
		if (!value || value.length == 0) {
			continue;
		}

		self.didEmitScan = YES;
		dispatch_async(dispatch_get_main_queue(), ^{
			[self stopScan];
			WitcherQrScanner *singleton = WitcherQrScanner::get_singleton();
			if (singleton) {
				singleton->on_qr_scanned(string_from_nsstring(value));
			}
		});
		return;
	}
}

- (void)emitScannerError:(NSString *)message {
	WitcherQrScanner *singleton = WitcherQrScanner::get_singleton();
	if (singleton) {
		singleton->on_scanner_error(string_from_nsstring(message));
	}
}

- (void)emitPermissionChanged:(BOOL)allowed {
	WitcherQrScanner *singleton = WitcherQrScanner::get_singleton();
	if (singleton) {
		singleton->on_permission_changed(allowed);
	}
}

@end

WitcherQrScanner *WitcherQrScanner::get_singleton() {
	return witcher_qr_scanner_instance;
}

void WitcherQrScanner::_bind_methods() {
	ClassDB::bind_method(D_METHOD("start_scan_normalized", "x", "y", "width", "height"), &WitcherQrScanner::start_scan_normalized);
	ClassDB::bind_method(D_METHOD("stop_scan"), &WitcherQrScanner::stop_scan);
	ClassDB::bind_method(D_METHOD("request_camera_permission"), &WitcherQrScanner::request_camera_permission);
	ClassDB::bind_method(D_METHOD("is_scanning"), &WitcherQrScanner::is_scanning);

	ADD_SIGNAL(MethodInfo("qr_scanned", PropertyInfo(Variant::STRING, "text")));
	ADD_SIGNAL(MethodInfo("scanner_error", PropertyInfo(Variant::STRING, "message")));
	ADD_SIGNAL(MethodInfo("permission_changed", PropertyInfo(Variant::BOOL, "allowed")));
}

void WitcherQrScanner::start_scan_normalized(float p_x, float p_y, float p_width, float p_height) {
	[scanner startScanNormalizedX:p_x y:p_y width:p_width height:p_height];
}

void WitcherQrScanner::stop_scan() {
	[scanner stopScan];
}

void WitcherQrScanner::request_camera_permission() {
	[scanner requestCameraPermission];
}

bool WitcherQrScanner::is_scanning() const {
	return [scanner isScanning];
}

void WitcherQrScanner::on_qr_scanned(const String &p_text) {
	emit_signal("qr_scanned", p_text);
}

void WitcherQrScanner::on_scanner_error(const String &p_message) {
	emit_signal("scanner_error", p_message);
}

void WitcherQrScanner::on_permission_changed(bool p_allowed) {
	emit_signal("permission_changed", p_allowed);
}

WitcherQrScanner::WitcherQrScanner() {
	witcher_qr_scanner_instance = this;
	scanner = [[GodotWitcherQrScanner alloc] init];
}

WitcherQrScanner::~WitcherQrScanner() {
	[scanner stopScan];
	scanner = nil;
	witcher_qr_scanner_instance = nullptr;
}

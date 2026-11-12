#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
int main(void) {
	@autoreleasepool {
		CFArrayRef a = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID);
		if (!a) { printf("no window list (no WindowServer connection?)\n"); return 1; }
		printf("%ld windows\n", (long)CFArrayGetCount(a));
		for (NSDictionary *w in (__bridge NSArray *)a) {
			NSDictionary *b = w[(id)kCGWindowBounds];
			printf("%5d %-22s layer %4d alpha %.2f onscreen %d %4.0fx%-4.0f at %4.0f,%-4.0f '%s'\n",
			    [w[(id)kCGWindowNumber] intValue], [w[(id)kCGWindowOwnerName] UTF8String] ?: "?",
			    [w[(id)kCGWindowLayer] intValue], [w[(id)kCGWindowAlpha] doubleValue], [w[(id)kCGWindowIsOnscreen] intValue],
			    [b[@"Width"] doubleValue], [b[@"Height"] doubleValue], [b[@"X"] doubleValue], [b[@"Y"] doubleValue],
			    [w[(id)kCGWindowName] UTF8String] ?: "");
		}
		CFRelease(a);
	}
	return 0;
}

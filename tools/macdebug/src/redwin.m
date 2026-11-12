#import <AppKit/AppKit.h>
int main(int argc, char **argv) {
	@autoreleasepool {
		[NSApplication sharedApplication];
		[NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
		NSRect r = NSMakeRect(60, 300, 300, 400);
		NSWindow *w = [[NSWindow alloc] initWithContentRect:r styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
		    backing:NSBackingStoreBuffered defer:NO];
		w.title = @"Hello from macOS 27 on Mi 8 Pro";
		w.backgroundColor = [NSColor colorWithCalibratedRed:0.9 green:0.15 blue:0.1 alpha:1];
		NSTextField *t = [NSTextField labelWithString:@"macOS 27.2\nXiaomi MI 8 Pro\nSDM845"];
		t.font = [NSFont systemFontOfSize:28 weight:NSFontWeightBold];
		t.textColor = NSColor.whiteColor;
		t.frame = NSMakeRect(20, 150, 260, 120);
		[w.contentView addSubview:t];
		w.level = NSScreenSaverWindowLevel;
		w.canBecomeVisibleWithoutLogin = YES;
		[w makeKeyAndOrderFront:nil];
		[NSApp activateIgnoringOtherApps:YES];
		fprintf(stderr, "redwin: window %ld on screen %d\n", (long)w.windowNumber, (int)w.isOnActiveSpace);
		[NSTimer scheduledTimerWithTimeInterval:120 repeats:NO block:^(NSTimer *x) { exit(0); }];
		[NSApp run];
	}
	return 0;
}

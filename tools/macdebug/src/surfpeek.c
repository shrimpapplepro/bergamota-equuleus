#include <IOSurface/IOSurfaceRef.h>
#include <stdio.h>
#include <stdlib.h>
static double nz(const uint8_t *p, size_t bpr, size_t w, size_t h, uint32_t *sample) {
	size_t n = 0, tot = 0;
	for (size_t y = 0; y < h; y += 8) for (size_t x = 0; x < w; x += 8) {
		const uint8_t *q = p + y * bpr + x * 4;
		tot++; if (q[0] | q[1] | q[2]) { n++; if (sample && !*sample) *sample = *(const uint32_t *)q; }
	}
	return tot ? 100.0 * n / tot : 0;
}
int main(int argc, char **argv) {
	int lo = argc > 1 ? atoi(argv[1]) : 1, hi = argc > 2 ? atoi(argv[2]) : 64;
	for (int id = lo; id <= hi; id++) {
		IOSurfaceRef s = IOSurfaceLookup((IOSurfaceID)id);
		if (!s) continue;
		size_t w = IOSurfaceGetWidth(s), h = IOSurfaceGetHeight(s), bpr = IOSurfaceGetBytesPerRow(s), pc = IOSurfaceGetPlaneCount(s);
		IOSurfaceLock(s, kIOSurfaceLockReadOnly, NULL);
		uint8_t *base = IOSurfaceGetBaseAddress(s);
		uint8_t *p0 = pc ? IOSurfaceGetBaseAddressOfPlane(s, 0) : base;
		size_t bpr0 = pc ? IOSurfaceGetBytesPerRowOfPlane(s, 0) : bpr;
		uint32_t sb = 0, sp = 0;
		double nb = nz(base, bpr, w, h, &sb), np = (p0 != base) ? nz(p0, bpr0, w, h, &sp) : nb;
		printf("id %3d %4zux%-4zu fmt %08x planes %zu bpr %zu alloc %zu plane0 off %ld bpr0 %zu | base %.1f%% nonblack (first %08x) plane0 %.1f%% (first %08x)\n",
		    id, w, h, IOSurfaceGetPixelFormat(s), pc, bpr, IOSurfaceGetAllocSize(s), (long)(p0 - base), bpr0, nb, sb, np, sp);
		IOSurfaceUnlock(s, kIOSurfaceLockReadOnly, NULL);
		CFRelease(s);
	}
	return 0;
}

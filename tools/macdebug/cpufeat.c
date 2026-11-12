#include <stdio.h>
#include <stdint.h>
#include <sys/sysctl.h>
#include <signal.h>
#include <setjmp.h>
#include <string.h>
static sigjmp_buf jb;
static void onill(int s) { (void)s; siglongjmp(jb, 1); }
static int opt(const char *n) { int v = -1; size_t l = sizeof(v); if (sysctlbyname(n, &v, &l, NULL, 0)) return -2; return v; }
int main(void) {
	const char *names[] = {"hw.optional.arm.FEAT_DotProd", "hw.optional.arm.FEAT_FHM", "hw.optional.arm.FEAT_I8MM",
	    "hw.optional.arm.FEAT_BF16", "hw.optional.arm.FEAT_SHA3", "hw.optional.arm.FEAT_FP16", "hw.optional.arm.FEAT_LSE",
	    "hw.optional.arm.FEAT_RDM", "hw.optional.arm.FEAT_LRCPC", "hw.optional.arm.FEAT_LRCPC2", "hw.optional.arm.FEAT_JSCVT",
	    "hw.optional.arm.FEAT_FCMA", "hw.optional.arm.FEAT_DPB", "hw.optional.arm.FEAT_FlagM", "hw.optional.arm.FEAT_SB", 0};
	for (int i = 0; names[i]; i++) printf("%s = %d\n", names[i], opt(names[i]));
	signal(SIGILL, onill);
	for (int i = 0; i < 200; i++) {
		if (sigsetjmp(jb, 1)) { printf("UDOT: SIGILL on try %d\n", i); return 1; }
		__asm__ volatile(".inst 0x6e819440" ::: "v0");   /* udot v0.4s, v2.16b, v1.16b */
	}
	printf("UDOT: ok x200\n");
	return 0;
}

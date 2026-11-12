/* DYLD_INSERT_LIBRARIES=exitbt.dylib: print a symbolized backtrace to stderr (and /dev/console) when the process
 * calls exit()/_exit() with a nonzero status or abort(). */
#include <dlfcn.h>
#include <execinfo.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define DYLD_INTERPOSE(_replacement, _replacee) \
	__attribute__((used)) static struct { const void *replacement; const void *replacee; } _interpose_##_replacee \
	__attribute__((section("__DATA,__interpose"))) = { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };
static void bt(const char *why, int status) {
	void *f[64]; int n = backtrace(f, 64);
	int fds[2] = {2, open("/dev/console", O_WRONLY)};
	for (int k = 0; k < 2; k++) {
		if (fds[k] < 0) continue;
		dprintf(fds[k], "EXITBT %s(%d) in pid %d:\n", why, status, getpid());
		for (int i = 1; i < n; i++) {
			Dl_info d; memset(&d, 0, sizeof(d));
			dladdr(f[i], &d);
			const char *img = d.dli_fname ? strrchr(d.dli_fname, '/') : NULL;
			dprintf(fds[k], "EXITBT  #%d %p %s+0x%lx %s+0x%lx\n", i, f[i], img ? img + 1 : "?",
			    d.dli_fbase ? (unsigned long)((char *)f[i] - (char *)d.dli_fbase) : 0UL, d.dli_sname ? d.dli_sname : "?",
			    d.dli_saddr ? (unsigned long)((char *)f[i] - (char *)d.dli_saddr) : 0UL);
		}
	}
}
static void my_exit(int s) { if (s) bt("exit", s); exit(s); }
static void my__exit(int s) { if (s) bt("_exit", s); _exit(s); }
static void my_abort(void) { bt("abort", 0); abort(); }
DYLD_INTERPOSE(my_exit, exit)
DYLD_INTERPOSE(my__exit, _exit)
DYLD_INTERPOSE(my_abort, abort)
__attribute__((constructor)) static void hello(void) { dprintf(2, "EXITBT loaded in pid %d\n", getpid()); }

/*
 * oslogtap.dylib: readable os_log output for one process, without logd/uuidtext (on the phone `log show` only
 * prints "<compose failure [shared UUID]>": there is no uuidtext for our rewritten dyld cache).
 *
 *   DYLD_INSERT_LIBRARIES=/usr/local/lib/oslogtap.dylib  [OSLOGTAP_FILE=/var/tmp/oslog-NAME.log]
 *
 * Interposes _os_log_impl / _os_log_error_impl / _os_log_fault_impl / _os_log_debug_impl (the calls the os_log
 * macros compile to, through stubs, so interposing works). In the process the format string is a plain C string and
 * the arguments are in the os_log buffer: summary byte, count byte, then per argument a descriptor byte (type in the
 * high nibble: 0 scalar, 2 string pointer, 4 object), a size byte and the data. Formats are expanded with the
 * arguments in order (%s/%@ strings and objects, %d/%u/%x/%llu/%p scalars; other specifiers print raw); privacy
 * markers ({public}, {private}, ...) are ignored. Each line: time, pid, type, text. The original call is then made.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <os/log.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

#define DYLD_INTERPOSE(_replacement, _replacee) \
	__attribute__((used)) static struct { const void *replacement; const void *replacee; } _interpose_##_replacee \
	__attribute__((section("__DATA,__interpose"))) = { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };

extern void _os_log_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size);
extern void _os_log_error_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size);
extern void _os_log_fault_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size);
extern void _os_log_debug_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size);

static int g_fd = -1;
static pthread_once_t g_once = PTHREAD_ONCE_INIT;
static __thread int g_inside;

static void
open_out(void)
{
	const char *p = getenv("OSLOGTAP_FILE");
	char def[128];
	if (p == NULL) {
		snprintf(def, sizeof(def), "/var/tmp/oslog-%s-%d.log", getprogname(), getpid());
		p = def;
	}
	g_fd = open(p, O_WRONLY | O_CREAT | O_APPEND, 0644);
}

struct arg {
	int type;
	int size;
	const uint8_t *data;
};

static void
append_obj(char *out, size_t cap, const void *obj)
{
	if (obj == NULL) {
		strlcat(out, "(null)", cap);
		return;
	}
	CFStringRef d = CFCopyDescription((CFTypeRef)obj);
	char tmp[512] = "";
	if (d != NULL) {
		CFStringGetCString(d, tmp, sizeof(tmp), kCFStringEncodingUTF8);
		CFRelease(d);
	}
	strlcat(out, tmp, cap);
}

static void
render(char *out, size_t cap, const char *fmt, const uint8_t *buf, uint32_t size)
{
	struct arg args[32];
	int n = 0;
	if (buf != NULL && size >= 2) {
		const uint8_t *p = buf + 2, *end = buf + size;
		int count = buf[1];
		while (n < count && n < 32 && p + 2 <= end) {
			args[n].type = p[0] >> 4;
			args[n].size = p[1];
			args[n].data = p + 2;
			p += 2 + p[1];
			if (p > end) {
				break;
			}
			n++;
		}
	}
	int ai = 0;
	out[0] = 0;
	for (const char *f = fmt; *f && strlen(out) + 8 < cap; f++) {
		if (*f != '%') {
			char c[2] = {*f, 0};
			strlcat(out, c, cap);
			continue;
		}
		if (f[1] == '%') {
			strlcat(out, "%", cap);
			f++;
			continue;
		}
		const char *s = f + 1;
		if (*s == '{') {
			while (*s && *s != '}') {
				s++;
			}
			if (*s) {
				s++;
			}
		}
		while (*s && strchr("0123456789.-+# lhqjztL*", *s)) {
			s++;
		}
		char conv = *s;
		if (!conv) {
			break;
		}
		f = s;
		if (ai >= n) {
			strlcat(out, "<?>", cap);
			continue;
		}
		struct arg *a = &args[ai++];
		char tmp[64];
		uint64_t v = 0;
		if (a->size <= 8) {
			memcpy(&v, a->data, a->size);
		}
		if (conv == 's' && a->type == 2) {
			const char *str = (const char *)(uintptr_t)v;
			strlcat(out, str ? str : "(null)", cap);
		} else if (conv == '@' || a->type == 4) {
			append_obj(out, cap, (const void *)(uintptr_t)v);
		} else if (conv == 'd' || conv == 'i') {
			snprintf(tmp, sizeof(tmp), "%lld", a->size == 4 ? (long long)(int32_t)v : (long long)v);
			strlcat(out, tmp, cap);
		} else if (conv == 'u') {
			snprintf(tmp, sizeof(tmp), "%llu", a->size == 4 ? (unsigned long long)(uint32_t)v : (unsigned long long)v);
			strlcat(out, tmp, cap);
		} else if (conv == 'x' || conv == 'X' || conv == 'p') {
			snprintf(tmp, sizeof(tmp), "0x%llx", (unsigned long long)v);
			strlcat(out, tmp, cap);
		} else if (conv == 'f' || conv == 'g' || conv == 'e') {
			double dv;
			memcpy(&dv, &v, sizeof(dv));
			snprintf(tmp, sizeof(tmp), "%g", dv);
			strlcat(out, tmp, cap);
		} else {
			snprintf(tmp, sizeof(tmp), "<%c:0x%llx>", conv, (unsigned long long)v);
			strlcat(out, tmp, cap);
		}
	}
}

static void
tap(const char *kind, const char *format, uint8_t *buf, uint32_t size)
{
	if (g_inside) {
		return;
	}
	g_inside = 1;
	pthread_once(&g_once, open_out);
	if (g_fd >= 0 && format != NULL) {
		char text[2048];
		render(text, sizeof(text), format, buf, size);
		struct timeval tv;
		gettimeofday(&tv, NULL);
		dprintf(g_fd, "%ld.%03d %d %s %s\n", (long)tv.tv_sec, (int)(tv.tv_usec / 1000), getpid(), kind, text);
	}
	g_inside = 0;
}

static void
my_os_log_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size)
{
	tap(type == OS_LOG_TYPE_INFO ? "info" : type == OS_LOG_TYPE_DEBUG ? "debug" : type == OS_LOG_TYPE_ERROR ? "ERROR" :
	    type == OS_LOG_TYPE_FAULT ? "FAULT" : "default", format, buf, size);
	_os_log_impl(dso, log, type, format, buf, size);
}

static void
my_os_log_error_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size)
{
	tap("ERROR", format, buf, size);
	_os_log_error_impl(dso, log, type, format, buf, size);
}

static void
my_os_log_fault_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size)
{
	tap("FAULT", format, buf, size);
	_os_log_fault_impl(dso, log, type, format, buf, size);
}

static void
my_os_log_debug_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size)
{
	tap("debug", format, buf, size);
	_os_log_debug_impl(dso, log, type, format, buf, size);
}

DYLD_INTERPOSE(my_os_log_impl, _os_log_impl)
DYLD_INTERPOSE(my_os_log_error_impl, _os_log_error_impl)
DYLD_INTERPOSE(my_os_log_fault_impl, _os_log_fault_impl)
DYLD_INTERPOSE(my_os_log_debug_impl, _os_log_debug_impl)

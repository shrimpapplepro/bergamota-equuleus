/*
 * sweetclock: the iOS wall clock across dual boots (kernel patch 0262).
 *
 * The kernel keeps the offset between the PM8998 RTC and Unix time in the RTC alarm's data registers (patch
 * 0245). LineageOS uses that alarm too, so after a LineageOS session iOS starts in 1970. This helper keeps a
 * second copy of the offset on the iOS volume:
 *
 *   sweetclock          clock before 2025: set it to raw RTC + stored offset (settimeofday; the kernel then
 *                       stores the offset in the RTC again). Clock valid: store the current offset if it moved
 *                       by more than 2 s (the user set the time, or timed did).
 *   sweetclock show     print raw RTC, stored offset, current time; changes nothing
 *
 * Run by the launchd job org.sweet.sweetclock at load and every 10 minutes, as root.
 * Raw RTC: sysctl kern.sweet_rtc_raw. Store: /private/var/db/sweetclock ("offset N\n").
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define STORE     "/private/var/db/sweetclock"
#define STORE_TMP "/private/var/db/sweetclock.new"
#define T_MIN     1735689600LL /* 2025-01-01: older is not a real wall clock (as the kernel) */
#define T_MAX     4102444800LL /* 2100-01-01 */

static void
say(const char *fmt, long long a, long long b, long long c)
{
	char when[32] = "";
	time_t now = time(NULL);
	struct tm tm;
	if (gmtime_r(&now, &tm)) {
		strftime(when, sizeof(when), "%Y-%m-%dT%H:%M:%SZ", &tm);
	}
	fprintf(stderr, "%s sweetclock: ", when);
	fprintf(stderr, fmt, a, b, c);
	fputc('\n', stderr);
}

static int
raw_rtc(long long *raw)
{
	uint64_t v = 0;
	size_t n = sizeof(v);
	if (sysctlbyname("kern.sweet_rtc_raw", &v, &n, NULL, 0) != 0 || n != sizeof(v)) {
		return -1;
	}
	*raw = (long long)v;
	return 0;
}

static int
load(long long *off)
{
	FILE *f = fopen(STORE, "r");
	char tag[16];
	int ok;
	if (!f) {
		return -1;
	}
	ok = fscanf(f, "%15s %lld", tag, off) == 2 && strcmp(tag, "offset") == 0;
	fclose(f);
	return ok ? 0 : -1;
}

static int
store(long long off)
{
	char buf[64];
	int n = snprintf(buf, sizeof(buf), "offset %lld\n", off);
	int fd = open(STORE_TMP, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if (fd < 0) {
		return -1;
	}
	if (write(fd, buf, (size_t)n) != n || fsync(fd) != 0) {
		close(fd);
		unlink(STORE_TMP);
		return -1;
	}
	close(fd);
	return rename(STORE_TMP, STORE);
}

int
main(int argc, char **argv)
{
	long long raw, off = 0, now = (long long)time(NULL);
	int have = 0, tries = 0;
	/* Early in boot the RTC can be unreadable for a while (ENXIO): retry for 2 minutes while the clock is not set. */
	while (raw_rtc(&raw) != 0) {
		int e = errno;
		if (e == ENOENT) {
			say("no kern.sweet_rtc_raw: kernel without patch 0262", 0, 0, 0);
			return 1;
		}
		now = (long long)time(NULL);
		if (++tries >= 24 || (now >= T_MIN && now < T_MAX)) {
			say("RTC not readable (errno %lld) after %lld tries", e, tries, 0);
			return 1;
		}
		sleep(5);
	}
	if (tries) {
		say("RTC readable after %lld tries", tries, 0, 0);
	}
	now = (long long)time(NULL);
	have = load(&off) == 0;
	if (argc > 1 && strcmp(argv[1], "show") == 0) {
		printf("raw %lld stored-offset %s%lld now %lld (%s)\n", raw, have ? "" : "none ", have ? off : 0, now,
		    now >= T_MIN && now < T_MAX ? "valid" : "not set");
		return 0;
	}
	if (now < T_MIN || now >= T_MAX) {
		long long t = raw + off;
		if (!have || t < T_MIN || t >= T_MAX) {
			say("clock not set (now %lld) and no usable stored offset (have %lld, raw %lld)", now, have, raw);
			return 1;
		}
		struct timeval tv = { .tv_sec = (time_t)t, .tv_usec = 0 };
		if (settimeofday(&tv, NULL) != 0) {
			say("settimeofday %lld failed errno %lld (raw %lld)", t, errno, raw);
			return 1;
		}
		say("clock restored to %lld (raw %lld + stored offset %lld)", t, raw, off);
		return 0;
	}
	long long want = now - raw;
	if (have && llabs(want - off) <= 2) {
		return 0;
	}
	if (store(want) != 0) {
		say("storing offset %lld failed errno %lld", want, errno, 0);
		return 1;
	}
	say("offset stored: %lld (was %lld, raw %lld)", want, have ? off : -1, raw);
	return 0;
}

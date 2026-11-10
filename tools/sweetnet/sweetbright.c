/*
 * sweetbright: the iOS brightness slider to the Mi 8 Pro AMOLED (kernel patch 0263, sysctl kern.sweet_fb_brightness).
 *
 * Without a backlight service CoreBrightness has no hardware to drive, but backboardd still tracks the user's level
 * (BKSDisplayBrightnessGetCurrent, 0..1). This polls it and hands it to the kernel, which sends DCS 0x51.
 *
 *   sweetbright get            print backboardd's level and the kernel's request / applied values
 *   sweetbright set N          kernel request N (2..1023), for testing
 *   sweetbright watch          print backboardd's level when it changes (Ctrl-C), changes nothing
 *   sweetbright daemon [G]     follow the slider: panel = 8 + 1015 * level^G (G default 2.0), polled every 100 ms;
 *                              the floor of 8 keeps the panel readable at the bottom of the slider
 *
 * Run as root (the sysctl is root-writable). Job org.sweet.sweetbright runs `daemon`.
 */
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysctl.h>
#include <time.h>
#include <unistd.h>

typedef float (*get_fn)(void);

static get_fn
bks_get(void)
{
	void *h = dlopen("/System/Library/PrivateFrameworks/BackBoardServices.framework/BackBoardServices", RTLD_NOW);
	if (!h) {
		fprintf(stderr, "sweetbright: BackBoardServices: %s\n", dlerror());
		return NULL;
	}
	get_fn f = (get_fn)dlsym(h, "BKSDisplayBrightnessGetCurrent");
	if (!f) {
		fprintf(stderr, "sweetbright: no BKSDisplayBrightnessGetCurrent\n");
	}
	return f;
}

static int
kget(const char *name)
{
	int v = -9;
	size_t n = sizeof(v);
	if (sysctlbyname(name, &v, &n, NULL, 0) != 0) {
		return -9;
	}
	return v;
}

static int
kset(int v)
{
	return sysctlbyname("kern.sweet_fb_brightness", NULL, NULL, &v, sizeof(v));
}

static void
stamp(void)
{
	char when[32] = "";
	time_t now = time(NULL);
	struct tm tm;
	if (localtime_r(&now, &tm)) {
		strftime(when, sizeof(when), "%H:%M:%S", &tm);
	}
	fprintf(stderr, "%s sweetbright: ", when);
}

int
main(int argc, char **argv)
{
	const char *mode = argc > 1 ? argv[1] : "get";
	if (!strcmp(mode, "set") && argc > 2) {
		int v = atoi(argv[2]);
		if (kset(v) != 0) {
			perror("sweetbright: kern.sweet_fb_brightness");
			return 1;
		}
		usleep(200000);
		printf("request %d applied %d\n", kget("kern.sweet_fb_brightness"), kget("kern.sweet_fb_brightness_applied"));
		return 0;
	}
	get_fn get = bks_get();
	if (!strcmp(mode, "get")) {
		printf("backboardd %.4f request %d applied %d\n", get ? get() : -1.0f, kget("kern.sweet_fb_brightness"),
		    kget("kern.sweet_fb_brightness_applied"));
		return get ? 0 : 1;
	}
	if (!get) {
		return 1;
	}
	if (!strcmp(mode, "watch")) {
		float last = -2.0f;
		for (;;) {
			float v = get();
			if (fabsf(v - last) > 0.0005f) {
				printf("%.4f\n", v);
				fflush(stdout);
				last = v;
			}
			usleep(100000);
		}
	}
	if (!strcmp(mode, "daemon")) {
		double g = argc > 2 ? atof(argv[2]) : 2.0;
		if (g < 0.5 || g > 4.0) {
			g = 2.0;
		}
		if (kget("kern.sweet_fb_brightness") == -9) {
			stamp();
			fprintf(stderr, "no kern.sweet_fb_brightness: kernel without patch 0263; nothing to do\n");
			return 0;       /* a clean exit: the job (KeepAlive SuccessfulExit false) does not restart it */
		}
		float last = -2.0f;
		int sent = -1;
		stamp();
		fprintf(stderr, "following backboardd's brightness, gamma %.2f\n", g);
		for (;;) {
			float v = get();
			if (v >= 0.0f && v <= 1.0f && fabsf(v - last) > 0.0005f) {
				int lvl = 8 + (int)lround(1015.0 * pow((double)v, g));
				if (lvl != sent && kset(lvl) == 0) {
					sent = lvl;
				}
				last = v;
			}
			usleep(100000);
		}
	}
	fprintf(stderr, "usage: sweetbright get | set N | watch | daemon [gamma]\n");
	return 2;
}

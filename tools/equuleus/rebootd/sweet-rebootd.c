/*
 * sweet-rebootd: remote reboot for the Mi 8 Pro under macOS/iOS, for when nobody can hold the buttons.
 *
 * Listens on TCP 5141. A client sends one line:
 *   "ping"                                   -> "pong" (health check)
 *   "sweet-reboot normal|fastboot|recovery"  -> "ok", then sync() and reboot(RB_AUTOBOOT) into that mode
 *                                               (kern.sweet_reboot_mode, kernel patch 0137; normal = LineageOS)
 *
 * Deliberately no shell, no getpwuid/getlogin, no launchd/XPC: a crash-looping opendirectoryd makes every user
 * lookup block (SSH logins, /bin/sh, /sbin/reboot) and this must still work then. reboot(2) goes through
 * reboot_kernel(): sync, process shutdown, unmount, then the board's reset.
 *
 * Build: tools/equuleus/rebootd/build.sh; run as a launchd job (KeepAlive) or `launchctl submit`.
 */
#include <errno.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/reboot.h>
#include <sys/socket.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <unistd.h>

#define PORT 5141

static void
say(int fd, const char *s)
{
	(void)write(fd, s, strlen(s));
}

int
main(void)
{
	signal(SIGPIPE, SIG_IGN);
	int s = socket(AF_INET, SOCK_STREAM, 0);
	if (s < 0) {
		perror("socket");
		return 1;
	}
	int one = 1;
	setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
	struct sockaddr_in a;
	memset(&a, 0, sizeof(a));
	a.sin_len = sizeof(a);
	a.sin_family = AF_INET;
	a.sin_port = htons(PORT);
	a.sin_addr.s_addr = htonl(INADDR_ANY);
	if (bind(s, (struct sockaddr *)&a, sizeof(a)) != 0 || listen(s, 4) != 0) {
		perror("bind/listen");
		return 1;
	}
	fprintf(stderr, "sweet-rebootd: listening on %d\n", PORT);
	for (;;) {
		int c = accept(s, NULL, NULL);
		if (c < 0) {
			if (errno == EINTR) {
				continue;
			}
			sleep(1);
			continue;
		}
		struct timeval tv = {5, 0};
		setsockopt(c, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
		char buf[96];
		ssize_t n = read(c, buf, sizeof(buf) - 1);
		if (n <= 0) {
			close(c);
			continue;
		}
		buf[n] = 0;
		buf[strcspn(buf, "\r\n")] = 0;
		if (strcmp(buf, "ping") == 0) {
			say(c, "pong\n");
			close(c);
			continue;
		}
		const char *mode = NULL;
		if (strcmp(buf, "sweet-reboot normal") == 0) {
			mode = "normal";
		} else if (strcmp(buf, "sweet-reboot fastboot") == 0) {
			mode = "bootloader";
		} else if (strcmp(buf, "sweet-reboot recovery") == 0) {
			mode = "recovery";
		}
		if (mode == NULL) {
			say(c, "?\n");
			close(c);
			continue;
		}
		int r = sysctlbyname("kern.sweet_reboot_mode", NULL, NULL, (void *)mode, strlen(mode));
		char msg[80];
		snprintf(msg, sizeof(msg), "ok %s (mode sysctl %d)\n", mode, r);
		say(c, msg);
		close(c);
		fprintf(stderr, "sweet-rebootd: reboot to %s requested\n", mode);
		sync();
		reboot(RB_AUTOBOOT);
		/* reboot(2) failed: say so on the console and keep serving */
		fprintf(stderr, "sweet-rebootd: reboot() failed: %s\n", strerror(errno));
	}
}

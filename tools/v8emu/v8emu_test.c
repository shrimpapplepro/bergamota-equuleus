/*
 * Differential test of osfmk/arm64/sweet_v8emu.h (xnu patch 1212): random encodings of every emulated class run
 * once on the CPU (JIT page: instruction + ret, via v8emu_native.S) and once through the C emulator; registers,
 * NZCV and memory must match.
 *
 *   On an Apple Silicon Mac the CPU implements them: this checks the emulator against the hardware.
 *   On the phone (SDM845) every "native" run traps into the kernel emulation: this checks the kernel
 *   integration (sleh.c) against the same C code.
 *
 *   v8emu_test [ITERATIONS per class, default 100000] [SEED]
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <pthread.h>
#include <libkern/OSCacheControl.h>
#include "sweet_v8emu.h"

struct v8ctx {
	uint64_t x[16];
	uint64_t nzcv;
	uint64_t pad;
	uint8_t v[32][16];
};
_Static_assert(__builtin_offsetof(struct v8ctx, v) == 144, "layout");
extern void v8_run(struct v8ctx *ctx, const void *code);

static uint64_t rs = 0x9E3779B97F4A7C15ull;
static uint64_t
rnd(void)
{
	rs ^= rs << 13;
	rs ^= rs >> 7;
	rs ^= rs << 17;
	return rs;
}

static uint32_t *jit;

static void
run_native(uint32_t insn, struct v8ctx *c)
{
	pthread_jit_write_protect_np(0);
	jit[0] = insn;
	jit[1] = 0xD65F03C0u;           /* ret */
	pthread_jit_write_protect_np(1);
	sys_icache_invalidate(jit, 8);
	v8_run(c, jit);
}

static int
mem_load(void *ctx, uint64_t addr, unsigned size, uint64_t *val)
{
	(void)ctx;
	*val = 0;
	memcpy(val, (const void *)(uintptr_t)addr, size);
	return 0;
}

static int
mem_store(void *ctx, uint64_t addr, unsigned size, uint64_t val)
{
	(void)ctx;
	memcpy((void *)(uintptr_t)addr, &val, size);
	return 0;
}

static void
run_emu(uint32_t insn, struct v8ctx *c)
{
	struct sweet_v8_cpu cpu;
	uint64_t fault = 0;
	memset(&cpu, 0, sizeof(cpu));
	for (int r = 0; r < 16; r++) {
		cpu.x[r] = c->x[r];
	}
	cpu.nzcv = (uint32_t)c->nzcv;
	memcpy(cpu.v, c->v, sizeof(c->v));
	unsigned cls = sweet_v8_classify(insn);
	if (cls == SWEET_V8C_NONE || sweet_v8_execute(insn, cls, &cpu, mem_load, mem_store, NULL, &fault) != SWEET_V8_DONE) {
		fprintf(stderr, "emulator refused 0x%08x (class %u)\n", insn, cls);
		exit(2);
	}
	for (int r = 0; r < 16; r++) {
		c->x[r] = cpu.x[r];
	}
	c->nzcv = cpu.nzcv;
	memcpy(c->v, cpu.v, sizeof(c->v));
}

static uint8_t membuf_a[2048], membuf_b[2048];

static void
fill(struct v8ctx *c)
{
	for (int r = 0; r < 16; r++) {
		c->x[r] = rnd();
	}
	c->nzcv = (rnd() & 0xF) << 28;
	c->pad = 0;
	for (int r = 0; r < 32; r++) {
		for (int b = 0; b < 16; b += 8) {
			uint64_t w = rnd();
			memcpy(&c->v[r][b], &w, 8);
		}
	}
}

/* one random encoding of class k; for LRCPC2 also sets the base register into membuf */
static uint32_t
gen(int k, struct v8ctx *c, uint8_t *mem)
{
	uint32_t rd = rnd() & 31, rn = rnd() & 31, rm = rnd() & 31, ra = rnd() & 31;
	switch (k) {
	case 0: {       /* LRCPC2 */
		uint32_t size, opc;
		do {
			size = rnd() & 3;
			opc = rnd() & 3;
		} while ((opc == 2 && size == 3) || (opc == 3 && size >= 2));
		/* naturally aligned: an unaligned acquire/release access faults on Apple CPUs (real atomics are aligned) */
		uint32_t imm9 = (uint32_t)(rnd() & 0x1FF) & ~((1u << size) - 1);
		uint32_t base = rnd() & 15, rt = rnd() & 15;
		if ((rnd() & 15) == 0) {
			rt = 31;
		}
		if (opc == 0 && rt == base) {
			/* a store of the base register writes the buffer address, which differs between the two runs */
			rt = (base + 1) & 15;
		}
		c->x[base] = (uint64_t)(uintptr_t)(mem + 1024);
		return (size << 30) | 0x19000000u | (opc << 22) | (imm9 << 12) | (base << 5) | rt;
	}
	case 1: {       /* DotProd vector */
		uint32_t q = rnd() & 1, u = rnd() & 1;
		return 0x0E809400u | (q << 30) | (u << 29) | (rm << 16) | (rn << 5) | rd;
	}
	case 2: {       /* DotProd by element */
		uint32_t q = rnd() & 1, u = rnd() & 1, l = rnd() & 1, h = rnd() & 1;
		return 0x0F80E000u | (q << 30) | (u << 29) | (l << 21) | (rm << 16) | (h << 11) | (rn << 5) | rd;
	}
	case 3: {       /* FlagM */
		uint32_t g = rnd() % 5, x = rnd() & 15;
		if (g == 0) {
			return SWEET_V8_CFINV;
		}
		if (g == 1) {
			return SWEET_V8_AXFLAG;
		}
		if (g == 2) {
			return SWEET_V8_XAFLAG;
		}
		if (g == 3) {
			return 0xBA000400u | ((uint32_t)(rnd() & 63) << 15) | (x << 5) | (uint32_t)(rnd() & 15);
		}
		return 0x3A00080Du | ((uint32_t)(rnd() & 1) << 14) | (x << 5);
	}
	default: {      /* SHA3 */
		switch (rnd() & 3) {
		case 0: return 0xCE000000u | (rm << 16) | (ra << 10) | (rn << 5) | rd;
		case 1: return 0xCE200000u | (rm << 16) | (ra << 10) | (rn << 5) | rd;
		case 2: return 0xCE608C00u | (rm << 16) | (rn << 5) | rd;
		default: return 0xCE800000u | (rm << 16) | ((uint32_t)(rnd() & 63) << 10) | (rn << 5) | rd;
		}
	}
	}
}

int
main(int argc, char **argv)
{
	long iters = argc > 1 ? atol(argv[1]) : 100000;
	if (argc > 2) {
		rs = strtoull(argv[2], NULL, 0) | 1;
	}
	jit = mmap(NULL, 16384, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANON | MAP_JIT, -1, 0);
	if (jit == MAP_FAILED) {
		perror("mmap MAP_JIT");
		return 1;
	}
	static const char *names[] = {"LRCPC2", "DotProd vec", "DotProd elem", "FlagM", "SHA3"};
	int bad = 0;
	for (int k = 0; k < 5; k++) {
		long fails = 0;
		for (long n = 0; n < iters; n++) {
			struct v8ctx a, b;
			fill(&a);
			for (size_t j = 0; j < sizeof(membuf_a); j++) {
				membuf_a[j] = (uint8_t)rnd();
			}
			uint32_t insn = gen(k, &a, membuf_a);
			memcpy(membuf_b, membuf_a, sizeof(membuf_a));
			b = a;
			/* the emulator works on membuf_b: point the same base register there */
			for (int r = 0; r < 16; r++) {
				if (a.x[r] == (uint64_t)(uintptr_t)(membuf_a + 1024)) {
					b.x[r] = (uint64_t)(uintptr_t)(membuf_b + 1024);
				}
			}
			run_native(insn, &a);
			run_emu(insn, &b);
			int diff = 0;
			for (int r = 0; r < 16; r++) {
				uint64_t xa = a.x[r], xb = b.x[r];
				if (xb == (uint64_t)(uintptr_t)(membuf_b + 1024)) {
					xb = (uint64_t)(uintptr_t)(membuf_a + 1024);
				}
				if (xa != xb) {
					diff = 1;
					if (fails < 5) {
						printf("  x%d: cpu 0x%016llx emu 0x%016llx\n", r, (unsigned long long)xa, (unsigned long long)xb);
					}
				}
			}
			if ((a.nzcv & 0xF0000000u) != (b.nzcv & 0xF0000000u)) {
				diff = 1;
				if (fails < 5) {
					printf("  nzcv: cpu %llx emu %llx\n", (unsigned long long)a.nzcv >> 28, (unsigned long long)b.nzcv >> 28);
				}
			}
			for (int r = 0; r < 32; r++) {
				if (memcmp(a.v[r], b.v[r], 16) != 0) {
					diff = 1;
					if (fails < 5) {
						printf("  v%d differs\n", r);
					}
				}
			}
			if (memcmp(membuf_a, membuf_b, sizeof(membuf_a)) != 0) {
				diff = 1;
				if (fails < 5) {
					printf("  memory differs\n");
				}
			}
			if (diff) {
				if (fails < 5) {
					printf("FAIL %s 0x%08x\n", names[k], insn);
				}
				fails++;
			}
		}
		printf("%-13s %s (%ld/%ld failed)\n", names[k], fails ? "FAIL" : "PASS", fails, iters);
		bad |= fails != 0;
	}
	return bad;
}

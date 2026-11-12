// v8_run(struct v8ctx *ctx, const void *code): load x0-x15, NZCV and q0-q31 from ctx, call code
// (one instruction + ret), store them back. ctx layout: x[16] at 0, nzcv at 128, v[32][16] at 144.
	.text
	.globl	_v8_run
	.p2align	2
_v8_run:
	stp	x29, x30, [sp, #-16]!
	mov	x29, sp
	stp	x19, x20, [sp, #-16]!
	stp	x21, x22, [sp, #-16]!
	stp	d8, d9, [sp, #-16]!
	stp	d10, d11, [sp, #-16]!
	stp	d12, d13, [sp, #-16]!
	stp	d14, d15, [sp, #-16]!
	mov	x19, x0
	mov	x20, x1
	add	x9, x19, #144
	ldp	q0, q1, [x9, #0]
	ldp	q2, q3, [x9, #32]
	ldp	q4, q5, [x9, #64]
	ldp	q6, q7, [x9, #96]
	ldp	q8, q9, [x9, #128]
	ldp	q10, q11, [x9, #160]
	ldp	q12, q13, [x9, #192]
	ldp	q14, q15, [x9, #224]
	ldp	q16, q17, [x9, #256]
	ldp	q18, q19, [x9, #288]
	ldp	q20, q21, [x9, #320]
	ldp	q22, q23, [x9, #352]
	ldp	q24, q25, [x9, #384]
	ldp	q26, q27, [x9, #416]
	ldp	q28, q29, [x9, #448]
	ldp	q30, q31, [x9, #480]
	ldr	x9, [x19, #128]
	msr	nzcv, x9
	ldp	x0, x1, [x19, #0]
	ldp	x2, x3, [x19, #16]
	ldp	x4, x5, [x19, #32]
	ldp	x6, x7, [x19, #48]
	ldp	x8, x9, [x19, #64]
	ldp	x10, x11, [x19, #80]
	ldp	x12, x13, [x19, #96]
	ldp	x14, x15, [x19, #112]
	blr	x20
	stp	x0, x1, [x19, #0]
	stp	x2, x3, [x19, #16]
	stp	x4, x5, [x19, #32]
	stp	x6, x7, [x19, #48]
	stp	x8, x9, [x19, #64]
	stp	x10, x11, [x19, #80]
	stp	x12, x13, [x19, #96]
	stp	x14, x15, [x19, #112]
	mrs	x9, nzcv
	str	x9, [x19, #128]
	add	x9, x19, #144
	stp	q0, q1, [x9, #0]
	stp	q2, q3, [x9, #32]
	stp	q4, q5, [x9, #64]
	stp	q6, q7, [x9, #96]
	stp	q8, q9, [x9, #128]
	stp	q10, q11, [x9, #160]
	stp	q12, q13, [x9, #192]
	stp	q14, q15, [x9, #224]
	stp	q16, q17, [x9, #256]
	stp	q18, q19, [x9, #288]
	stp	q20, q21, [x9, #320]
	stp	q22, q23, [x9, #352]
	stp	q24, q25, [x9, #384]
	stp	q26, q27, [x9, #416]
	stp	q28, q29, [x9, #448]
	stp	q30, q31, [x9, #480]
	ldp	d14, d15, [sp], #16
	ldp	d12, d13, [sp], #16
	ldp	d10, d11, [sp], #16
	ldp	d8, d9, [sp], #16
	ldp	x21, x22, [sp], #16
	ldp	x19, x20, [sp], #16
	ldp	x29, x30, [sp], #16
	ret

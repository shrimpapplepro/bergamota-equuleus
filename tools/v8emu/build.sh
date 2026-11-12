#!/bin/bash
# Build the v8emu differential test (xnu patch 1212, osfmk/arm64/sweet_v8emu.h).
#   tools/v8emu/build.sh HEADER_DIR [OUTDIR]
# HEADER_DIR holds sweet_v8emu.h (a tree with the patch applied, e.g. .../osfmk/arm64).
# Runs it on this Mac (Apple Silicon executes every class natively: emulator vs hardware). The same binary on the
# phone checks the kernel emulation: ssh root@192.168.7.2 'cat > /var/root/v8emu_test' < OUT/v8emu_test
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HDR="${1:?header dir}"
OUT="${2:-$HERE/out}"
mkdir -p "$OUT"
clang -arch arm64 -mmacosx-version-min=14.0 -O1 -g -Wall -Wextra -I "$HDR" \
    "$HERE/v8emu_test.c" "$HERE/v8emu_native.S" -o "$OUT/v8emu_test"
codesign -f -s - "$OUT/v8emu_test"
"$OUT/v8emu_test" "${ITER:-200000}"

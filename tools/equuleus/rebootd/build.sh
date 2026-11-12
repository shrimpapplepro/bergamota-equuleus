#!/bin/bash
# Build sweet-rebootd (arm64 macOS, ad-hoc signed) into OUT (default: ./out).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="${1:-$HERE/out}"; mkdir -p "$OUT"
clang -arch arm64 -mmacosx-version-min=14.0 -O2 -Wall -Wextra "$HERE/sweet-rebootd.c" -o "$OUT/sweet-rebootd"
codesign -f -s - "$OUT/sweet-rebootd"

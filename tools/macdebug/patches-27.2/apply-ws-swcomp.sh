#!/bin/sh
set -e
[ "$(dd if=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 skip=38530692 count=4 2>/dev/null | od -An -tx1 | tr -d " \n")" = "ff1300f9" ] || { echo "old word at 38530692 differs"; exit 1; }
[ "$(dd if=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 skip=38530572 count=4 2>/dev/null | od -An -tx1 | tr -d " \n")" = "018095d2" ] || { echo "old word at 38530572 differs"; exit 1; }
[ "$(dd if=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 skip=38530576 count=4 2>/dev/null | od -An -tx1 | tr -d " \n")" = "6184bff2" ] || { echo "old word at 38530576 differs"; exit 1; }
[ "$(dd if=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 skip=38530580 count=4 2>/dev/null | od -An -tx1 | tr -d " \n")" = "c100c0f2" ] || { echo "old word at 38530580 differs"; exit 1; }
printf '\361\377\377\027' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 seek=38530692 conv=notrunc 2>/dev/null
printf '\001\100\231\322' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 seek=38530572 conv=notrunc 2>/dev/null
printf '\101\163\247\362' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 seek=38530576 conv=notrunc 2>/dev/null
printf '\037\040\003\325' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 seek=38530580 conv=notrunc 2>/dev/null
printf '\364\242\111\061\331\244\376\053\305\310\176\004\024\326\347\046\235\374\161' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 seek=130524866 conv=notrunc 2>/dev/null
printf '\102\013\102\341\134\040\065\122\127\161\211\334' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.01 bs=1 seek=130524886 conv=notrunc 2>/dev/null
sync; echo patched

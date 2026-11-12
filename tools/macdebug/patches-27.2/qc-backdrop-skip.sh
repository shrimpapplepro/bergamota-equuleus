#!/bin/sh
set -e
[ "$(dd if=/System/Library/dyld/dyld_shared_cache_arm64e.03 bs=1 skip=94589500 count=4 2>/dev/null | od -An -tx1 | tr -d " \n")" = "8a782036" ] || { echo "old word at 94589500 differs"; exit 1; }
printf '\052\006\040\066' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.03 bs=1 seek=94589500 conv=notrunc 2>/dev/null
printf '\367\056\240\061\010\261\074\230\305\311\224\251\221\251\153\047\157\275\366\002\032\051\066\317\341\216\243' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.03 bs=1 seek=131207810 conv=notrunc 2>/dev/null
printf '\302\175\243\324' | dd of=/System/Library/dyld/dyld_shared_cache_arm64e.03 bs=1 seek=131207838 conv=notrunc 2>/dev/null
sync; echo patched

# macdebug: tools for bringing up macOS 27 userland on the Mi 8 Pro

| File | Use |
| --- | --- |
| `dsc_sym.py CACHE_DIR ADDR...` | unslid address -> image + nearest exported symbol, ~1 s (ipsw a2s took >50 min on exFAT) |
| `dsc_around.py CACHE_DIR ADDR [N]` | disassembly of N instructions before ADDR, BL targets resolved, ADRP+ADD strings shown |
| `dsc_imgbase.py CACHE_DIR IMAGE` / `dsc_name.py CACHE_DIR IMAGE SYMBOL` | unslid image base / exported symbol address |
| `scan_ext.py CACHE_DIR` | count instructions of ARMv8.3+ extensions the SDM845 lacks in the cache's executable mappings (python3.13: numpy) |
| `exitbt.c` | `DYLD_INSERT_LIBRARIES` dylib: symbolized backtrace (with image offsets) on exit(!=0)/_exit/abort, to stderr + /dev/console. dyld honours the variable on this kernel |
| `cpufeat.c` | prints hw.optional.arm.FEAT_* and tries UDOT |
| `sweet-try` | phone-side (/usr/local/bin): bootstrap a staged daemon from LaunchDaemons.sweet-off with an automatic bootout |

Crash PCs in the kernel log: unslid = pc - slide (`CRASH ... slide 0x...`). exitbt frames: unslid = image base
(`dsc_imgbase.py`) + the printed `IMAGE+0xOFFSET`. Build dylibs/tools with
`clang -arch arm64 -mmacosx-version-min=14.0 ...` and `codesign -f -s -`; copy with `ssh root@192.168.7.2 'cat > PATH' < FILE`.
Failed syscalls of any process: `sysctl -w kern.sweet_syserr_names=NAME` (kernel 1213), lines `SWEET ERR:` in the UDP log.

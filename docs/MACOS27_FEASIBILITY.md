# macOS 27 on the Mi 8 Pro (equuleus): feasibility notes (started 2026-11-11, unfinished)

Read-only study on the Mac. Nothing was written to the phone. Tags: **[V]** verified in this session, **[U]** unverified.

## Parked before this

Installing iOS 26 on `recovery` (replacing iOS 18 image 10) is **parked, nothing written**. Candidate image:
`enxerto/out/equuleus-boot26-3-wifi.img` (sha256 51d02965..., 21,893,120 bytes). `recovery` still holds iOS 18 image 10
(`equuleus-boot-10-bright.img`, sha256 3dcecb03...). Wi-Fi ran 480 s without a drop. MobileSafari aborts at launch on
iOS 26 (SIGABRT, `abort() called`, 4 crash files at 01:26), not analysed.

## Findings

* Source: `/Volumes/DEEZNUTS/henge-ipsw/UniversalMac_27.2_26B123_Restore.ipsw` (macOS 27.2, 26B123). [V]
* **Identity to use: `VirtualMac2,1` (`vma2macosap`, chip 0xFE00).** Its manifest has no SPTM, no TXM, no SEP, no DCP, no
  GFX, no exclaves; every real Mac (M1 included) has `Ap,SecurePageTableMonitor` and `Ap,TrustedExecutionMonitor`. So the
  macOS 27 userland must run without them on the virtual Mac, the same argument as iPhone12,1 for iOS 26. [V]
* **Kernel gap:** the 27.2 kernel is `xnu-13432.41.4` (`RELEASE_ARM64_VMAPPLE`). Apple has published nothing newer than
  `xnu-12377.121.6` (26.5), which is what Heartwood builds. macOS 27 userland would run on a kernel one major release
  older. BSD syscall table: the macOS 27.0 SDK ends at 557 (`coalition_policy_get`, MAXSYSCALL 558), identical to the end
  of `syscalls.master` in 12377.121.6, so no new BSD syscalls. Mach traps, sysctls, commpage and user-client ABIs not
  compared. [V for the syscall table, U for the rest]
* **Instruction census**, macOS 27.2 `dyld_shared_cache_arm64e`, code sections only (82 files, 4115 images, 921.8 M
  words): FlagM (CFINV/RMIF/SETF) 0, FlagM2 0, FRINT32/64 0, LDAPUR/STLUR 15 (libsystem_m), FJCVTZS 2165
  (JavaScriptCore + WebCore, both copies), FCMLA/FCADD 25270 (libBLAS, libSparseBLAS), DIT 204 (corecrypto, dyld,
  MobileGestalt), SB 7, MTE 7607 (JavaScriptCore, libsystem_malloc), LDRAA/LDRAB 22, PACGA 767. This is the iOS 26 profile:
  `pacstrip.py` and patch 0141 should cover it as they are. Tool and outputs: scratchpad `mac27/census.c`,
  `census-27.2-26B123.txt` (copy them here before the scratchpad is cleaned). Cache extracted to
  `/Volumes/DEEZNUTS/mac27-study/cache/26B123__MacOS` (6.7 GB). [V]

## Phone state since 2026-11-11 (user: "Remove all the stuff on xiaomi but lineageos")

Done from rooted adb in LineageOS, no reboot, GPT not touched. [V]

* `recovery` (sda19): LineageOS Recovery restored from `backup-mi8pro-20261108/recovery-lineage.img`; the whole partition
  reads back as sha256 0171ce01... Before the write it held exactly iOS 18 image 10 (first 19,009,536 bytes = sha256
  3dcecb03..., the file `enxerto/out/equuleus-boot-10-bright.img`).
* `ios_payload` (sda22, 1 GiB), `ios_root` (sda23, 32 GiB), `ios_data` (sda24, 56.1 GiB): `blkdiscard`, then the first
  and last 16 MiB of each read back as zeros (`ios_data` was read from 71 MiB to its end: all zeros). The partition
  entries stay, as room for macOS (89 GiB in all). Android's shell does 32-bit arithmetic: compute `dd` offsets for
  partitions over 4 GiB on the Mac.
* Not touched: `boot` (LineageOS), `userdata` (sda21, 24 GiB, 745 MB used), bootloaders, modem, persist.
* Still on the Mac: both boot images and `research/ios26/ios26-root-full.img` (17 GB). The iOS 18 root image and the
  extracted iOS 18 IPSW (26 GB) were deleted on 2026-11-11 for space; `research/ios18/full` and the `BuildManifest.plist`
  stay. Both systems can be rebuilt from this repository.

## Target: macOS 27.2 or higher (user, 2026-11-11)

The user's target is macOS 27.2 or later, not 26.5, because macOS 27 has touchscreen support (for the touchscreen
MacBook Pro). The 26.5 download was stopped and removed. macOS-uke stays a reference for the userland recipes only.

### macOS 27.2 has a touchscreen input path, also in the virtual Mac kernel [V]

* Kernel `kernelcache.release.vma2` of 26B123 contains `AppleMultitouchDriver` with the personality
  `AppleMultitouchHIDService (0x0D,0x04)`: provider `IOHIDInterface`, HID usage page 0x0D (digitizer), usage 0x04
  (touch screen), `Manufacturer` = `Apple`, `MT Built-In` = true, `parser-type` 1, `parser-options` 16. A second
  personality `MTUserDevice` matches usage page 0xFF60, usage 7. So a HID device that reports itself as an Apple
  touchscreen digitizer is taken by the multitouch driver as a built-in touchscreen.
* Userland (dyld cache of 26B123): `BKHIDDirectTouchEventProcessor`, `BKDirectTouchState`,
  `WSHitTestInfoForDirectTouchPoint`, `touchScreenDigitizerSender`, `anyBuiltinTouchscreenDigitizer`,
  `userInteractedWithTouchScreen`, direct-touch gesture recognizers in MapKit. Virtualization has private
  `_VZUSBTouchScreenConfiguration` and `_VZAppleTouchScreenConfiguration` (`UsbTouchScreen`, `AvpTouchScreen`).
* Host macOS 27.3: the Touch pane of System Settings (`TouchExtension.appex`) reads the MobileGestalt key
  `DisplaySupportsTouch`. The kext `AppleEmbeddedTouchEEPROMDriver` matches `display-generic-data,rw` (real hardware).
* Not known: the exact HID report descriptor the driver expects, whether the user interface needs
  `DisplaySupportsTouch` to react to touches, and what the Virtualization touchscreen device looks like on the wire. [U]

### Reference: Leviidev/Henge (read 2026-11-11, origin/main 945c391, GPL-2.0)

A virtual Mac without a hypervisor: arm64 to arm64 JIT with a software MMU, device model after QEMU's `vmapple`
(GICv3, PL011, virtio, xHCI, Apple paravirtual GPU replayed with Metal). It boots the **stock** macOS 27.2 kernel and
userland of `VirtualMac2,1`, so the kernel gap above does not exist there. Local copy: `~/dev/Henge` (branch `shrimp`,
171 commits behind upstream), notes in `~/dev/henge-debug`.

* PAC: the guest's pointer-authentication instructions become a strip or a no-op. Same idea as `pacstrip`, done at run
  time.
* Touch: Henge has **no touchscreen device**. It presents the screen as a Magic Trackpad 2 on USB (`devices/xhci.c`,
  usage page 0x0D usage 0x05 = touch pad; tap = click). Changing that device to a touchscreen digitizer
  (0x0D/0x04, manufacturer Apple) is the cheapest test of the path above, and it can be done on the Mac (`hengevm`)
  with no phone involved.
* What it gives this project: (1) proof that the 27.2 virtual-Mac userland runs with no SPTM, TXM or SEP; (2) a test
  bench on the Mac with an EL0 syscall trace (`HV_SVC_LOG` in the local tree), to list what the 27.2 userland asks of
  the kernel and compare it with XNU 12377; (3) the `vma2` device tree; (4) the place to develop the touchscreen HID
  device.

### Two routes to macOS 27.2 on this phone [U, neither tried]

1. **Native:** the kernel this fork boots (XNU 12377.121.6 with this phone's drivers) + the 27.2 `VirtualMac2,1`
   userland rewritten with `pacstrip`. Real speed, real drivers. Risks: userland one major release newer than the
   kernel; `AppleMultitouchDriver` and the graphics stack are closed kernel extensions that would have to come from
   the 27.2 kernel cache or be replaced; the phone's touch driver must present the 0x0D/0x04 device.
2. **Henge on the phone:** port Henge's engine to run under LineageOS (or bare metal) and boot the stock 27.2 kernel.
   No kernel gap. Risks: the engine copies most guest instructions unchanged and the Snapdragon 845 (ARMv8.2) lacks
   instructions the 27.2 code uses (see the census above: at least PAC, MTE, FJCVTZS, FCMLA need handling); Henge
   assumes 16 KB host pages; its GPU backend is Metal only; speed (27.2 is already the slowest system on an
   iPhone 17 Pro).

## Reference: iOSNJBrepo/macOS-uke (read 2026-11-11)

macOS 26.5 (25F71) with the Finder desktop on the Xiaomi Pad 7 (SM7675, Adreno 732). No licence file. It is built on
CrossDarwin/macOS-ForSheng (macOS 26.5 for the Pad 6S Pro, own EL1 kernel from XNU 12377.121.6) and UniXNU (UEFI,
DarwinBoot, NativeUfs).

* **Its kernel does not fit this phone.** ForSheng builds an arm64e kernel that uses the CPU's pointer authentication
  (`platform/sheng/macos26/pac/*`: EL1 PAC ABI, user PAC lifecycle, SMP key bootstrap). Both tablets are ARMv9. The
  Snapdragon 845 is ARMv8.2 and has no PAC. [V for the patches; whether ForSheng can be built without PAC: U]
* **The kernel already on this phone is the same XNU release.** The iOS 26 boot image uses `xnu/out-12377-1203`
  (XNU 12377.121.6, the macOS 26.5 kernel source), with this phone's display, touch, UFS, USB network, Wi-Fi and the
  PAC handling. So the plan is: that kernel + a macOS 26.5 root rewritten with `pacstrip` + the userland recipes of
  macOS-uke. macOS 26.5 on a 26.5 kernel has no version gap; macOS 27 keeps the gap described above. [U until tried]
* **Recipes to reuse** (`scripts/`, `INSTALL.md`, `docs/MACOS-RETURN.md`):
  * root from the system DMG `094-56453-087.dmg` (13,071,548,416 bytes decrypted) plus the SystemOS cryptex
    `094-56679-089.dmg`; the dyld cache goes to `/System/Library/dyld`, the other cryptex files to their real paths;
  * Data, Preboot and VM volumes made by hand (`fullos-volumes.sh`, `fullos-populate.sh`, `apfs-set-volume-group.py`);
    their container is 22,735,224,832 bytes, which fits `ios_root`;
  * no Setup Assistant: `macos-skip-setup.py` (local user, `com.apple.SetupAssistant` version keys,
    `OptimizerPreviousBuild`);
  * WindowServer composites on the CPU when the Metal device has no `acceleratorPort`, so a desktop without a GPU
    driver is possible. ForSheng reached WindowServer and the Recovery language window that way;
  * kernel modules they add from the KDK: IOMobileGraphicsFamily, IOSurface, IOAVFamily, HID;
  * touch as an absolute pointer (`UkeTouchPointer`); Metal plugins need `SIP0=0x7f`.
* **GPU, later.** Their Metal is an Adreno 740-family kernel driver + a Metal plugin (metal2vulkan + Turnip). The
  Adreno 630 is a different generation (a6xx). Turnip itself ran on this GPU under Chlorophyll (NOTES.md, 2026-10-26).
* **Unknown here:** an iOS-configured kernel under a macOS userland (platform checks, macOS-only user clients); macOS on
  an HFS root as Bergamota uses, or APFS support in this kernel; kernel extensions from the KDK in this kernel.
* Host space: their guide asks for about 120 GB free. This Mac has 45 GiB internal and about 230 GiB on DEEZNUTS
  (2026-11-11, after the cleanup).
* macOS 26.5 IPSW: `https://updates.cdn-apple.com/2026SpringFCS/fullrestores/122-58869/DFB1CEEF-5619-4591-9924-E20DB2C8FED0/UniversalMac_26.5_25F71_Restore.ipsw`

## Open questions (not started)

* Stage 1, cheap and non-destructive: one macOS 27 command-line binary with macOS 27's own dyld and libSystem from the
  restore ramdisk (`141-12288-175.dmg`), rewritten with `pacstrip`, run over SSH on the running iOS 26 system
  (`tools/renegade/mkbundle.py`, as in `docs/IOS18_PORT.md`). It tests the kernel gap directly. The iOS 26 root was
  removed from the phone on 2026-11-11, so this now needs `ios26-root-full.img` written back to `ios_root` first, or a
  small macOS root of its own.
* Root: system volume `141-12228-170.dmg.aea` (11.3 GB) + cryptexes (2.4 GB + App) on one HFS volume; size against the
  31 GiB `ios_root` and what replaces which root is the user's decision.
* WindowServer without a Metal device: unknown. Chlorophyll has no macOS build (and no iOS 26 build yet).
* Input: macOS 27 has a touchscreen path (section "Target" above). First test: a 0x0D/0x04 HID touchscreen in Henge
  on the Mac. Fallback: touch as a pointer, as macOS-uke does.
* Census tool and outputs are kept in `/Volumes/DEEZNUTS/mac27-study/census/`.

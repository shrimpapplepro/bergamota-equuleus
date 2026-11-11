#!/usr/bin/env python3
"""Minimal macOS 27.2 root for the Mi 8 Pro: the 27.2 restore ramdisk as an HFSX root, for the first macOS boot.

  mkroot-mac27-mini.py RAMDISK_RAW OUT_IMG [--size 2g] [--keys DIR] [--authorized-keys FILE] [--jobs N]

RAMDISK_RAW is the unwrapped restore ramdisk of UniversalMac_27.2_26B123 (141-12288-175.dmg, `ipsw img4 im4p
extract`): macOS 27.2 launchd, dyld, ~105 flat dylibs (no shared cache), sh/ls/ps and friends. This builds:

  * an HFSX (case-sensitive, not journaled) image with the ramdisk's files and their real owners/modes
    (owner map from an owners-on mount, applied offline by hfsroot_owners.py, everything else root:wheel);
  * the restore jobs removed (restored_external, PurpleReverseProxy, diskimagesiod, kernelmanagerd, locate,
    vsdbutil, ReportCrash), syslogd kept;
  * org.sweet.dropbear (research/ssh-build/out/dropbear-mac, macOS arm64) on port 22 with the host keys from
    --keys and /var/root/.ssh/authorized_keys from --authorized-keys; toybox-mac as /usr/local/bin/toybox;
  * org.sweet.mac27.hello: one line on /dev/console (the UDP kernel log) when launchd starts jobs;
  * every Mach-O rewritten by pacstrip (no PAC on the SDM845) and re-signed ad hoc.

The kernel itself brings ue0 up as 192.168.7.2 (patch 0075), so no network job is needed. Nothing here touches the
phone: write the image to `ios_data` from LineageOS and boot a kernel with `ufsroot=ios_data`.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('mkroot_full', os.path.join(HERE, 'mkroot-full.py'))
mf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mf)
rplat = mf.rplat
log = mf.log

DROP_JOBS = ('com.apple.restored_external.plist', 'com.apple.PurpleReverseProxy.ramdisk.plist',
             'com.apple.diskimagesiod.plist', 'com.apple.diskimagesiod.ram.plist', 'com.apple.kernelmanagerd.plist',
             'com.apple.locate.plist', 'com.apple.vsdbutil.plist', 'com.apple.ReportCrash.Root.plist')

DROPBEAR = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>org.sweet.dropbear</string>
<key>ProgramArguments</key><array><string>/usr/local/bin/dropbear</string><string>-F</string><string>-E</string>
<string>-s</string><string>-p</string><string>22</string><string>-r</string>
<string>/private/etc/dropbear/dropbear_ed25519_host_key</string></array>
<key>KeepAlive</key><true/><key>RunAtLoad</key><true/><key>UserName</key><string>root</string>
<key>StandardErrorPath</key><string>/dev/console</string>
</dict></plist>
"""
HELLO = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>org.sweet.mac27.hello</string>
<key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string>
<string>echo "SWEET MAC27: macOS 27.2 launchd runs jobs, 6*7=$((6*7))"; /usr/bin/uname -a; /bin/ps -A</string></array>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>/dev/console</string><key>StandardErrorPath</key><string>/dev/console</string>
</dict></plist>
"""


def worker(path):
    return mf.macho_worker(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ramdisk')
    ap.add_argument('out')
    ap.add_argument('--size', default='2g')
    ap.add_argument('--keys', required=True, help='dir with dropbear_ed25519_host_key (+ ecdsa)')
    ap.add_argument('--authorized-keys', required=True)
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    ap.add_argument('--mnt-dir', default=None, help='where the mount points go (default research/mac27-mnt)')
    a = ap.parse_args()
    work = os.path.dirname(os.path.abspath(a.out))
    mf.W = work
    # mount points on the internal disk: hdiutil cannot mount onto a folder of an exFAT drive (the image can live there)
    mnts = a.mnt_dir or os.path.join(ROOT, 'research', 'mac27-mnt')
    rootmnt, srcmnt = os.path.join(mnts, 'root'), os.path.join(mnts, 'src')
    os.makedirs(rootmnt, exist_ok=True)
    os.makedirs(srcmnt, exist_ok=True)

    if os.path.exists(a.out):
        mf.detach_all(a.out)
        os.unlink(a.out)
    rplat.make_image(a.out, a.size)
    rplat.format_hfsx(a.out, 'macOSRoot')
    mf.attach(a.out, rootmnt, readonly=False)
    log('root image mounted at', rootmnt)

    table = {}
    dev = rplat.attach_ipsw(a.ramdisk, srcmnt, owners=True)
    n = mf.walk_owners(srcmnt, table)
    mf.detach(dev)
    log(f'owner map: {n} entries')
    dev = rplat.attach_ipsw(a.ramdisk, srcmnt, owners=False)
    rc, err = mf.copy_tree(srcmnt, rootmnt)
    mf.detach(dev)
    if rc:
        sys.exit('ditto failed: ' + err[:2000])
    for junk in ('.Spotlight-V100', '.fseventsd', '.Trashes'):
        shutil.rmtree(os.path.join(rootmnt, junk), ignore_errors=True)

    ld = os.path.join(rootmnt, 'System/Library/LaunchDaemons')
    for j in DROP_JOBS:
        p = os.path.join(ld, j)
        if os.path.exists(p):
            os.unlink(p)
            table.pop('System/Library/LaunchDaemons/' + j, None)
    for name, text in (('org.sweet.dropbear.plist', DROPBEAR), ('org.sweet.mac27.hello.plist', HELLO)):
        p = os.path.join(ld, name)
        open(p, 'w').write(text)
        os.chmod(p, 0o644)
        table['System/Library/LaunchDaemons/' + name] = (0, 0, 0o644)
    log('launch jobs:', sorted(os.listdir(ld)))

    def put(src, rel, mode):
        dst = os.path.join(rootmnt, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, mode)
        table[rel] = (0, 0, mode)
    sb = os.path.join(ROOT, 'research/ssh-build/out')
    put(os.path.join(sb, 'dropbear-mac'), 'usr/local/bin/dropbear', 0o755)
    put(os.path.join(sb, 'toybox-mac'), 'usr/local/bin/toybox', 0o755)
    for d in ('usr/local', 'usr/local/bin', 'private/etc/dropbear'):
        table[d] = (0, 0, 0o755)
    for k in ('dropbear_ed25519_host_key', 'dropbear_ecdsa_host_key'):
        if os.path.exists(os.path.join(a.keys, k)):
            put(os.path.join(a.keys, k), 'private/etc/dropbear/' + k, 0o600)
    put(a.authorized_keys, 'private/var/root/.ssh/authorized_keys', 0o600)
    table['private/var/root'] = (0, 0, 0o755)
    table['private/var/root/.ssh'] = (0, 0, 0o700)
    os.chmod(os.path.join(rootmnt, 'private/var/root/.ssh'), 0o700)
    for d in ('private/tmp', 'private/var/tmp', 'private/var/log', 'private/var/run', 'private/var/db'):
        os.makedirs(os.path.join(rootmnt, d), exist_ok=True)
        table.setdefault(d, (0, 0, 0o1777 if d.endswith('tmp') else 0o755))

    files = []
    for r, _, fs in os.walk(rootmnt):
        for f in fs:
            p = os.path.join(r, f)
            if os.path.isfile(p) and not os.path.islink(p) and os.path.getsize(p) >= 32:
                files.append(p)
    t0, stats, failed = time.time(), Counter(), []
    with Pool(a.jobs) as pool:
        for p, status, _ in pool.imap_unordered(worker, files, chunksize=8):
            if status is None:
                continue
            stats[status.split(':')[0]] += 1
            if status.startswith('FAILED'):
                failed.append((p, status))
    log(f'macho: {dict(stats)} in {time.time() - t0:.0f}s')
    if failed:
        for p, s in failed[:20]:
            log('  ', p, s)
        sys.exit('Mach-O rewrite failed')

    mf.write_map(table, os.path.join(work, 'owners.tsv'))
    subprocess.run(['sync'])
    r = rplat.detach(rootmnt)
    if r.returncode:
        sys.exit('detach failed: ' + r.stderr)
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'hfsroot_owners.py'), a.out, '--map',
                    os.path.join(work, 'owners.tsv'), '--default-root'], check=True)
    rc, text = rplat.fsck(a.out)
    log('fsck rc', rc, text.strip()[-400:])
    if rc:
        sys.exit('fsck reports errors')
    log('done:', a.out)


if __name__ == '__main__':
    main()

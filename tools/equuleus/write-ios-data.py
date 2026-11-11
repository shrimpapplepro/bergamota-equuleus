#!/usr/bin/env python3
"""Write a root image to the Mi 8 Pro's `ios_data` partition from LineageOS (rooted adb), and later only what changed.

  write-ios-data.py IMG --full        write all of IMG, verify by sha256 read-back, record IMG.phone (block hashes)
  write-ios-data.py IMG [--dry-run]   write only the 1 MiB blocks whose sha1 differs from IMG.phone, then verify

IMG.phone holds the sha1 of every 1 MiB block as last written to the phone (the builder's IMG.blocks has the same
format). It is only true until the root is booted read-write: then the changed-block mode refuses (block 0, the HFS
volume header, differs) and only --full is safe. Offsets are computed here (Android's mksh arithmetic is 32-bit). Never writes anything but
/dev/block/by-name/ios_data, and refuses an image larger than the partition minus its last 8 MiB (console ring).
"""
import hashlib
import os
import subprocess
import sys
import time

MB = 1 << 20
PART = '/dev/block/by-name/ios_data'
ADB = ['adb', '-s', '5d37c8ba']
RING = 8 * MB                       # ufslogsecs=1 console ring at the partition end


def sh(cmd):
    return subprocess.run(ADB + ['shell', cmd], capture_output=True, text=True).stdout.strip()


def block_hashes(img):
    out = []
    with open(img, 'rb') as f:
        while True:
            b = f.read(MB)
            if not b:
                return out
            out.append(hashlib.sha1(b).hexdigest())


def runs_of(idx):
    runs, start, prev = [], None, None
    for i in idx:
        if start is not None and i == prev + 1:
            prev = i
            continue
        if start is not None:
            runs.append((start, prev - start + 1))
        start = prev = i
    if start is not None:
        runs.append((start, prev - start + 1))
    return runs


def write_run(f, start, count):
    f.seek(start * MB)
    p = subprocess.Popen(ADB + ['exec-in', f'dd of={PART} ibs=65536 obs=1048576 seek={start} 2>/dev/null'],
                         stdin=subprocess.PIPE)
    left = count * MB
    while left:
        chunk = f.read(min(left, 8 * MB))
        if not chunk:
            break
        p.stdin.write(chunk)
        left -= len(chunk)
    p.stdin.close()
    return p.wait()


def main():
    img = sys.argv[1]
    full, dry = '--full' in sys.argv, '--dry-run' in sys.argv
    size = os.path.getsize(img)
    assert size % MB == 0, 'image size must be a whole number of MiB'
    if sh('id -u') != '0':
        sys.exit('adb is not root: run `adb -s 5d37c8ba root` in LineageOS first')
    psize = int(sh(f'blockdev --getsize64 {PART}') or 0)
    if not psize or size > psize - RING:
        sys.exit(f'image {size} B does not fit {PART} ({psize} B) minus the console ring')
    t0 = time.time()
    new = block_hashes(img)
    manifest = img + '.phone'
    if full:
        idx = list(range(len(new)))
    else:
        if not os.path.exists(manifest):
            sys.exit(f'no {manifest}: run with --full first')
        old = open(manifest).read().split()
        # A booted root (ufsrw=1 rootrw=1) changes the phone after the last write, and the manifest no longer says
        # what is there: writing only "changed" blocks would then mix two file system states (seen 2026-11-12). The
        # HFS volume header (block 0) is rewritten on every read-write mount, so compare that block first.
        b0 = subprocess.run(ADB + ['exec-out', f'dd if={PART} bs=1048576 count=1 2>/dev/null'], capture_output=True).stdout
        if hashlib.sha1(b0).hexdigest() != old[0]:
            sys.exit('the phone\'s ios_data changed since the last write (booted read-write?): use --full')
        idx = [i for i, h in enumerate(new) if i >= len(old) or old[i] != h]
    runs = runs_of(idx)
    print(f'{len(new)} blocks, {len(idx)} to write in {len(runs)} runs (hashing {time.time() - t0:.0f}s)', flush=True)
    if dry:
        for s, c in runs[:50]:
            print(f'  {s} MiB +{c} MiB')
        return
    t0 = time.time()
    with open(img, 'rb') as f:
        for k, (s, c) in enumerate(runs, 1):
            rc = write_run(f, s, c)
            if k % 20 == 0 or k == len(runs) or c > 512:
                print(f'  run {k}/{len(runs)}: {s} MiB +{c} MiB rc={rc} ({time.time() - t0:.0f}s)', flush=True)
            if rc:
                sys.exit(f'write failed at run {k} ({s} MiB)')
    sh('sync')
    print(f'written in {time.time() - t0:.0f}s; verifying', flush=True)
    want = hashlib.sha256()
    with open(img, 'rb') as f:
        while True:
            b = f.read(8 * MB)
            if not b:
                break
            want.update(b)
    sh('echo 3 > /proc/sys/vm/drop_caches')
    got = sh(f'dd if={PART} bs=1048576 count={size // MB} 2>/dev/null | sha256sum').split()[0]
    print('phone', got, '\nimage', want.hexdigest(), flush=True)
    if got != want.hexdigest():
        sys.exit('MISMATCH: phone content differs from the image (manifest not updated)')
    open(manifest + '.tmp', 'w').write('\n'.join(new) + '\n')
    os.replace(manifest + '.tmp', manifest)
    print('OK, manifest', manifest)


if __name__ == '__main__':
    main()

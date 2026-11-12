"""Patch instruction words in the PHONE's dyld cache file without copying it: compute the new CodeDirectory page
hashes from the phone's own signature blob and print a shell script that writes the changed bytes with dd.

  dsc_patch_remote.py LOCAL_CACHE_DIR SIGBLOB VA=OLDHEX:NEWHEX [...] > apply.sh

LOCAL_CACHE_DIR: a Mac copy whose PAGES around the patch are identical to the phone's (check with shasum of the
page first: the signature blob may differ, e.g. after later re-hashing on the phone). SIGBLOB: the phone file's
embedded signature, `dd if=FILE bs=1 skip=SIGOFF count=SIGSIZE` (offset/size from the cache header at 0x28).
The script checks every old word on the phone before writing (cmp of a dd extract) and refuses otherwise.
"""
import glob
import hashlib
import os
import struct
import sys

HASH = {1: 'sha1', 2: 'sha256', 3: 'sha256', 4: 'sha384'}


def where(d, va):
    for f in sorted(glob.glob(os.path.join(d, 'dyld_shared_cache_arm64e*'))):
        if any(s in f for s in ('.map', '.atlas')):
            continue
        with open(f, 'rb') as fh:
            hdr = fh.read(0x200)
            if not hdr.startswith(b'dyld_v1'):
                continue
            moff, mcnt = struct.unpack_from('<II', hdr, 0x10)
            fh.seek(moff)
            for a, size, foff, mp, ip in [struct.unpack('<QQQII', fh.read(32)) for _ in range(mcnt)]:
                if a <= va < a + size:
                    so, ss = struct.unpack_from('<QQ', hdr, 0x28)
                    return f, foff + va - a, so
    sys.exit(f'{va:#x}: not in any mapping')


def main():
    d, sigpath = sys.argv[1], sys.argv[2]
    sig = bytearray(open(sigpath, 'rb').read())
    edits, fname, sigoff = [], None, None
    for arg in sys.argv[3:]:
        va, w = arg.split('=')
        old, new = (int(x, 16) for x in w.split(':'))
        f, off, so = where(d, int(va, 16))
        if fname not in (None, f):
            sys.exit('all patches must be in one cache file')
        fname, sigoff = f, so
        edits.append((off, old, new))
    data = {}
    with open(fname, 'rb') as fh:
        for off, old, new in edits:
            fh.seek(off)
            if struct.unpack('<I', fh.read(4))[0] != old:
                sys.exit(f'local copy: word at {off:#x} is not {old:#010x}')
    orig = bytes(sig)
    magic, length, count = struct.unpack_from('>III', sig, 0)
    assert magic == 0xFADE0CC0, hex(magic)
    for i in range(count):
        typ, boff = struct.unpack_from('>II', sig, 12 + 8 * i)
        if struct.unpack_from('>I', sig, boff)[0] != 0xFADE0C02:
            continue
        cm, cl, ver, fl, hashOff, identOff, nSpecial, nCode, codeLimit = struct.unpack_from('>9I', sig, boff)
        hs, ht, sp, pl = struct.unpack_from('>BBBB', sig, boff + 36)
        ps = 1 << pl
        for p in sorted({off // ps for off, _, _ in edits}):     # each page once, with all its edits
            a, b = p * ps, min((p + 1) * ps, codeLimit)
            with open(fname, 'rb') as fh:
                fh.seek(a)
                page = bytearray(fh.read(b - a))
            want_old = hashlib.new(HASH[ht], bytes(page)).digest()[:hs]
            ho = boff + hashOff + p * hs
            if sig[ho:ho + hs] != want_old:
                sys.exit(f'CD {typ:#x}: the phone signature does not hash this page as the local copy has it: pages differ')
            for o2, ol2, nw2 in edits:
                if a <= o2 < b:
                    page[o2 - a:o2 - a + 4] = struct.pack('<I', nw2)
            sig[ho:ho + hs] = hashlib.new(HASH[ht], bytes(page)).digest()[:hs]
    name = os.path.basename(fname)
    F = f'/System/Library/dyld/{name}'
    print('#!/bin/sh\nset -e')
    for off, old, new in edits:
        print(f'[ "$(dd if={F} bs=1 skip={off} count=4 2>/dev/null | od -An -tx1 | tr -d " \\n")" = '
              f'"{struct.pack("<I", old).hex()}" ] || {{ echo "old word at {off} differs"; exit 1; }}')
    def esc(b):
        return ''.join(f'\\{x:03o}' for x in b)
    for off, old, new in edits:
        print(f"printf '{esc(struct.pack('<I', new))}' | dd of={F} bs=1 seek={off} conv=notrunc 2>/dev/null")
    i = 0
    while i < len(sig):
        if sig[i] != orig[i]:
            j = i
            while j < len(sig) and sig[j] != orig[j]:
                j += 1
            j = max(j, i + 1)
            print(f"printf '{esc(sig[i:j])}' | dd of={F} bs=1 seek={sigoff + i} conv=notrunc 2>/dev/null")
            i = j
        else:
            i += 1
    print('sync; echo patched')


if __name__ == '__main__':
    main()

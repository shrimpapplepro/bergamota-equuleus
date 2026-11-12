"""Patch instructions in a (pacstripped) dyld shared cache copy and re-hash the signature pages, printing every byte
range that changed so the same bytes can be written into the phone's copy of the file with dd.

  dsc_patch.py CACHE_DIR VA=OLDHEX:NEWHEX [VA=OLDHEX:NEWHEX ...]  [--dry-run]

VA is an unslid address; OLDHEX/NEWHEX are 32-bit instruction words (little-endian in the file). Every OLD word is
checked first (nothing is written if one differs). Then the words are written and pacstrip_cache.fix_signature
recomputes the CodeDirectory page hashes of the changed pages in place (dyld registers the embedded signature and the
kernel validates pages against it at fault time). Output lines `PATCH FILE OFFSET HEXBYTES` cover the instruction
words and the changed hash slots; apply each on the phone with
  printf '\\xAA\\xBB...' | dd of=/System/Library/dyld/FILE bs=1 seek=OFFSET conv=notrunc
(see dsc_patch_apply.sh output of --emit-sh). The Mac copy must be byte-identical to the phone's (check first).
"""
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'renegade'))
import pacstrip_cache  # noqa: E402


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
                    return f, foff + va - a
    sys.exit(f'{va:#x}: not in any mapping')


def sig_region(path):
    with open(path, 'rb') as fh:
        h = pacstrip_cache.read_header(fh.read(0x200))
    return h['codeSignatureOffset'], h['codeSignatureSize']


def main():
    d = sys.argv[1]
    dry = '--dry-run' in sys.argv
    edits = []
    for arg in sys.argv[2:]:
        if arg.startswith('--'):
            continue
        va, words = arg.split('=')
        old, new = words.split(':')
        f, off = where(d, int(va, 16))
        edits.append((f, off, int(old, 16), int(new, 16), int(va, 16)))
    todo = []
    for f, off, old, new, va in edits:
        with open(f, 'rb') as fh:
            fh.seek(off)
            cur = struct.unpack('<I', fh.read(4))[0]
        if cur == new:
            print(f'# {va:#x}: already patched', file=sys.stderr)
            continue
        if cur != old:
            sys.exit(f'{va:#x} ({os.path.basename(f)}+{off:#x}): found {cur:#010x}, expected {old:#010x}: nothing written')
        todo.append((f, off, old, new, va))
    edits = todo
    if not edits:
        return
    if dry:
        for f, off, old, new, va in edits:
            print(f'would patch {va:#x} {os.path.basename(f)}+{off:#x} {old:#010x} -> {new:#010x}')
        return
    by_file = {}
    for f, off, old, new, va in edits:
        by_file.setdefault(f, []).append((off, new))
    for f, items in by_file.items():
        so, ss = sig_region(f)
        with open(f, 'rb') as fh:
            fh.seek(so)
            before = fh.read(ss)
        with open(f, 'r+b') as fh:
            for off, new in items:
                fh.seek(off)
                fh.write(struct.pack('<I', new))
        n, note = pacstrip_cache.fix_signature(f, {off >> 12 for off, _ in items})
        with open(f, 'rb') as fh:
            fh.seek(so)
            after = fh.read(ss)
        name = os.path.basename(f)
        for off, new in items:
            print(f'PATCH {name} {off} {struct.pack("<I", new).hex()}')
        i = 0
        while i < len(after):
            if after[i] != before[i]:
                j = i
                while j < len(after) and (after[j] != before[j] or j - i < 1):
                    j += 1
                print(f'PATCH {name} {so + i} {after[i:j].hex()}')
                i = j
            else:
                i += 1
        print(f'# {name}: {n} page hashes updated ({note})', file=sys.stderr)


if __name__ == '__main__':
    main()

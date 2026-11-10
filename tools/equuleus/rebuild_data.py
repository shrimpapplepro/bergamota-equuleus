#!/usr/bin/env python3
"""Rebuild the Data disk as raw image from the packed seed plus the pages of a store dump. Works only on files on this Mac."""
import mmap, struct, sys, importlib.util
seed_path, store_path, out, loader = sys.argv[1:5]
spec = importlib.util.spec_from_file_location('packed_ramdisk', loader)
pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)
blob = open(seed_path, 'rb').read()
logical, extents = pr.regions(blob)
f = open(store_path, 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
base = m.find(b'SHNGDATA')
assert base >= 0 and base % 4096 == 0
ver, hdr, pages = struct.unpack_from('<IIQ', m, base + 8)
print('header at', hex(base), 'version', ver, 'pages', pages, 'logical', logical, 'generation', struct.unpack_from('<I', m, base + 56)[0])
assert pages * 4096 == logical, (pages * 4096, logical)
bm_blocks = (pages + 32767) // 32768
bitmap = m[base + 4096:base + 4096 + bm_blocks * 4096]
first = base + (1 + bm_blocks) * 4096
applied = 0
with open(out, 'wb') as o:
    o.truncate(logical)
    for offset, data in extents:
        o.seek(offset); o.write(data)
    for byte_index, byte in enumerate(bitmap):
        if not byte:
            continue
        for bit in range(8):
            if byte >> bit & 1:
                i = byte_index * 8 + bit
                o.seek(i * 4096)
                o.write(m[first + i * 4096:first + (i + 1) * 4096])
                applied += 1
print('pages applied', applied, applied * 4096 >> 20, 'MiB')

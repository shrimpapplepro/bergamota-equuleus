#!/usr/bin/env python3
"""Carve iOS crash reports and text logs out of the Data store dump (nonzero pages are in place; zeros are holes)."""
import json, mmap, os, re, sys
path, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
f = open(path, 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
print('magic at', m.find(b'SHNGDATA'), 'size', len(m))
pos = 0
seen = {}
while True:
    i = m.find(b'"bug_type":"', pos)
    if i < 0:
        break
    pos = i + 12
    # the header line starts with {"
    s = m.rfind(b'\n', max(0, i - 1500), i) + 1
    h = m.find(b'{"', max(0, i - 1500), i) if s == 0 else s
    e = m.find(b'\n', i, i + 1500)
    head = m[h:e if e > 0 else i + 800]
    try:
        info = json.loads(head)
    except Exception:
        continue
    key = info.get('incident_id') or info.get('incident') or h
    if key in seen:
        continue
    # to the next run of zeros
    z = m.find(b'\0' * 64, i, i + 8 << 20 if False else i + (8 << 20))
    blob = m[h:z if z > 0 else i + (8 << 20)]
    seen[key] = h
    name = f"{info.get('name') or info.get('app_name') or 'x'}-{info.get('bug_type')}-{len(seen):03d}.ips"
    name = re.sub(r'[^\w.\-]', '_', name)
    open(os.path.join(outdir, name), 'wb').write(blob)
    print(f"{h:#012x} {len(blob):7d} {name} {info.get('timestamp','')} {info.get('os_version','')[:30]}")
print('reports', len(seen))

"""Fast address -> image + nearest exported symbol for a split dyld shared cache (unslid addresses).
  dsc_sym.py CACHE_DIR ADDR [ADDR ...]
Image ranges come from the cache's image table and each image's __TEXT segment; names from the image's exports
trie (LC_DYLD_EXPORTS_TRIE / LC_DYLD_INFO export), so a non-exported function shows as the nearest export before it.
"""
import glob, os, struct, sys, bisect

d = sys.argv[1]
files = []
for f in sorted(glob.glob(os.path.join(d, 'dyld_shared_cache_arm64e*'))):
    if any(s in f for s in ('.map', '.atlas')):
        continue
    fh = open(f, 'rb')
    hdr = fh.read(0x200)
    if not hdr.startswith(b'dyld_v1'):
        continue
    moff, mcnt = struct.unpack_from('<II', hdr, 0x10)
    fh.seek(moff)
    maps = [struct.unpack('<QQQII', fh.read(32)) for _ in range(mcnt)]
    files.append((f, fh, hdr, maps))

def vm_read(addr, n):
    for f, fh, hdr, maps in files:
        for a, size, foff, mp, ip in maps:
            if a <= addr < a + size:
                fh.seek(foff + addr - a)
                return fh.read(n)
    return None

main = [x for x in files if x[0].endswith('dyld_shared_cache_arm64e')][0]
mfh, mhdr = main[1], main[2]
img_off, img_cnt = struct.unpack_from('<II', mhdr, 0x1C0)
mfh.seek(img_off)
images = []
for _ in range(img_cnt):
    addr, mt, ino, poff, pad = struct.unpack('<QQQII', mfh.read(32))
    images.append((addr, poff))

def cstr(fh, off):
    fh.seek(off)
    return fh.read(512).split(b'\0', 1)[0].decode()

def parse_image(base):
    h = vm_read(base, 32)
    magic, cpu, sub, ftype, ncmds, sizeofcmds, flags, res = struct.unpack('<IiiIIIII', h)
    lc = vm_read(base + 32, sizeofcmds)
    segs, trie = {}, None
    p = 0
    for _ in range(ncmds):
        cmd, sz = struct.unpack_from('<II', lc, p)
        if cmd == 0x19:
            name = lc[p + 8:p + 24].split(b'\0')[0].decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', lc, p + 24)
            segs[name] = (vmaddr, vmsize, fileoff)
        elif cmd == 0x80000033:                     # LC_DYLD_EXPORTS_TRIE
            trie = struct.unpack_from('<II', lc, p + 8)
        elif cmd in (0x22, 0x80000022) and trie is None:  # LC_DYLD_INFO(_ONLY): export_off, export_size
            vals = struct.unpack_from('<10I', lc, p + 8)
            trie = (vals[8], vals[9])
        p += sz
    return segs, trie

def uleb(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return r, i

def exports(segs, trie):
    if not trie or '__LINKEDIT' not in segs:
        return []
    le_vm, le_size, le_foff = segs['__LINKEDIT']
    off, size = trie
    data = vm_read(le_vm + off - le_foff, size)
    if not data:
        return []
    base = segs['__TEXT'][0]
    out, stack = [], [(0, '')]
    while stack:
        node, prefix = stack.pop()
        tsize, i = uleb(data, node)
        if tsize:
            j = i
            fl, j = uleb(data, j)
            if not (fl & 0x8):          # not a re-export
                a, j = uleb(data, j)
                out.append((base + a, prefix))
        i += tsize
        nchild = data[i]; i += 1
        for _ in range(nchild):
            e = data.index(b'\0', i)
            s = data[i:e].decode(errors='replace'); i = e + 1
            child, i = uleb(data, i)
            stack.append((child, prefix + s))
    return sorted(out)

cache_img = {}
for a_str in sys.argv[2:]:
    addr = int(a_str, 16)
    hit = None
    for base, poff in images:
        if base > addr or addr - base > 0x10000000:
            continue
        segs, trie = cache_img.get(base) or parse_image(base)
        cache_img[base] = (segs, trie)
        t = segs.get('__TEXT')
        if t and t[0] <= addr < t[0] + t[1]:
            hit = (base, poff, segs, trie)
            break
    if not hit:
        print(f'{a_str}: ?')
        continue
    base, poff, segs, trie = hit
    ex = exports(segs, trie)
    k = bisect.bisect_right([e[0] for e in ex], addr) - 1
    sym = f'{ex[k][1]}+0x{addr - ex[k][0]:x}' if k >= 0 else '?'
    print(f'{a_str}: {os.path.basename(cstr(mfh, poff))}  {sym}')

"""Turn the kernel's frame copy (sysctl kern.sweet_fb_shot, xnu 0224) into a PNG, on the Mac.
  ssh root@192.168.7.2 'sysctl -w kern.sweet_fb_shot_scale=3 >/dev/null; sysctl -b kern.sweet_fb_shot' > raw
  python3 -I fbshot2png.py raw out.png
Layout: 16-byte header (u32 'SHOT' 0x544f4853, width, height, bytes per row), then BGRA rows. No dependencies.
"""
import struct
import sys
import zlib

raw = open(sys.argv[1], 'rb').read()
magic, w, h, bpr = struct.unpack_from('<4I', raw, 0)
if magic != 0x544F4853 or 16 + bpr * h > len(raw):
    sys.exit(f'bad header {magic:#x} {w}x{h} bpr {bpr} ({len(raw)} bytes)')
rows, nz = bytearray(), 0
for y in range(h):
    r = raw[16 + y * bpr:16 + y * bpr + w * 4]
    rows.append(0)
    px = bytearray(w * 3)
    px[0::3] = r[2::4]
    px[1::3] = r[1::4]
    px[2::3] = r[0::4]
    nz += sum(1 for i in range(0, w * 4, 4) if r[i] | r[i + 1] | r[i + 2])
    rows += px


def chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)


png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + \
    chunk(b'IDAT', zlib.compress(bytes(rows), 6)) + chunk(b'IEND', b'')
open(sys.argv[2], 'wb').write(png)
print(f'{sys.argv[2]}: {w}x{h}, {nz * 100 // (w * h)}% non-black')

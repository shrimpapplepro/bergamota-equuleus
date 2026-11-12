"""Resolve a dyld cache stub: dsc_stub.py CACHE_DIR STUB_ADDR -> the GOT slot's target symbol."""
import os, struct, subprocess, sys, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
d, a = sys.argv[1], int(sys.argv[2], 16)
sys.argv = [sys.argv[0], d]
spec = importlib.util.spec_from_file_location('dsc_sym', os.path.join(here, 'dsc_sym.py'))
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
w = struct.unpack('<4I', ds.vm_read(a, 16))
# arm64e auth stub: adrp x17, page; add x17, x17, #off; ldr x16, [x17]; braa x16, x17
if (w[0] & 0x9F00001F) == 0x90000011 and (w[1] & 0xFFC003FF) == 0x91000231 and w[2] == 0xF9400230:
    imm = ((w[0] >> 29) & 3) | (((w[0] >> 5) & 0x7FFFF) << 2)
    if imm & (1 << 20): imm -= 1 << 21
    slot = (a & ~0xFFF) + (imm << 12) + ((w[1] >> 10) & 0xFFF)
    v = struct.unpack('<Q', ds.vm_read(slot, 8))[0]
    tgt = (v & 0x0000000FFFFFFFFF) + (0x180000000 if (v & 0x0000000FFFFFFFFF) < 0x100000000 else 0)
    out = subprocess.run([sys.executable, '-I', os.path.join(here, 'dsc_sym.py'), d, hex(tgt)], capture_output=True, text=True).stdout.strip()
    print(f'stub {a:#x} -> slot {slot:#x} = {v:#x} -> {out}')
    sys.exit(0)
x16 = None
for k, i in enumerate(w):
    pc = a + 4 * k
    if (i & 0x9F000000) == 0x90000000 and (i & 31) == 16:
        imm = ((i >> 29) & 3) | (((i >> 5) & 0x7FFFF) << 2)
        if imm & (1 << 20): imm -= 1 << 21
        x16 = (pc & ~0xFFF) + (imm << 12)
    elif (i & 0xFFC003FF) == 0xF9400210 and x16 is not None:      # ldr x16, [x16, #imm]
        slot = x16 + ((i >> 10) & 0xFFF) * 8
        v = struct.unpack('<Q', ds.vm_read(slot, 8))[0]
        tgt = (v & 0x0000000FFFFFFFFF) + (0x180000000 if (v & 0x0000000FFFFFFFFF) < 0x100000000 else 0)                               # drop PAC / high bits
        out = subprocess.run([sys.executable, '-I', os.path.join(here, 'dsc_sym.py'), d, hex(tgt)], capture_output=True, text=True).stdout.strip()
        print(f'stub {a:#x} -> slot {slot:#x} = {v:#x} -> {out}')
        sys.exit(0)
    elif (i & 0xFFC003FF) == 0xF9400211 and x16 is not None:      # ldr x17, [x16, #imm] (auth stub form)
        slot = x16 + ((i >> 10) & 0xFFF) * 8
        v = struct.unpack('<Q', ds.vm_read(slot, 8))[0]
        tgt = (v & 0x0000000FFFFFFFFF) + (0x180000000 if (v & 0x0000000FFFFFFFFF) < 0x100000000 else 0)
        out = subprocess.run([sys.executable, '-I', os.path.join(here, 'dsc_sym.py'), d, hex(tgt)], capture_output=True, text=True).stdout.strip()
        print(f'stub {a:#x} -> slot {slot:#x} = {v:#x} -> {out}')
        sys.exit(0)
print('not a recognised stub:', [hex(x) for x in w])

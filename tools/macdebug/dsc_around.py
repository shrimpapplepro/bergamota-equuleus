"""Disassemble N instructions before ADDR in a dyld cache; resolve BL targets and ADRP+ADD/LDR string refs.
  dsc_around.py CACHE_DIR ADDR [N]"""
import os, struct, subprocess, sys, tempfile, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
d, addr = sys.argv[1], int(sys.argv[2], 16)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
sys.argv = [sys.argv[0], d]                          # dsc_sym parses argv at import: give it no addresses
spec = importlib.util.spec_from_file_location('dsc_sym', os.path.join(here, 'dsc_sym.py'))
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
start = addr - 4 * n
raw = ds.vm_read(start, 4 * (n + 4))
words = struct.unpack(f'<{len(raw)//4}I', raw)
with tempfile.TemporaryDirectory() as t:
    s = os.path.join(t, 'a.s'); o = os.path.join(t, 'a.o')
    open(s, 'w').write('.text\n' + ''.join(f'.inst 0x{w:08x}\n' for w in words))
    subprocess.run(['clang', '-c', '-arch', 'arm64', s, '-o', o], check=True)
    dis = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/llvm-objdump', '-d', '--no-show-raw-insn', o],
                         capture_output=True, text=True).stdout
lines = [l for l in dis.splitlines() if l.strip()[:1].isdigit() or (':' in l and l.strip().split(':')[0].strip().isalnum() and l.startswith(' '))]
lines = [l for l in dis.splitlines() if l.startswith('    ') or l.startswith('\t') or l[:8].strip().endswith(':')][-len(words):]
adrp = {}
def cstr_at(va):
    b = ds.vm_read(va, 160)
    if not b: return None
    z = b.split(b'\0', 1)[0]
    try:
        t = z.decode()
    except UnicodeDecodeError:
        return None
    return t if t and all(32 <= ord(c) < 127 for c in t) else None
for k, w in enumerate(words):
    pc = start + 4 * k
    txt = lines[k].split(':', 1)[1].strip() if k < len(lines) and ':' in lines[k] else f'.inst 0x{w:08x}'
    note = ''
    if (w & 0xFC000000) == 0x94000000:              # BL
        imm = w & 0x03FFFFFF
        if imm & 0x02000000: imm -= 0x04000000
        tgt = pc + imm * 4
        note = ds_sym = ''
        try:
            sys.argv = [sys.argv[0], d]
            out = subprocess.run([sys.executable, '-I', os.path.join(here, 'dsc_sym.py'), d, hex(tgt)], capture_output=True, text=True).stdout.strip()
            note = '  -> ' + out.split(': ', 1)[-1]
        except Exception as e:
            note = f'  -> {tgt:#x}'
    elif (w & 0x9F000000) == 0x90000000:            # ADRP
        rd = w & 31
        imm = ((w >> 29) & 3) | (((w >> 5) & 0x7FFFF) << 2)
        if imm & (1 << 20): imm -= 1 << 21
        adrp[rd] = (pc & ~0xFFF) + (imm << 12)
    elif (w & 0xFF800000) == 0x91000000:            # ADD imm
        rn, rd = (w >> 5) & 31, w & 31
        if rn in adrp:
            va = adrp[rn] + ((w >> 10) & 0xFFF)
            s_ = cstr_at(va)
            note = f'  ; {va:#x}' + (f' "{s_}"' if s_ else '')
    mark = '  <== ret addr' if pc == addr else ''
    print(f'{pc:#x}: {txt}{note}{mark}')

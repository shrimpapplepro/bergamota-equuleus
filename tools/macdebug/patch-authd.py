#!/usr/bin/env python3
"""Patch macOS authd so it does not require an Apple-anchored code signature on its login agents.

  patch-authd.py AUTHD_IN AUTHD_OUT

The macOS port re-signs every binary ad-hoc (inherent to PAC-stripping), so authd's agent requirement
`identifier "com.apple.SecurityAgent" and anchor apple` can never be satisfied and `system.login.console`
fails ("Received message forbidden due to code signing requirement" / "the responder does not satisfy the
required code identity"). authd sets that requirement with a single call to
`_xpc_connection_set_peer_code_signing_requirement(conn, req)` per arm64e slice; this replaces that `bl`
with `mov w0, #0` (requirement never set, success path taken). Re-sign the output ad-hoc preserving
entitlements: `codesign -f -s - --preserve-metadata=entitlements,identifier,flags AUTHD_OUT`.

Call site is found per slice from the symbol stub (otool), so it survives version changes.
"""
import struct
import subprocess
import sys


def slices(d):
    if struct.unpack_from('>I', d, 0)[0] != 0xCAFEBABE:
        sys.exit('not a fat binary')
    n = struct.unpack_from('>I', d, 4)[0]
    out = []
    for i in range(n):
        ct, cs, off, size, al = struct.unpack_from('>IIIII', d, 8 + 20 * i)
        out.append((ct, cs, off, size))
    return out


def find_call(path, fatoff, size):
    """Return the within-slice file offset of the bl to _xpc_connection_set_peer_code_signing_requirement."""
    tmp = path + f'.slice{fatoff:x}'
    with open(path, 'rb') as f:
        f.seek(fatoff)
        open(tmp, 'wb').write(f.read(size))
    dis = subprocess.run(['otool', '-tV', tmp], capture_output=True, text=True).stdout
    for line in dis.splitlines():
        if 'set_peer_code_signing_requirement' in line and '\tbl\t' in line:
            va = int(line.split()[0], 16)
            return va - 0x100000000     # __TEXT vmaddr base
    return None


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = bytearray(open(src, 'rb').read())
    patched = 0
    for ct, cs, off, size in slices(d):
        if ct != 0x100000C:             # arm64e only
            continue
        vmoff = find_call(src, off, size)
        if vmoff is None:
            print(f'slice {cs:#x}: no set_peer call found', file=sys.stderr)
            continue
        fo = off + vmoff
        cur = struct.unpack_from('<I', d, fo)[0]
        if (cur & 0xFC000000) != 0x94000000:
            sys.exit(f'slice {cs:#x} {fo:#x}: not a bl ({cur:#010x})')
        struct.pack_into('<I', d, fo, 0x52800000)   # mov w0, #0
        print(f'slice {cs:#x}: {fo:#x} {cur:#010x} -> mov w0,#0')
        patched += 1
    if not patched:
        sys.exit('nothing patched')
    open(dst, 'wb').write(d)
    print(f'wrote {dst}; now: codesign -f -s - --preserve-metadata=entitlements,identifier,flags {dst}')


if __name__ == '__main__':
    main()

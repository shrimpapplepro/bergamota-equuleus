#!/usr/bin/env python3
"""Read a window of sda23 from the phone over adb and keep only its nonzero 4K pages, as a sparse file. Read only on the phone."""
import subprocess, sys, time
out, skip_mib, count_mib = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
cmd = ['adb', 'exec-out', f'dd if=/dev/block/sda23 bs=1048576 skip={skip_mib} count={count_mib} 2>/dev/null']
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1 << 20)
MIB = 1 << 20
total = kept = 0
t0 = time.time()
with open(out, 'wb') as f:
    pending = b''
    while True:
        block = p.stdout.read(MIB)
        if not block:
            break
        if block.strip(b'\0'):
            for i in range(0, len(block), 4096):
                page = block[i:i + 4096]
                if page.strip(b'\0'):
                    f.seek(total + i)
                    f.write(page)
                    kept += 1
        total += len(block)
        if total % (1024 * MIB) == 0:
            print(f'{total >> 30} GiB, {kept * 4096 >> 20} MiB nonzero, {time.time() - t0:.0f}s', flush=True)
    f.truncate(total)
print('done', total, 'bytes', kept * 4096 >> 20, 'MiB nonzero', f'{time.time() - t0:.0f}s', 'rc', p.wait(), flush=True)

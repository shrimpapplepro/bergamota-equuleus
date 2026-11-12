"""Count instruction encodings of ARMv8.3+ extensions the SDM845 lacks in the executable mappings of a dyld cache."""
import glob, os, struct, sys
import numpy as np
PAT = {  # name: (mask, value)
 'DotProd vec (SDOT/UDOT)': (0xBFE0FC00, 0x0E809400),
 'DotProd elem':            (0xBFC0F400, 0x0F80E000),
 'FHM FMLAL/FMLSL vec':     (0xBFA0EC00, 0x0E20EC00),  # approx: FMLAL(2)/FMLSL(2) vector
 'FHM elem':                (0xBFC0B400, 0x0F800000),  # approx: FMLAL/FMLSL by element (size=10, opc 0x00/0x40/0x80/0xC0)
 'FCMA FCMLA vec':          (0xBF20E400, 0x2E00C400),
 'FCMA FCADD':              (0xBF20EC00, 0x2E00E400),
 'JSCVT FJCVTZS':           (0xFFFFFC00, 0x1E7E0000),
 'LRCPC2 LDAPUR/STLUR':     (0x3F200C00, 0x19000000),
 'FlagM CFINV':             (0xFFFFFFFF, 0xD500401F),
 'FlagM RMIF':              (0xFFE07C10, 0xBA000400),
 'FlagM SETF8/16':          (0xFFFFBC1F, 0x3A00080D),
 'FlagM2 AXFLAG/XAFLAG':    (0xFFFFFFDF, 0xD500405F),
 'SB':                      (0xFFFFFFFF, 0xD50330FF),
 'FRINTTS FRINT32/64':      (0xFFB6FC00, 0x1E284000),
 'I8MM SMMLA/UMMLA/USMMLA': (0xBFE0FC00, 0x4E80A400),
 'BF16 BFDOT/BFMMLA/BFCVT': (0xBFE0FC00, 0x2E40FC00),
 'SHA3 EOR3/BCAX/RAX1/XAR': (0xFF808000, 0xCE000000),
 'SHA512':                  (0xFFE0B000, 0xCE608000),
 'SM3/SM4':                 (0xFFE0C000, 0xCE40C000),
}
tot = {k: 0 for k in PAT}
for f in sorted(glob.glob(os.path.join(sys.argv[1], 'dyld_shared_cache_arm64e*'))):
    if any(s in f for s in ('.map', '.atlas', 'symbols')):
        continue
    with open(f, 'rb') as fh:
        hdr = fh.read(0x200)
        if not hdr.startswith(b'dyld_v1'):
            continue
        moff, mcnt = struct.unpack_from('<II', hdr, 0x10)
        fh.seek(moff)
        for i in range(mcnt):
            addr, size, foff, maxp, initp = struct.unpack('<QQQII', fh.read(32))
            if not (initp & 4):
                continue
            pos = fh.tell()
            fh.seek(foff)
            w = np.frombuffer(fh.read(size - size % 4), dtype='<u4')
            fh.seek(pos)
            for k, (m, v) in PAT.items():
                tot[k] += int(np.count_nonzero((w & np.uint32(m)) == np.uint32(v)))
for k, n in sorted(tot.items(), key=lambda x: -x[1]):
    print(f'{n:9d}  {k}')

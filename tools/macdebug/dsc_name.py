"""Unslid address of an exported symbol: dsc_name.py CACHE_DIR IMAGE_BASENAME SYMBOL"""
import os, sys, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
d, img, sym = sys.argv[1:4]
sys.argv = [sys.argv[0], d]
spec = importlib.util.spec_from_file_location('dsc_sym', os.path.join(here, 'dsc_sym.py'))
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
for base, poff in ds.images:
    if os.path.basename(ds.cstr(ds.mfh, poff)) == img:
        segs, trie = ds.parse_image(base)
        for a, n in ds.exports(segs, trie):
            if n == sym:
                print(hex(a)); sys.exit(0)
print('not found')

import os, sys, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
d, img = sys.argv[1:3]
sys.argv = [sys.argv[0], d]
spec = importlib.util.spec_from_file_location('dsc_sym', os.path.join(here, 'dsc_sym.py'))
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
for base, poff in ds.images:
    if os.path.basename(ds.cstr(ds.mfh, poff)) == img:
        print(hex(base)); break

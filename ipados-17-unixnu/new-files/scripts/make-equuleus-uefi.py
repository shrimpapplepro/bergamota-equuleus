#!/usr/bin/env python3
"""Add UniXNU to Mu-Silicium's own equuleus (Xiaomi Mi 8 Pro) package.

make-dipper-uefi.py derives dipper from equuleusPkg and swaps out the panel driver. This phone IS equuleus, so the
package is patched in place: the native DisplayDxe, vendor binaries, DTS and boot image config stay as upstream has
them, and only the UniXNU modules plus the shared SEC and BootShim handoff fixes are applied. Edit lists are reused
from make-dipper-uefi.py, so both ports stay in step and upstream drift still stops the script.

Usage: make-equuleus-uefi.py MU_SILICIUM_DIR
"""
import argparse
import importlib.util
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

spec = importlib.util.spec_from_file_location('dipper_uefi', HERE / 'make-dipper-uefi.py')
dipper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dipper)

DEC_GUID = ('  gDipperPayloadFileGuid = { 0xD8B745A4, 0x0D49, 0x4A76, '
            '{ 0x9E, 0x74, 0x79, 0xD7, 0xB7, 0xD5, 0x3A, 0x61 } }\n')

# dipper-only edits: its own platform GUID, dropping the panel driver, and the Mi 8 model strings.
SKIP = ('PLATFORM_GUID', 'USE_CUSTOM_DISPLAY_DRIVER', 'PcdSmbiosSystem')
MARK = 'UniXNUPkg/Application/UniXNU/UniXNU.inf'


def to_equuleus(text):
    return text.replace('dipper', 'equuleus')


def apply_marked(path, mark, edits, label):
    """Apply (name, original, replacement) edits under path once, keyed on a marker in the first file."""
    if mark in dipper.read(path / edits[0][0])[0]:
        print(f'{label}: already patched')
        return
    for name, original, replacement in edits:
        dipper.replace_once(path / name, original, replacement)
    print(f'{label}: patched')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('uefi', type=Path, help='Mu-Silicium checkout')
    uefi = parser.parse_args().uefi.resolve()
    package = uefi / 'Platforms/Xiaomi/equuleusPkg'
    if not package.is_dir():
        raise SystemExit(f'not a Mu-Silicium checkout with equuleusPkg: {uefi}')

    # Board modules: the payload block device driver and the USB log app, re-pointed at this package.
    for driver in ('DipperBootMemoryDxe', 'DipperUsbLogDxe'):
        target = package / 'Drivers' / driver
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ROOT / 'uefi' / driver, target)
        for inf in target.glob('*.inf'):
            text, _ = dipper.read(inf)
            inf.write_text(text.replace('dipperPkg/dipper.dec', 'equuleusPkg/equuleus.dec'), newline='')

    dec = package / 'equuleus.dec'
    # Upstream's equuleus.dec is empty, so the whole file is written, as make-dipper-uefi.py does for its copy.
    if '[Defines]' not in dipper.read(dec)[0]:
        dec.write_text(
            '[Defines]\n'
            '  DEC_SPECIFICATION = 0x00010005\n'
            '  PACKAGE_NAME      = equuleusPkg\n'
            '  PACKAGE_GUID      = 3E7B2C14-9A5D-4F61-8C27-D1E4A6B09F35\n'
            '  PACKAGE_VERSION   = 0.1\n\n'
            '[Guids]\n' + DEC_GUID
        )
        print('package declaration: written')

    edits = [(to_equuleus(name), to_equuleus(original), to_equuleus(replacement))
             for name, original, replacement in dipper.EDITS
             if not original.lstrip().startswith(SKIP) and 'PcdSmbiosSystem' not in original]
    if MARK in dipper.read(package / 'equuleus.dsc')[0]:
        print('package modules: already patched')
    else:
        for name, original, replacement in edits:
            dipper.replace_once(package / name, original, replacement)
        print(f'package modules: {len(edits)} edits applied')

    # Measured on the phone: the 87 MiB DXE heap ran out before the APRIORI list ended, so RamManagerDxe (outside the
    # list) never loaded and the rest of DRAM was never added. Its protocol comes from EnvDxe, loaded first, and adding
    # DRAM needs CpuDxe; both precede this point.
    apriori = package / 'Include/APRIORI.inc'
    ram_manager = '  INF SiliciumPkg/Drivers/RamManagerDxe/RamManagerDxe.inf\n'
    if ram_manager in dipper.read(apriori)[0]:
        print('early RAM manager: already patched')
    else:
        hal_iommu = '  INF Binaries/equuleus/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.inf\n'
        dipper.replace_once(apriori, hal_iommu, hal_iommu + ram_manager)
        print('early RAM manager: patched')

    # Shared by every device of the checkout: the entry-argument HOB, cache maintenance and appended payload support.
    sec = uefi / dipper.SEC
    if dipper.SEC_MARK in dipper.read(sec / 'SiliciumPkg.dec')[0]:
        print('SEC: already patched')
    else:
        for name, original, replacement in dipper.SEC_EDITS:
            dipper.replace_once(sec / name, original, replacement)
        for name, text in dipper.SEC_APPEND.items():
            dipper.append(sec / name, text)
        dipper.replace_once(sec / 'Sec/AArch64/Helper.S', 'ASM_FUNCTION_REMOVE_IF_UNREFERENCED',
                            dipper.SEC_HELPER + 'ASM_FUNCTION_REMOVE_IF_UNREFERENCED')
        print('SEC: patched')

    shim = uefi / dipper.SHIM
    if dipper.SHIM_MARK in dipper.read(shim)[0]:
        print('boot shim: already patched')
    else:
        for original, replacement in dipper.SHIM_EDITS:
            dipper.replace_once(shim, original, replacement)
        print('boot shim: patched')

    # dipper's marker (APPENDED_PAYLOAD_SIZE) also occurs in SHIM_EDITS, so it reads as patched after them and the
    # edits below would be skipped. The #ifndef only exists once they are applied.
    if '#ifndef APPENDED_PAYLOAD_SIZE' in dipper.read(shim)[0]:
        print('appended payload shim: already patched')
    else:
        for original, replacement in dipper.APPENDED_SHIM_EDITS:
            dipper.replace_once(shim, original, replacement)
        print('appended payload shim: patched')

    apply_marked(sec, dipper.APPENDED_SEC_MARK, dipper.APPENDED_SEC_EDITS, 'appended payload SEC')
    apply_marked(uefi, dipper.RAM_READY_MARK, dipper.RAM_READY_EDITS, 'RAM-ready protocol')
    print(f'firmware port: {package}')


if __name__ == '__main__':
    main()

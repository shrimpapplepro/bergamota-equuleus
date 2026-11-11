#!/usr/bin/env python3
"""Full macOS 27.2 root for the Mi 8 Pro: the VirtualMac2,1 system volume + SystemOS and AppOS cryptexes as one
HFSX root, for `ios_data`.

  mkroot-mac27-full.py DMG_DIR OUT_IMG --keys DIR --authorized-keys FILE [--size 30g] [--jobs N]
                       [--stages copy,macho,cache,tweaks,seal] [--allow-jobs FILE]

DMG_DIR holds the decrypted images of UniversalMac_27.2_26B123 (identity vma2macosap, `ipsw extract --dmg fs|sys|app`
then `ipsw fw aea`): OS 141-12228-170.dmg, SystemOS 141-12293-172.dmg, AppOS 141-12233-175.dmg. Reuses
mkroot-full.py's stages (copy: cryptexes first, OS volume on top, owner map; macho: pacstrip + ad-hoc re-sign of every
Mach-O; cache: pacstrip_cache.py + fips_rehmac.py) with the dyld cache at the macOS path /System/Library/dyld (the
first place ignition looks on the system volume). Then (tweaks):

  * launch daemons: only an allow-list stays in /System/Library/LaunchDaemons (DEFAULT_JOBS or --allow-jobs, one
    label per line); every other plist moves to /System/Library/LaunchDaemons.sweet-off/ (same name), so a daemon
    goes back with one `mv` + `launchctl bootstrap system ...` over SSH. LaunchAgents move to
    /System/Library/LaunchAgents.sweet-off/ (no user session yet);
  * org.sweet.dropbear (SSH, as in the mini root) and org.sweet.mac27.hello (one line + uname/ps on the console);
  * dropbear-mac and toybox-mac in /usr/local/bin, host keys, root's authorized_keys;
  * the single volume stands in for System + Data: the firmlinked Data paths (/Users, /Applications, /Library,
    /private/var/...) are plain directories on it.

seal: unmount, hfsroot_owners.py (owner map, the rest root:wheel), fsck_hfs, then a manifest of the image's 1 MiB
block hashes (OUT_IMG.blocks) for writeback-ios-data.py, which later writes only changed blocks to the phone.
Nothing here touches the phone.

Known gap (2026-11-12 build): six OS-volume entries are root-only even on a noowners mount (the dslocal Default node
templates aliases/computers/groups/networks/users under System/Library/Templates/Data/private/var/db/dslocal/nodes/
Default, and usr/sbin/visudo), so the copy stage stops after `ditto os` with "Permission denied". Copy them with sudo
(`cp -Rp` from a read-only mount of the OS dmg), record `stat -f "%N\t%u\t%g\t%Lp"` of them, rebuild owners.tsv
(appos, sysos, os walked owners-on, then those lines), run mf.prune_after(root, 'os') + mf.layout_fixes(root), make
the copies user-readable for the build, and continue with --stages macho,cache,tweaks,seal (the seal step applies
the recorded modes). The 2026-11-12 build did exactly that (scratchpad mac27-owners-resume.py).
"""
import argparse
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('mkroot_full', os.path.join(HERE, 'mkroot-full.py'))
mf = importlib.util.module_from_spec(spec)
sys.modules['mkroot_full'] = mf          # multiprocessing pickles mf.macho_worker by module name
spec.loader.exec_module(mf)
rplat = mf.rplat
log = mf.log

CACHE_REL = 'System/Library/dyld'
DMG_NAMES = {'os': '141-12228-170.dmg', 'sysos': '141-12293-172.dmg', 'appos': '141-12233-175.dmg'}

# Daemons kept for the first full boot: logging, notifications, configuration, directory services, disks.
DEFAULT_JOBS = [
    'com.apple.logd', 'com.apple.syslogd', 'com.apple.notifyd', 'com.apple.configd', 'com.apple.opendirectoryd',
    'com.apple.diskarbitrationd', 'com.apple.securityd', 'com.apple.trustd', 'com.apple.mDNSResponder',
    'com.apple.mDNSResponderHelper', 'com.apple.coreservicesd', 'com.apple.lsd', 'com.apple.cfprefsd.xpc.daemon',
    'com.apple.distnoted.xpc.daemon', 'com.apple.kextd', 'com.apple.usermanagerd', 'com.apple.taskgated',
    'com.apple.taskgated-helper', 'com.apple.UserEventAgent-System', 'com.apple.powerd',
]

DROPBEAR = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>org.sweet.dropbear</string>
<key>ProgramArguments</key><array><string>/usr/local/bin/dropbear</string><string>-F</string><string>-E</string>
<string>-s</string><string>-p</string><string>22</string><string>-r</string>
<string>/private/etc/dropbear/dropbear_ed25519_host_key</string></array>
<key>KeepAlive</key><true/><key>RunAtLoad</key><true/><key>UserName</key><string>root</string>
<key>StandardErrorPath</key><string>/dev/console</string>
</dict></plist>
"""
HELLO = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>org.sweet.mac27.hello</string>
<key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string>
<string>echo "SWEET MAC27 FULL: launchd runs jobs"; /usr/bin/uname -a; /usr/bin/sw_vers; /bin/ps -A</string></array>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>/dev/console</string><key>StandardErrorPath</key><string>/dev/console</string>
</dict></plist>
"""


def macho_worker_mac(path):
    """mkroot-full's worker, plus: codesign refuses a bundle's main executable whose bundle has unsigned nested code
    ("code object is not signed at all / In subcomponent ...": Dock, iWork importers). The kernel checks no bundle
    seals, so such a file is signed as a standalone copy outside its bundle and put back (identity kept)."""
    import tempfile
    p, status, counts = mf.macho_worker(path)
    if not (status or '').startswith('FAILED: codesign failed'):
        return p, status, counts
    t = tempfile.mkdtemp(prefix='sweet-sign-')
    try:
        q = os.path.join(t, os.path.basename(path))
        shutil.copyfile(path, q)
        os.chmod(q, 0o755)
        old = mf.pacstrip.sign(q)
        mode = os.stat(path).st_mode & 0o7777
        shutil.copyfile(q, path)
        os.chmod(path, mode)
        return p, 'rewritten', {'__ident': old, 'standalone-signed': 1}
    except BaseException as e:
        return p, 'FAILED: standalone sign: ' + str(e)[:200], None
    finally:
        shutil.rmtree(t, ignore_errors=True)


def stage_tweaks(a, root, table):
    import plistlib
    allow = set(DEFAULT_JOBS)
    if a.allow_jobs:
        allow = {l.strip() for l in open(a.allow_jobs) if l.strip() and not l.startswith('#')}
    for sub in ('LaunchDaemons', 'LaunchAgents'):
        src = os.path.join(root, 'System/Library', sub)
        off = os.path.join(root, 'System/Library', sub + '.sweet-off')
        os.makedirs(off, exist_ok=True)
        table[f'System/Library/{sub}.sweet-off'] = (0, 0, 0o755)
        kept, moved = [], 0
        for n in sorted(os.listdir(src)):
            p = os.path.join(src, n)
            label = None
            try:
                label = plistlib.load(open(p, 'rb')).get('Label')
            except Exception:
                pass
            if sub == 'LaunchDaemons' and (label in allow or n[:-6] in allow):
                kept.append(n)
                continue
            os.rename(p, os.path.join(off, n))
            rel_old, rel_new = f'System/Library/{sub}/{n}', f'System/Library/{sub}.sweet-off/{n}'
            if rel_old in table:
                table[rel_new] = table.pop(rel_old)
            moved += 1
        log(f'{sub}: kept {len(kept)} {kept if sub == "LaunchDaemons" else ""}, moved {moved} to {sub}.sweet-off')
        missing = sorted(allow - {k[:-6] for k in kept}) if sub == 'LaunchDaemons' else []
        if missing:
            log('  allow-list labels with no plist:', missing)

    ld = os.path.join(root, 'System/Library/LaunchDaemons')
    for name, text in (('org.sweet.dropbear.plist', DROPBEAR), ('org.sweet.mac27.hello.plist', HELLO)):
        p = os.path.join(ld, name)
        open(p, 'w').write(text)
        os.chmod(p, 0o644)
        table['System/Library/LaunchDaemons/' + name] = (0, 0, 0o644)

    def put(src, rel, mode):
        dst = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, mode)
        table[rel] = (0, 0, mode)
    sb = os.path.join(ROOT, 'research/ssh-build/out')
    put(os.path.join(sb, 'dropbear-mac'), 'usr/local/bin/dropbear', 0o755)
    put(os.path.join(sb, 'toybox-mac'), 'usr/local/bin/toybox', 0o755)
    for d in ('usr/local', 'usr/local/bin', 'private/etc/dropbear'):
        table[d] = (0, 0, 0o755)
    for k in ('dropbear_ed25519_host_key', 'dropbear_ecdsa_host_key'):
        if os.path.exists(os.path.join(a.keys, k)):
            put(os.path.join(a.keys, k), 'private/etc/dropbear/' + k, 0o600)
    put(a.authorized_keys, 'private/var/root/.ssh/authorized_keys', 0o600)
    table['private/var/root'] = (0, 0, 0o755)
    table['private/var/root/.ssh'] = (0, 0, 0o700)
    os.chmod(os.path.join(root, 'private/var/root/.ssh'), 0o700)

    # One volume for System + Data: the firmlink targets and the usual Data directories as plain directories.
    for d, mode in (('Users', 0o755), ('Users/Shared', 0o1777), ('Applications', 0o775), ('Library', 0o755),
                    ('private/tmp', 0o1777), ('private/var/tmp', 0o1777), ('private/var/log', 0o755),
                    ('private/var/run', 0o755), ('private/var/db', 0o755), ('private/var/folders', 0o755),
                    ('private/var/vm', 0o755), ('private/var/root', 0o755), ('System/Volumes/Data', 0o755),
                    ('System/Volumes/Preboot', 0o755), ('System/Volumes/VM', 0o755)):
        p = os.path.join(root, d)
        if not os.path.lexists(p):
            os.makedirs(p, exist_ok=True)
            os.chmod(p, mode)
            table.setdefault(d, (0, 80 if d == 'Applications' else 0, mode))
    # launchd's prebuilt job cache (/System/Library/xpc/launchd.plist, keyed by plist path, daemons AND agents) is
    # what launchd loads; the directories are only its fallback. Keep the allow-listed daemons + our two jobs in it
    # (needs boot-arg launchd_unsecure_cache=1, as on the iOS roots); the original stays as launchd.plist.sweet-orig.
    cache = os.path.join(root, 'System/Library/xpc/launchd.plist')
    orig = cache + '.sweet-orig'
    if not os.path.exists(orig):
        shutil.copyfile(cache, orig)
        table['System/Library/xpc/launchd.plist.sweet-orig'] = (0, 0, 0o644)
    c = plistlib.load(open(orig, 'rb'))
    jobs = c['LaunchDaemons']
    keep = {k: v for k, v in jobs.items() if k.startswith('/System/Library/LaunchDaemons/') and isinstance(v, dict)
            and v.get('Label') in allow}
    for name, text in (('org.sweet.dropbear.plist', DROPBEAR), ('org.sweet.mac27.hello.plist', HELLO)):
        keep['/System/Library/LaunchDaemons/' + name] = plistlib.loads(text.encode())
    c['LaunchDaemons'] = keep
    with open(cache, 'wb') as f:
        plistlib.dump(c, f, fmt=plistlib.FMT_BINARY)
    log(f'launchd cache: {len(jobs)} jobs -> {len(keep)}: {sorted(v["Label"] for v in keep.values())}')

    # /System/Cryptexes/{OS,App} -> ../../System/Volumes/Preboot/Cryptexes/{OS,App}: the cryptexes are merged into
    # the root, so those point back at /
    pc = os.path.join(root, 'System/Volumes/Preboot/Cryptexes')
    os.makedirs(pc, exist_ok=True)
    for n in ('OS', 'App'):
        p = os.path.join(pc, n)
        if os.path.lexists(p):
            os.unlink(p)
        os.symlink('../../../../..', p)
    table.setdefault('System/Volumes/Preboot/Cryptexes', (0, 0, 0o755))

    fl = os.path.join(root, 'usr/share/firmlinks')
    if os.path.exists(fl):
        log('firmlinks (informational, not used on HFS):', open(fl).read().replace('\t', ' -> ').strip().replace('\n', '; ')[:600])


def write_blocks(img):
    """sha1 of every 1 MiB block, one hex digest per line (writeback-ios-data.py diffs against it)."""
    out = img + '.blocks'
    t0 = time.time()
    with open(img, 'rb') as f, open(out + '.tmp', 'w') as o:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            o.write(hashlib.sha1(b).hexdigest() + '\n')
    os.replace(out + '.tmp', out)
    log(f'block manifest {out} ({time.time() - t0:.0f}s)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dmg_dir')
    ap.add_argument('out')
    ap.add_argument('--size', default='30g')
    ap.add_argument('--keys', required=True)
    ap.add_argument('--authorized-keys', required=True)
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    ap.add_argument('--stages', default='copy,macho,cache,tweaks,seal')
    ap.add_argument('--allow-jobs', default=None)
    a = ap.parse_args()
    stages = a.stages.split(',')

    work = os.path.join(ROOT, 'research', 'mac27-full')          # map files and mount points: internal disk
    os.makedirs(work, exist_ok=True)
    mf.W = work
    mf.JB_OWNERS = os.path.join(work, 'owners-jb.tsv')
    mf.CACHE_REL = CACHE_REL
    mf.macho_worker = macho_worker_mac         # stage_macho's pool looks the worker up as a module global
    # macOS system files carry the `restricted` BSD flag (SF_RESTRICTED); a non-root ditto cannot set it and then
    # leaves the file out ("Operation not permitted", first run: Safari.app and 28 more from AppOS alone). The
    # platform's pure Python copy moves data, symlinks and hard links only; owners/modes come from the owner map.
    mf.copy_tree = lambda src, dst: rplat.py_copy_tree(src, dst, list(mf.EXCLUDE), chown=False)
    # hfs_trim.py punches holes into the image file to give pruned blocks back to the host; exFAT (DEEZNUTS) has no
    # F_PUNCHHOLE ("Inappropriate ioctl for device"), and the image is not sparse there anyway: skip it.
    _run = mf.run
    mf.run = lambda cmd, **kw: None if any(str(c).endswith('hfs_trim.py') for c in cmd) else _run(cmd, **kw)
    rootmnt = os.path.join(work, 'root')
    dmgs = {k: os.path.join(a.dmg_dir, v) for k, v in DMG_NAMES.items()}
    img = os.path.abspath(a.out)
    a.skip_sources, a.delete_sources = None, False

    if 'copy' in stages:
        mf.stage_copy(a, img, rootmnt, dmgs)        # leaves the image mounted at rootmnt, owners.tsv in work
    elif not os.path.ismount(rootmnt):
        mf.attach(img, rootmnt, readonly=False)
    if 'macho' in stages:
        mf.stage_macho(a, rootmnt)
    if 'cache' in stages:
        mf.stage_cache(a, rootmnt)
    table_path = os.path.join(work, 'owners.tsv')
    if 'tweaks' in stages:
        table = mf.load_map(table_path)
        stage_tweaks(a, rootmnt, table)
        mf.write_map(table, table_path)
    if 'seal' in stages:
        subprocess.run(['sync'])
        r = rplat.detach(rootmnt)
        if r.returncode:
            sys.exit('detach failed: ' + r.stderr)
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'hfsroot_owners.py'), img, '--map', table_path,
                        '--default-root'], check=True)
        rc, text = rplat.fsck(img)
        log('fsck rc', rc, text.strip()[-400:])
        if rc:
            sys.exit('fsck reports errors')
        write_blocks(img)
        log('done:', img)


if __name__ == '__main__':
    main()

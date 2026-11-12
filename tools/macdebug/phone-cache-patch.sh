#!/bin/zsh
# phone-cache-patch.sh NAME VA=OLD:NEW [VA=OLD:NEW ...]
# Patch instruction words in the PHONE's dyld cache (/System/Library/dyld/...) over SSH: locate the cache file and
# its signature in the Mac copy (/Volumes/DEEZNUTS/mac27-study/cache-pacstrip, pages must match the phone's),
# fetch the phone's signature blob, compute the new page hashes (dsc_patch_remote.py checks the page matches),
# back up the touched 16 KiB pages and the whole signature blob to /var/tmp on the phone, write, sync.
# The script is kept as tools/macdebug/patches-27.2/NAME.sh. Takes effect for new mappings: reboot after.
set -eu
HERE=${0:A:h}
NAME=${1:?name}; shift
LOCAL=${PHONE_CACHE_LOCAL:-/Volumes/DEEZNUTS/mac27-study/cache-pacstrip}
SSHO=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=4 -o BatchMode=yes)
T=$(mktemp -d)
read FILE SIGOFF SIGSIZE PAGES < <(python3 -I - $LOCAL "$@" <<'EOF'
import glob, os, struct, sys
d = sys.argv[1]
res = None
pages = set()
for arg in sys.argv[2:]:
    va = int(arg.split('=')[0], 16)
    for f in sorted(glob.glob(os.path.join(d, 'dyld_shared_cache_arm64e*'))):
        if any(s in f for s in ('.map', '.atlas')):
            continue
        hdr = open(f, 'rb').read(0x200)
        if not hdr.startswith(b'dyld_v1'):
            continue
        moff, mcnt = struct.unpack_from('<II', hdr, 0x10)
        so, ss = struct.unpack_from('<QQ', hdr, 0x28)
        maps = [struct.unpack_from('<QQQII', hdr if moff + 32 * mcnt <= 0x200 else open(f, 'rb').read(moff + 32 * mcnt), moff + 32 * i) for i in range(mcnt)]
        for a, size, foff, mp, ip in maps:
            if a <= va < a + size:
                cur = (os.path.basename(f), so, ss)
                if res not in (None, cur):
                    sys.exit('patches span two cache files')
                res = cur
                pages.add((foff + va - a) // 16384)
print(res[0], res[1], res[2], ','.join(str(p) for p in sorted(pages)))
EOF
)
F=/System/Library/dyld/$FILE
echo "file $FILE sig $SIGOFF+$SIGSIZE pages $PAGES"
# the signature blob (offset and size are 16 KiB multiples in these caches)
ssh "${SSHO[@]}" root@192.168.7.2 "dd if=$F bs=16384 skip=$((SIGOFF / 16384)) count=$(((SIGSIZE + 16383) / 16384)) 2>/dev/null" > $T/sig.raw
python3 -I -c "import sys; d=open('$T/sig.raw','rb').read(); open('$T/sig','wb').write(d[:$SIGSIZE])"
python3 -I $HERE/dsc_patch_remote.py $LOCAL $T/sig "$@" > $T/apply.sh
mkdir -p $HERE/patches-27.2
cp $T/apply.sh $HERE/patches-27.2/$NAME.sh
BK=/var/tmp/cachepatch-$NAME
ssh "${SSHO[@]}" root@192.168.7.2 "mkdir -p $BK && for p in ${PAGES//,/ }; do dd if=$F of=$BK/page-\$p bs=16384 skip=\$p count=1 2>/dev/null; done; dd if=$F of=$BK/sig bs=16384 skip=$((SIGOFF / 16384)) count=$(((SIGSIZE + 16383) / 16384)) 2>/dev/null; echo '$FILE $SIGOFF $PAGES' > $BK/info; cat > $BK/apply.sh; sh $BK/apply.sh" < $T/apply.sh
rm -rf "${T:?}"

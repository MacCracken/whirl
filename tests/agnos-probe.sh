#!/bin/bash
# agnos-probe.sh — run tests/agnos_probe.cyr on a real AGNOS kernel under QEMU.
#
# Roadmap A2: the agnos smoke (agnos/scripts/smoke/whirl-smoke.sh) drives three
# typed commands, so three #ifdef CYRIUS_TARGET_AGNOS regions ship unexecuted.
# This runs the probe that covers them, and settles roadmap B3.
#
# WHY IT DOES NOT USE THE KEYBOARD: the agnos smoke types commands into agnsh
# through a USB-xHCI HID that drops characters — it retries, and judges only
# attempts whose command line echoed intact. That is the right design when you
# need a shell. Here we do not: the probe takes no input and prints everything
# it finds. So it is staged AS /bin/agnsh in a THROWAWAY copy of the rootfs,
# which makes kybernet exec it directly at boot. No keyboard, no retries, no
# typos, and a deterministic pass/fail. The real rootfs is never modified.
#
# Structure (image build, OVMF discovery, QEMU invocation) follows
# agnos/scripts/smoke/whirl-smoke.sh so the two stay recognisably the same shape.
#
# Requires: qemu-system-x86_64, OVMF, parted, mtools, sgdisk, mkfs.ext2, python3.
# Needs sibling checkouts: ../agnos (built kernel + rootfs), ../gnoboot (built).
#
#   usage: tests/agnos-probe.sh [--keep]
#
# Exit 0 if the probe reported zero failures, 1 otherwise.
set -u

WHIRL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGNOS_ROOT="${AGNOS_ROOT:-$WHIRL_ROOT/../agnos}"
GNOBOOT_ROOT="${GNOBOOT_ROOT:-$WHIRL_ROOT/../gnoboot}"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

OVMF_CODE_CANDIDATES="/usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/edk2/x64/OVMF_CODE.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/OVMF/OVMF_CODE_4M.fd"
OVMF_VARS_CANDIDATES="/usr/share/edk2/x64/OVMF_VARS.4m.fd /usr/share/edk2/x64/OVMF_VARS.fd /usr/share/OVMF/OVMF_VARS.fd /usr/share/OVMF/OVMF_VARS_4M.fd"
OVMF_CODE=""; for c in $OVMF_CODE_CANDIDATES; do [ -f "$c" ] && { OVMF_CODE="$c"; break; }; done
OVMF_VARS_SRC=""; for c in $OVMF_VARS_CANDIDATES; do [ -f "$c" ] && { OVMF_VARS_SRC="$c"; break; }; done
{ [ -z "$OVMF_CODE" ] || [ -z "$OVMF_VARS_SRC" ]; } && { echo "ERROR: OVMF not found"; exit 1; }

for tool in qemu-system-x86_64 parted mformat mmd mcopy sgdisk mkfs.ext2 dd python3 cyrius; do
    command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: missing tool '$tool'"; exit 1; }
done

GNOBOOT="$GNOBOOT_ROOT/build/BOOTX64.EFI"
AGNOS="$AGNOS_ROOT/build/agnos"
SRC_ROOTFS="$AGNOS_ROOT/build/rootfs"
[ -f "$GNOBOOT" ]   || { echo "ERROR: gnoboot not built at $GNOBOOT"; exit 1; }
[ -f "$AGNOS" ]     || { echo "ERROR: agnos kernel not built at $AGNOS"; exit 1; }
[ -d "$SRC_ROOTFS" ] || { echo "ERROR: agnos rootfs not staged at $SRC_ROOTFS"; exit 1; }

WORK="$WHIRL_ROOT/build/agnos-probe"; rm -rf "$WORK"; mkdir -p "$WORK"
IMG="$WORK/agnos-probe.img"; SER="$WORK/serial.log"; MON="/tmp/whirl-agnos-probe-mon.sock"

echo "=== building the probe (--agnos) ==="
# cyrius writes progress to stderr, so 2>&1 is load-bearing: without it the
# pipeline sees an empty stdout and the guard fires on a successful build.
if ! ( cd "$WHIRL_ROOT" && CYRIUS_DCE=1 cyrius build --agnos tests/agnos_probe.cyr build/whirl-agnos-probe ) 2>&1 \
     | grep -E "^OK$|error" ; then
    echo "ERROR: probe build failed"; exit 1
fi

echo "=== staging a throwaway rootfs (probe AS /bin/agnsh) ==="
# A COPY. The probe replaces agnsh only in this copy, so the agnos repo's staged
# rootfs — which the real smoke depends on — is left exactly as it was.
ROOTFS="$WORK/rootfs"
cp -a "$SRC_ROOTFS" "$ROOTFS"
cp "$WHIRL_ROOT/build/whirl-agnos-probe" "$ROOTFS/bin/agnsh"
echo "  /bin/agnsh <- whirl-agnos-probe ($(stat -c%s "$ROOTFS/bin/agnsh") bytes)"
# A real system has one; the agnos rootfs does not. The probe writes its scratch
# files to / for that reason, but create it anyway so the image is less surprising.
mkdir -p "$ROOTFS/tmp"
[ -f "$ROOTFS/etc/ssl/cert.pem" ] \
    && echo "  trust store present: $(stat -c%s "$ROOTFS/etc/ssl/cert.pem") bytes" \
    || echo "  WARNING: no /etc/ssl/cert.pem staged — the ca-load probe will report FAIL"

PART_OFFSET=$(( 33 * 1048576 )); PART_BYTES=$(( 95 * 1048576 )); PART_BLOCKS=$(( PART_BYTES / 4096 ))
EXT2_FEATURES="${EXT2_FEATURES:-^resize_inode,^dir_index,^metadata_csum,^64bit,^uninit_bg}"

echo "=== building disk image ==="
dd if=/dev/zero of="$IMG" bs=1M count=128 status=none
parted -s "$IMG" mklabel gpt \
    mkpart ESP fat32 1MiB 33MiB set 1 esp on \
    mkpart agnos-fs ext2 33MiB 100MiB
sgdisk -t 2:8300 "$IMG" >/dev/null
mformat -i "$IMG"@@1048576 -F
mmd -i "$IMG"@@1048576 ::EFI ::EFI/BOOT ::boot
mcopy -i "$IMG"@@1048576 "$GNOBOOT" ::EFI/BOOT/BOOTX64.EFI
mcopy -i "$IMG"@@1048576 "$AGNOS" ::boot/agnos
mkfs.ext2 -F -q -L AGNOS-PROBE -b 4096 -m 0 -O "$EXT2_FEATURES" \
    -d "$ROOTFS" -E offset=$PART_OFFSET "$IMG" $PART_BLOCKS

# --- self-signed TLS server for the B3 negative check -------------------------
# Under SLIRP the guest reaches this host at 10.0.2.2, so a server here is a
# reachable bad-cert endpoint for the guest — the public *.badssl.com hosts are
# NOT reachable from this network, and a probe that cannot connect proves
# nothing. The cert NAMES 10.0.2.2, so a rejection is attributable to the
# untrusted issuer rather than a hostname mismatch.
BADSSL_PORT=18443
BADPID=""
if command -v openssl >/dev/null 2>&1; then
    openssl req -x509 -newkey rsa:2048 -keyout "$WORK/bad-key.pem" -out "$WORK/bad-cert.pem" \
        -days 2 -nodes -subj "/CN=10.0.2.2" -addext "subjectAltName=IP:10.0.2.2" >/dev/null 2>&1
    if [ -f "$WORK/bad-cert.pem" ]; then
        openssl s_server -quiet -cert "$WORK/bad-cert.pem" -key "$WORK/bad-key.pem" \
            -accept "$BADSSL_PORT" -naccept 4 -www >/dev/null 2>&1 &
        BADPID=$!
        sleep 1
        echo "  self-signed server up on :$BADSSL_PORT (guest sees 10.0.2.2:$BADSSL_PORT)"
    fi
fi
[ -z "$BADPID" ] && echo "  WARNING: no self-signed server — the B3 negative check is inconclusive"

cp "$OVMF_VARS_SRC" "$WORK/vars.fd"; chmod +w "$WORK/vars.fd"; : > "$SER"; rm -f "$MON"
KVM_ARGS="-cpu max"; [ -e /dev/kvm ] && KVM_ARGS="-enable-kvm -cpu host"

echo "=== booting QEMU ($( [ -e /dev/kvm ] && echo KVM || echo TCG )) ==="
qemu-system-x86_64 -machine q35 -m 512M $KVM_ARGS \
    -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
    -drive "if=pflash,format=raw,file=$WORK/vars.fd" \
    -drive "file=$IMG,format=raw,if=none,id=disk0" \
    -device "nvme,drive=disk0,serial=AGNOS-PROBE" \
    -netdev "user,id=u1" -device "virtio-net-pci,netdev=u1" \
    -serial "file:$SER" -display none -no-reboot \
    -monitor "unix:$MON,server,nowait" >/dev/null 2>&1 &
QPID=$!

# Wait for the probe to finish (PROBE: END) or give up. Nothing is typed — the
# probe is PID 1's exec target, so it starts on its own and runs to completion.
python3 - "$SER" <<'PYEOF'
import sys, time
SER = sys.argv[1]
def ser():
    try: return open(SER, "rb").read().decode("latin1")
    except OSError: return ""
for _ in range(600):          # up to 300s — the B3 handshakes add real time
    d = ser()
    if "PROBE: END" in d: break
    time.sleep(0.5)
PYEOF

sleep 1; kill "$QPID" 2>/dev/null; wait "$QPID" 2>/dev/null
[ -n "$BADPID" ] && { kill "$BADPID" 2>/dev/null; wait "$BADPID" 2>/dev/null; }

echo ""
echo "=== probe output ==="
grep -a '^PROBE:' "$SER" | sed 's/^/  /'

echo ""
echo "=== verdict ==="
rc=0
if ! grep -qa 'PROBE: END' "$SER"; then
    echo "  FAIL: the probe did not run to completion (no 'PROBE: END' on the console)"
    echo "        the binary may not have exec'd — check $SER"
    rc=1
else
    FAILS="$(grep -a '^PROBE: FAILURES' "$SER" | tail -1 | awk '{print $3}')"
    NPASS="$(grep -ca '^PROBE: PASS' "$SER")"
    if [ "${FAILS:-1}" = "0" ]; then
        echo "  PASS: probe completed with 0 failures ($NPASS checks passed)"
    else
        echo "  FAIL: probe reported $FAILS failure(s)"
        grep -a '^PROBE: FAIL' "$SER" | sed 's/^/        /'
        rc=1
    fi
    # B3 is a question, not a gate — surface the answer either way.
    grep -aE 'b3-verdict|b3-good|b3-bad' "$SER" \
        | sed 's/^PROBE: INFO /  B3: /; s/^PROBE: PASS /  B3 PASS: /; s/^PROBE: FAIL /  B3 FAIL: /'
fi
echo "  full serial: $SER"
[ $KEEP -eq 0 ] && rm -rf "$ROOTFS" "$IMG"
exit $rc

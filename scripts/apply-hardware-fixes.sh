#!/bin/bash
# Detect hardware model and write model-specific kernel parameter overrides to
# a GRUB drop-in so they survive kernel/GRUB updates without touching the main
# /etc/default/grub file.

set -e

MODEL=$(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null || true)
VENDOR=$(cat /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null || true)

GRUB_D="/etc/default/grub.d"
FIXES_FILE="$GRUB_D/kramden-hardware-fixes.cfg"

mkdir -p "$GRUB_D"
rm -f "$FIXES_FILE"

EXTRA_PARAMS=""

# Dell Latitude 7390: two kernel-level boot hang sources affect this model.
#
# 1. nvme_core.default_ps_state=0 — NVMe drives (Samsung PM981, Toshiba KBG30)
#    use APST (Autonomous Power State Transition). During boot the drive enters
#    a deep low-power state the kernel cannot wake quickly enough, stalling the
#    Plymouth spinner indefinitely.
#
# 2. i915.enable_psr=0 — Intel UHD 620 Panel Self Refresh (PSR) causes the
#    i915 KMS driver to freeze waiting on a display handshake that never
#    completes. Symptom: Dell firmware logo persists in the centre, static
#    Ubuntu logo appears at the bottom, no animation.
if echo "$VENDOR" | grep -qi "dell" && echo "$MODEL" | grep -qi "Latitude 7390"; then
    echo "Detected Dell Latitude 7390 — applying NVMe APST and i915 PSR fixes"
    EXTRA_PARAMS="nvme_core.default_ps_state=0 i915.enable_psr=0"
fi

if [ -n "$EXTRA_PARAMS" ]; then
    {
        echo "# Written by kramden-provision for ${VENDOR} ${MODEL}"
        echo "GRUB_CMDLINE_LINUX_DEFAULT=\"\$GRUB_CMDLINE_LINUX_DEFAULT $EXTRA_PARAMS\""
    } > "$FIXES_FILE"
    update-grub
    echo "Hardware fix applied: $EXTRA_PARAMS"
else
    echo "No hardware-specific fixes required for this model."
fi

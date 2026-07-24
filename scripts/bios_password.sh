#!/bin/bash

echo "Checking for BIOS Password"
lshw_admin_state=$(lshw -c system 2>/dev/null | grep configuration | grep -oE 'administrator_password=(enabled|disabled)' | head -n1 | cut -d= -f2)
admin_pass=""
if [ "$lshw_admin_state" = "enabled" ]; then
    admin_pass="enabled"
fi
dell_admin_pass=""
if [ -x "/opt/dell/dcc/cctk" ]; then
    # cctk has no read-only password query (--PasswordLock is a
    # different feature; --setuppwd/--syspwd are setters that
    # require a value). Probing with a write reveals whether an
    # admin password is required: per Dell's CCTK error code
    # reference, codes 149/152/180/191 all mean "setup/admin
    # password required to change this setting". Exit 65 ("command
    # sub-function disabled or unavailable") is unrelated to
    # password state and must not be treated as a password signal.
    #
    # --tpmppiclearoverride is unsupported on some older platforms
    # (e.g. Latitude E7250), where it always exits 65 regardless of
    # password state, making it useless as a probe there. --PropOwnTag
    # is supported far more broadly (it's used fleet-wide in dell.sh),
    # so probe it instead by re-writing its current value — a no-op
    # when the write succeeds.
    current_owner=$(/opt/dell/dcc/cctk --PropOwnTag 2>/dev/null | awk -F= '{print $2}')
    sudo /opt/dell/dcc/cctk --PropOwnTag="$current_owner" >/dev/null 2>&1
    case $? in
        65|149|152|180|191) dell_admin_pass="enabled" ;;
    esac
fi

hp_admin_pass=""
hp_unreliable=""
vendor=$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null)
if [[ $vendor =~ "HP" || $vendor =~ "Hewlett" ]]; then
    modprobe hp-bioscfg 2>/dev/null
    auth_dir=/sys/class/firmware-attributes/hp-bioscfg/authentication
    if [ -d "$auth_dir" ]; then
        for f in "$auth_dir"/*/is_enabled; do
            [ -r "$f" ] || continue
            if ! val=$(cat "$f" 2>/dev/null); then
                hp_unreliable=1
                continue
            fi
            if [ "$val" = "1" ]; then
                hp_admin_pass="enabled"
                break
            fi
        done
        # The hp-bioscfg driver creates corrupted entries (e.g. names
        # containing \r) on some HP firmware, where is_enabled lies and
        # reads of sibling attributes return I/O errors. If we see any
        # such entry and didn't already find an is_enabled=1, detection
        # is unreliable on this machine.
        if [ -z "$hp_admin_pass" ]; then
            for d in "$auth_dir"/*/; do
                [ -d "$d" ] || continue
                name=$(basename "$d")
                if ! [[ "$name" =~ ^[A-Za-z0-9_]+$ ]] || ! cat "$d/role" >/dev/null 2>&1; then
                    hp_unreliable=1
                    break
                fi
            done
        fi
    fi
fi

if [[ ${#admin_pass} > 0 || ${#dell_admin_pass} > 0 || ${#hp_admin_pass} > 0 ]];
then
    echo "BIOS Password enabled"
    exit 1
else
    # If lshw could read the SMBIOS Hardware Security table and saw
    # administrator_password=disabled, trust that — it's an
    # authoritative "no password set" signal from firmware and should
    # override the hp-bioscfg malformed-entries heuristic.
    if [ -n "$hp_unreliable" ] && [ "$lshw_admin_state" != "disabled" ]; then
        echo "WARNING: HP BIOS password state could not be determined reliably on this firmware (hp-bioscfg exposed malformed authentication entries). Verify manually via F10 Setup." >&2
    fi
    echo "BIOS Password disabled"
fi

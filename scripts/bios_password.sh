#!/bin/bash

echo "Checking for BIOS Password"
admin_pass=$(lshw -c system|grep configuration|grep administrator_password=enabled)
if [ -x "/opt/dell/dcc/cctk" ]; then
    dell_admin_pass=$(/opt/dell/dcc/cctk --PasswordLock | grep Enabled)
else
    dell_admin_pass=""
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
    if [ -n "$hp_unreliable" ]; then
        echo "WARNING: HP BIOS password state could not be determined reliably on this firmware (hp-bioscfg exposed malformed authentication entries). Verify manually via F10 Setup." >&2
    fi
    echo "BIOS Password disabled"
fi

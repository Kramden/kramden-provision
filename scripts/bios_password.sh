#!/bin/bash

echo "Checking for BIOS Password"
admin_pass=$(lshw -c system|grep configuration|grep administrator_password=enabled)
if [ -x "/opt/dell/dcc/cctk" ]; then
    dell_admin_pass=$(/opt/dell/dcc/cctk --PasswordLock | grep Enabled)
else
    dell_admin_pass=""
fi

if [[ ${#admin_pass} > 0 || ${#dell_admin_pass} > 0 ]];
then
    echo "BIOS Password enabled"
    exit 1
else
    echo "BIOS Password disabled"
fi

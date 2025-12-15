#!/bin/bash

echo "Checking for BIOS Password"
admin_pass=$(lshw -c system|grep configuration|grep administrator_password=enabled)
if [[ ${#admin_pass} > 0 ]];
then
    echo "BIOS Password enabled"
    exit 1
else
    echo "BIOS Password disabled"
fi

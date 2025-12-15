#!/bin/bash

echo "Checking for Asset Info"

declare -i ret
ret=0
vendor=$(cat /sys/devices/virtual/dmi/id/sys_vendor)
if [[ $vendor =~ "HP" ]];
then
    echo "Checking for HP Asset Tags"
    # Get product serial needed to strip from asset tag
    serial=$(cat /sys/devices/virtual/dmi/id/product_serial)
    rawtags=$(cat /sys/firmware/efi/efivars/HP_TAGS-fb3b9ece-4aba-4933-b49d-b4d67d892351 | tr -d '\0')
    # strip leading serial from tag
    tags=${rawtags/$serial/}
    # Check for greater than 1 because of null terminated variable
    if [[ ${#tags} > 1 ]];
    then
        echo "HP Tags found"
        echo "Tag: $tags"
        ret=1
    else
        echo "HP Tags not found"
    fi
elif [[ $vendor =~ "Dell" ]];
then
    echo "Checking for Dell Asset Tag"
    #tags=$(cat /sys/devices/virtual/dmi/id/chassis_asset_tag)
    asset=$(/opt/dell/dcc/cctk --Asset | awk -F = '{print $2}')
    # Check for greater than 1 because of null terminated variable
    if [[ ${#asset} > 1 ]];
    then
        echo "Dell Asset Tags found"
        echo "Asset Tag: $asset"
        echo "Clearing Asset Tag"
        /opt/dell/dcc/cctk --Asset= > /dev/null
        asset=$(/opt/dell/dcc/cctk --Asset | awk -F = '{print $2}')
        if [[ ${#asset} > 1 ]];
        then
            echo "Failed to clear Dell Asset Tag"
            ret=1
        fi
    else
        echo "Dell Asset Tags not found"
    fi
    echo "Checking for Dell Ownership Tag"
    ownership=$(/opt/dell/dcc/cctk --PropOwnTag | awk -F = '{print $2}')
    # Check for greater than 1 because of null terminated variable
    if [[ ${#ownership} > 1 ]];
    then
        echo "Dell Ownership Tag found"
        echo "Ownership Tag: $ownership"
        echo "Clearing Ownership Tag"
        /opt/dell/dcc/cctk --PropOwnTag= >/dev/null
        ownership=$(/opt/dell/dcc/cctk --PropOwnTag | awk -F = '{print $2}')
        if [[ ${#ownership} > 1 ]];
        then
            echo "Failed to clear Dell Ownership Tag"
            ret=1
        fi
    else
        echo "Dell Ownership Tag not found"
    fi
fi

# Exit with error
if (( ret != 0 ));
then
    echo "Failed"
    exit 1
fi

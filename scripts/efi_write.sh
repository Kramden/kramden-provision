#!/bin/bash

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# Define a valid GUID and a variable name
GUID="9a8e2042-75d4-4d70-9890-6a8437367c1f"
VAR_NAME="${GUID}-KramdenNumber"

# Define the value
VAR_VALUE=$1

# Create a temporary file to hold the value
TEMP_FILE=$(mktemp)

# Write the value to the temporary file
echo -n "$VAR_VALUE" > "$TEMP_FILE"

# Write the EFI variable
if efivar --write --name="$VAR_NAME" --data="$TEMP_FILE"; then
    echo "EFI variable '$VAR_NAME' written successfully with value '$VAR_VALUE'."
else
    echo "Failed to write EFI variable '$VAR_NAME'."
fi

# Clean up the temporary file
rm -f "$TEMP_FILE"

#!/bin/bash

# Check if the variable name is provided as an argument
if [ $# -ne 1 ]; then
    echo "Usage: $0 <VariableName>"
    exit 1
fi

# Define the variable name from the argument
VAR_NAME="$1"

# List all EFI variables and check if the named variable exists
if efivar -l | grep -q "$VAR_NAME"; then
    # Get the corresponding filename
    UUID=$(ls /sys/firmware/efi/efivars | grep "$VAR_NAME" | head -n 1)
    if [ -n "$UUID" ]; then
        # Read the EFI variable
        cat "/sys/firmware/efi/efivars/$UUID"
    else
        echo "Variable $VAR_NAME not found."
    fi
else
    echo "EFI variable $VAR_NAME does not exist."
fi

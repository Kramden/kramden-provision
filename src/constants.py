deb_packages = [
    "kramden-overrides",
    "kramden-desktop",
    "kramden-device",
    "libreoffice-writer",
]
snap_packages = [
    "frogsquash",
    "gnome-2048",
    "gnome-chess",
    "gnome-nibbles",
    "gnome-weather",
    "iagno",
    "mc-installer",
    "quadrapassel",
    "snap-store",
    "spotify",
    "vlc",
    "zoom-client",
]

# SMBIOS chassis type mapping (from DMTF SMBIOS specification)

CHASSIS_TYPE_MAP = {
    # Desktop types
    3: "Desktop",  # Desktop
    4: "Desktop",  # Low Profile Desktop
    5: "Desktop",  # Pizza Box
    6: "Desktop",  # Mini Tower
    7: "Desktop",  # Tower
    15: "Desktop",  # Space-saving
    16: "Desktop",  # Lunch Box
    24: "Desktop",  # Sealed-case PC
    35: "Desktop",  # Mini PC
    36: "Desktop",  # Stick PC
    # Laptop types
    8: "Laptop",  # Portable
    9: "Laptop",  # Laptop
    10: "Laptop",  # Notebook
    14: "Laptop",  # Sub Notebook
    30: "Laptop",  # Tablet
    31: "Laptop",  # Convertible
    32: "Laptop",  # Detachable
    # All-In-One
    13: "All-In-One",
}

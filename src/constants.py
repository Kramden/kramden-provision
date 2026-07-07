from enum import Enum


class Brand(Enum):
    """Brand options available in the Sortly Brand dropdown."""

    GATEWAY = "Gateway"
    PANASONIC = "Panasonic"
    MICROSOFT = "Microsoft"
    REPUBLIC_OF_GAMERS = "Republic of Gamers"
    ALIENWARE = "Alienware"
    TOSHIBA = "Toshiba"
    RAZER = "Razer"
    GOOGLE = "Google"
    LG = "LG"
    APPLE = "Apple"
    DELL = "Dell"
    LENOVO = "Lenovo"
    HP = "HP"
    ASUS = "Asus"
    MSI = "MSI"
    SAMSUNG = "Samsung"
    ACER = "Acer"
    FRAMEWORK = "Framework"
    KRAMDEN_CUSTOM_BUILDS = "Kramden Custom Builds"
    OTHER = "Other"
    FUJITSU = "Fujitsu"
    SONY = "Sony"
    GETAC = "Getac"

    @classmethod
    def from_vendor(cls, vendor):
        """Map a raw hardware vendor string to a Brand, or None if unrecognized."""
        if not vendor:
            return None
        v = str(vendor).strip().lower()
        for prefixes, brand in _VENDOR_PREFIX_MAP:
            if v.startswith(prefixes):
                return brand
        return None


# Vendor string prefixes (lowercase) mapped to their Sortly brand. Sub-brands
# that ship their own DMI vendor (e.g. Alienware) are listed independently of
# their parent company.
_VENDOR_PREFIX_MAP = [
    (("republic of gamers",), Brand.REPUBLIC_OF_GAMERS),
    (("alienware",), Brand.ALIENWARE),
    # ASUSTeK COMPUTER INC., ASUSTek, ASUS
    (("asus",), Brand.ASUS),
    # HP Inc., Hewlett-Packard
    (("hp", "hewlett"), Brand.HP),
    (("dell",), Brand.DELL),
    (("lenovo",), Brand.LENOVO),
    (("microsoft",), Brand.MICROSOFT),
    # Micro-Star International, MSI
    (("msi", "micro-star"), Brand.MSI),
    (("acer",), Brand.ACER),
    (("apple",), Brand.APPLE),
    (("framework",), Brand.FRAMEWORK),
    (("fujitsu",), Brand.FUJITSU),
    (("gateway",), Brand.GATEWAY),
    (("getac",), Brand.GETAC),
    (("google",), Brand.GOOGLE),
    (("lg",), Brand.LG),
    (("panasonic",), Brand.PANASONIC),
    (("razer",), Brand.RAZER),
    (("samsung",), Brand.SAMSUNG),
    (("sony",), Brand.SONY),
    (("toshiba",), Brand.TOSHIBA),
]

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

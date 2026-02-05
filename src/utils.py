import psutil
import subprocess
import threading
import os
from constants import snap_packages, deb_packages
import gi

gi.require_version("Snapd", "2")
from gi.repository import Snapd, GLib
import apt
import dbus
import pyudev
import re
import json
import math


# Utility class for functions used throughout the app
class Utils:
    def __init__(self):
        self.model = ""
        self.vendor = ""
        self.serial = ""
        self.hostname = ""
        self.os = ""
        try:
            result = subprocess.run(
                ["sudo", "hostnamectl", "status", "--json=pretty"],
                capture_output=True,
                text=True,
                check=True,
            )
            json_output = result.stdout
            data = json.loads(json_output)
            self.hostname = data.get("StaticHostname", "")
            self.model = data.get("HardwareModel", "")
            self.vendor = data.get("HardwareVendor", "")
            # NOTE: Some Lenovo firmware is known to expose an incorrect or dummy
            # HardwareSerial via systemd-hostnamed / `hostnamectl` (for example,
            # all-zero values or "Not Available"). For Lenovo systems we therefore
            # intentionally skip the HardwareSerial reported by hostnamectl here and
            # rely instead on the DMI-based fallback below
            # (/sys/devices/virtual/dmi/id/*) to obtain a more reliable serial.
            if self.vendor.lower() != "lenovo":
                self.serial = data.get("HardwareSerial", "")
            self.os = data.get("OperatingSystemPrettyName", "")
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
            # If hostnamectl fails or returns invalid JSON, use empty defaults
            # The fallback logic below will still attempt to populate serial from DMI
            pass
        if not self.serial:
            serial_files = ["board_serial", "product_serial", "chassis_serial"]
            for serial_file in serial_files:
                try:
                    result = subprocess.run(
                        [
                            "sudo",
                            "cat",
                            os.path.join("/sys/devices/virtual/dmi/id/", serial_file),
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    contents = result.stdout
                    if contents.strip():
                        self.serial = contents.strip()
                        break
                except subprocess.CalledProcessError:
                    # If reading this serial file fails, try the next one
                    continue

    # Return the size of all detected necessary drives
    def get_disks(self):
        context = pyudev.Context()
        disks = {}
        for device in context.list_devices(subsystem="block", DEVTYPE="disk"):
            if not "loop" in device["DEVNAME"] and not re.search(
                r"sr[0-9]", device["DEVNAME"]
            ):
                if device.attributes.asint("removable") != 1:
                    disks[str(device["DEVNAME"])] = int(
                        round(device.attributes.asint("size") * 512 / 1024**3, 0)
                    )
        return disks

    # Return host name
    def get_hostname(self):
        return self.hostname

    # Set the system hostname
    def set_hostname(self, hostname):
        # Ensure hostname isn't empty
        if len(hostname) < 1:
            return False
        result = subprocess.run(["hostnamectl", "set-hostname", hostname])
        return result.returncode == 0

    # Set timezone and sync hardware clock
    def sync_clock(self):
        clock_sh = "/usr/share/kramden-provision/scripts/clock.sh"
        if self.file_exists_and_executable(clock_sh):
            result = subprocess.run(["sudo", clock_sh])
            return result.returncode == 0
        return False

    # Check if BIOS Password is set, returns True if set
    def has_bios_password(self):
        bios_password_sh = "/usr/share/kramden-provision/scripts/bios_password.sh"
        if self.file_exists_and_executable(bios_password_sh):
            result = subprocess.run(["sudo", bios_password_sh])
            return result.returncode != 0
        return False

    # Check if BIOS has Asset info, returns True if set
    def has_asset_info(self):
        asset_sh = "/usr/share/kramden-provision/scripts/asset.sh"
        if self.file_exists_and_executable(asset_sh):
            result = subprocess.run(["sudo", asset_sh])
            return result.returncode != 0
        return False

    # Check if Computrace/Absolute is activated in BIOS, returns True if activated
    def has_computrace_enabled(self):
        # Check firmware attributes exposed by Linux kernel
        # Works for Lenovo, Dell, and HP (with hp-bioscfg driver on Linux 6.x+)
        result = self._check_computrace_firmware_attrs()
        if result is not None:
            return result

        # Fallback to Dell-specific check using cctk tool
        if self.vendor.lower() == "dell":
            result = self._check_computrace_dell_cctk()
            if result is not None:
                return result

        # Fallback to check dmidecode for Computrace/Absolute entries
        # This works across all vendors by reading SMBIOS tables
        result = self._check_computrace_dmidecode()
        if result is not None:
            return result

        return None  # Cannot determine

    def _check_computrace_firmware_attrs(self):
        """Check firmware-attributes sysfs interface (Lenovo, Dell, HP with proper drivers)."""
        # Attributes ending in "Activation" use Enable/Disable to indicate activation state
        # Other attributes use Activate/Activated to indicate activation state
        activation_attrs = [
            "AbsolutePersistenceModuleActivation",
            "ComputraceModuleActivation",
        ]
        standard_attrs = [
            "Computrace",
            "Absolute",
        ]
        firmware_attrs_base = "/sys/class/firmware-attributes"
        try:
            if not os.path.isdir(firmware_attrs_base):
                return None
            for provider in os.listdir(firmware_attrs_base):
                attrs_dir = os.path.join(firmware_attrs_base, provider, "attributes")
                if not os.path.isdir(attrs_dir):
                    continue
                # Check activation-style attributes first (Enable = activated)
                for attr_name in activation_attrs:
                    current_value_path = os.path.join(
                        attrs_dir, attr_name, "current_value"
                    )
                    if os.path.exists(current_value_path):
                        result = subprocess.run(
                            ["sudo", "cat", current_value_path],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            value = result.stdout.strip().lower()
                            # For *Activation attributes, Enable means activated
                            if value in ["enable", "enabled"]:
                                return True
                            elif value in [
                                "disable",
                                "disabled",
                                "permanentlydisable",
                                "permanently disable",
                            ]:
                                return False
                # Check standard attributes (Activate = activated)
                for attr_name in standard_attrs:
                    current_value_path = os.path.join(
                        attrs_dir, attr_name, "current_value"
                    )
                    if os.path.exists(current_value_path):
                        result = subprocess.run(
                            ["sudo", "cat", current_value_path],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            value = result.stdout.strip().lower()
                            if value in ["activate", "activated"]:
                                return True
                            elif value in [
                                "enable",
                                "enabled",
                                "disable",
                                "disabled",
                                "permanentlydisable",
                                "permanently disable",
                            ]:
                                return False
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    def _check_computrace_dell_cctk(self):
        """Check Dell systems using cctk tool."""
        cctk_path = "/opt/dell/dcc/cctk"
        if not os.path.exists(cctk_path):
            return None
        try:
            # Try common Dell attribute names for Computrace/Absolute
            for attr in ["Computrace", "AbsoluteEnable", "Absolute"]:
                result = subprocess.run(
                    ["sudo", cctk_path, f"--{attr}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    output = result.stdout.strip().lower()
                    # cctk typically outputs "attribute=value"
                    if "=activate" in output or "=activated" in output:
                        return True
                    elif "=disabled" in output or "=deactivate" in output or "=enabled" in output:
                        return False
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    def _check_computrace_dmidecode(self):
        """Check SMBIOS tables via dmidecode for Computrace/Absolute settings."""
        try:
            # Check BIOS information (type 0) and System Configuration Options (type 12)
            # for Computrace-related strings
            result = subprocess.run(
                ["sudo", "dmidecode"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return None

            output = result.stdout.lower()

            # Look for Computrace/Absolute entries in dmidecode output
            # Pattern: lines containing computrace or absolute followed by activated/disabled
            lines = output.split("\n")
            for i, line in enumerate(lines):
                if "computrace" in line or "absolute" in line:
                    # Check this line and nearby lines for status
                    context = " ".join(lines[max(0, i - 2) : min(len(lines), i + 3)])
                    if any(
                        status in context
                        for status in ["activated", "active"]
                    ):
                        # Make sure it's not "disabled" or "deactivated"
                        if "disabled" not in context and "deactivated" not in context:
                            return True
                    if any(
                        status in context
                        for status in ["disabled", "deactivated", "inactive"]
                    ):
                        return False
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    # Get vendor
    def get_vendor(self):
        return self.vendor

    # Get model
    def get_model(self):
        return self.model

    # Get serial
    def get_serial(self):
        return self.serial

    # Get OS
    def get_os(self):
        return self.os

    # Get installer
    def get_installer(self):
        return ""

    # Return MemTotal, rounded to nearest standard RAM size
    def get_mem(self):
        mem_info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                if line.strip():
                    key, value = line.split(":", 1)
                    mem_info[key.strip()] = value.strip()
        # MemTotal is in KiB (labeled as kB), convert to GiB
        mem_kib = int(mem_info["MemTotal"].split(" ")[0])
        mem_gib = mem_kib / 1024**2
        # Round to nearest standard RAM size to account for reserved memory (video, etc.)
        return str(self._round_to_standard_ram(mem_gib))

    def _round_to_standard_ram(self, mem_gib):
        """Round memory to nearest standard RAM size when within tolerance."""
        # Common RAM sizes in GiB
        standard_sizes = [4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
        # Only round to a standard size when within 10% of that size
        for size in standard_sizes:
            lower_bound = size * 0.9
            upper_bound = size * 1.1
            if lower_bound <= mem_gib <= upper_bound:
                return size
        # For very large RAM beyond our largest standard size, round up to nearest 64 GiB
        if mem_gib > standard_sizes[-1]:
            return math.ceil(mem_gib / 64) * 64
        # Otherwise, return truncated GB value (no rounding to a standard size)
        return int(mem_gib)

    # Return CPU model info
    def get_cpu_info(self):
        cpu_info = {}
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.strip():
                    key, value = line.split(":", 1)
                    cpu_info[key.strip()] = value.strip()

        return cpu_info["model name"]

    # Return discrete GPU info if found, otherwise None
    def get_discrete_gpu(self):
        # First check if a discrete GPU exists using lspci
        has_discrete = False
        has_nvidia = False
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Treat "discrete GPU present" as "more than one VGA/3D controller detected"
            controllers = []
            for line in result.stdout.splitlines():
                line_lower = line.lower()
                if "vga compatible controller" in line_lower or "3d controller" in line_lower:
                    controllers.append(line_lower)
                    # Check if this is an NVIDIA GPU (for PRIME offload settings)
                    if "nvidia" in line_lower:
                        has_nvidia = True
            has_discrete = len(controllers) > 1
        except (subprocess.CalledProcessError, OSError):
            pass

        if not has_discrete:
            return None

        # Check if NVIDIA proprietary driver is loaded (not nouveau)
        has_nvidia_proprietary = False
        if has_nvidia:
            # Check for /proc/driver/nvidia/version which only exists with proprietary driver
            has_nvidia_proprietary = os.path.exists("/proc/driver/nvidia/version")

        # Get friendly name using glxinfo with appropriate PRIME settings
        try:
            env = os.environ.copy()
            # For NVIDIA proprietary driver, use NVIDIA-specific PRIME offload variables
            if has_nvidia_proprietary:
                env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
                env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
            # Generic DRI_PRIME works for nouveau and AMD
            env["DRI_PRIME"] = "1"

            result = subprocess.run(
                ["glxinfo"],
                capture_output=True,
                text=True,
                env=env,
            )
            for line in result.stdout.splitlines():
                if "OpenGL renderer string:" in line:
                    renderer = line.split(":", 1)[1].strip()
                    return self._format_gpu_renderer(renderer)
        except (subprocess.CalledProcessError, OSError):
            pass

        return "Discrete GPU detected"

    def _format_gpu_renderer(self, renderer):
        """Clean up OpenGL renderer string for display."""
        # Handle zink Vulkan wrapper format: "zink Vulkan 1.4(NVIDIA RTX...)"
        zink_match = re.search(r"zink Vulkan [0-9.]+\((.+)\)", renderer)
        if zink_match:
            renderer = zink_match.group(1)
        # Remove driver suffix like "(NVIDIA_PROPRIETARY)" or " (NVIDIA_PROPRIETARY)"
        renderer = re.sub(r"\s*\([A-Z_]+\)\s*$", "", renderer)
        # Remove /PCIe/SSE2 suffix
        renderer = re.sub(r"/PCIe.*$", "", renderer)
        return renderer.strip()

    def check_snaps(self, packages):
        result = {}
        client = Snapd.Client()
        snaps_installed = [
            snap.get_name()
            for snap in client.get_snaps_sync(Snapd.GetAppsFlags.NONE, packages, None)
        ]
        for p in packages:
            if p in snaps_installed:
                result[p] = True
            else:
                result[p] = False
        return result

    def check_debs(self, packages):
        result = {}
        cache = apt.cache.Cache()
        cache.open(None)
        debs_installed = [p.name for p in cache if p.is_installed]
        for p in packages:
            if p in debs_installed:
                result[p] = True
            else:
                result[p] = False
        return result

    # Return battery capacity
    def get_battery_capacities(self):
        bus = dbus.SystemBus()
        upower = bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower")
        manager = dbus.Interface(upower, "org.freedesktop.UPower")

        # Get the list of all power devices
        devices = manager.EnumerateDevices()

        capacities = {}
        for device_path in devices:
            device = bus.get_object("org.freedesktop.UPower", device_path)
            device_properties = dbus.Interface(
                device, "org.freedesktop.DBus.Properties"
            )
            device_type = device_properties.Get("org.freedesktop.UPower.Device", "Type")

            # UPower.DeviceType for battery is 2
            if device_type == 2:
                # display number should be an int, but float always has something after the decimal e.g. "80.0"
                capacity = int(
                    round(
                        float(
                            device_properties.Get(
                                "org.freedesktop.UPower.Device", "Capacity"
                            )
                        ),
                        0,
                    )
                )
                model = device_properties.Get("org.freedesktop.UPower.Device", "Model")
                capacities[model] = capacity

        return capacities

    # Checks to see if registered with Landscape
    def is_registered(self):
        val = False
        if not os.environ["USER"] in ["osload", "finaltest", "owner"]:
            if os.path.isfile("/etc/landscape/client.conf") and os.access(
                "/etc/landscape/client.conf", os.R_OK
            ):
                command = ["landscape-config", "--is-registered"]
            else:
                command = ["pkexec", "landscape-config", "--is-registered"]
        else:
            command = ["sudo", "landscape-config", "--is-registered"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            val = result.returncode == 0
        except:
            pass
        return val

    # Register with landscape, returns True if successful
    def register_landscape(self, label=None, button=None, spinner=None, next_func=None):
        print("Utils:register_landscape")
        if button:
            button.set_sensitive(False)
        if spinner:
            spinner.start()
        if not os.environ["USER"] in ["osload", "finaltest", "owner"]:
            sudo = "pkexec"
        else:
            sudo = "sudo"

        command = [
            sudo,
            "landscape-config",
            "--silent",
            "--url",
            "https://landscape.kramden.org/message-system",
            "--ping-url",
            "https://landscape.kramden.org/ping",
            "--account-name",
            "standalone",
            "--computer-title",
            self.get_hostname(),
            "--script-users=ALL",
            "--access-group=global",
        ]
        thread = threading.Thread(
            target=self._run_subprocess,
            args=(command, label, button, spinner, next_func),
        )
        thread.start()

    def _run_subprocess(
        self, command, label=None, button=None, spinner=None, next_func=None
    ):
        print("Utils:_run_subprocess")
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            GLib.idle_add(self._update_label, label, stdout.decode(), stderr.decode())
        except Exception as e:
            GLib.idle_add(_update_label, label, f"Error: {e}", "")
        finally:
            GLib.idle_add(
                self._finish_run_subprocess, label, button, spinner, next_func
            )

    def _update_label(self, label, stdout, stderr):
        print("Utils:_update_label: " + stdout)
        label_text = ""
        if stdout:
            label_text += "Stdout:\n" + stdout
        if stderr:
            label_text += "\nStderr:\n" + stderr
        if label:
            label.set_label(label_text)
        return False

    def _finish_run_subprocess(
        self, label=None, button=None, spinner=None, next_func=None
    ):
        print("Utils:_finish_run_subprocess")
        if button:
            if self.is_registered():
                button.set_sensitive(False)
                if next_func:
                    next_func()
            else:
                button.set_sensitive(True)
        if spinner:
            spinner.stop()
        return False

    # Launch arbitrary app
    def launch_app(self, command):
        print("Utils:launch_app")
        try:
            subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
            )
        except:
            pass

    def file_exists_and_readable(self, filepath):
        return os.path.isfile(filepath) and os.access(filepath, os.R_OK)

    def file_exists_and_executable(self, filepath):
        return os.path.isfile(filepath) and os.access(filepath, os.X_OK)

    # Perform reset
    def complete_reset(self, stage):
        val = False
        print("Utils: complete_reset")
        script = f"/usr/share/kramden-provision/scripts/kramden-reset-{stage}"
        print("Utils: " + script)
        if self.file_exists_and_executable(script) and os.environ["USER"] in [
            "osload",
            "finaltest",
        ]:
            try:
                result = subprocess.run(
                    [script], capture_output=True, text=True, check=True
                )
                val = result.returncode == 0
            except:
                pass
        return val

    # get asset tags
    def get_asset_tags(self):
        asset_tag = None
        if "hp" in self.vendor.lower():
            print("Vendor is HP")
            try:
                with open(
                    "/sys/firmware/efi/efivars/HP_TAGS-fb3b9ece-4aba-4933-b49d-b4d67d892351",
                    "r",
                ) as f:
                    asset_tag = f.readline().strip()
            except Exception as e:
                print(f"Could not read HP asset tag: {e}")
        elif "dell" in self.vendor.lower():
            print("Vendor is Dell")
            if self.file_exists_and_executable("/opt/dell/dcc/cctk") and os.environ[
                "USER"
            ] in ["osload", "finaltest", "ubuntu"]:
                try:
                    result = subprocess.run(
                        ["/opt/dell/dcc/cctk", "--Asset"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    asset_tag = result.stdout.split("=")[1]
                except:
                    pass
        elif "lenovo" in self.vendor.lower():
            print("Vendor is Lenovo")
        else:
            print("Unknown Vendor")
        return asset_tag


if __name__ == "__main__":
    utils = Utils()
    vendor = utils.get_vendor()
    model = utils.get_model()
    asset_tags = utils.get_asset_tags()
    capacities = utils.get_battery_capacities()
    # for battery in capacities.keys():
    #    print(f"Battery {id + 1} Capacity: {capacity}%")
    print("Disk Capacity: " + str(utils.get_disks()) + " GB")
    print("CPU Model: " + utils.get_cpu_info())
    print("Snaps: " + str(utils.check_snaps(snap_packages)))
    print("Debs: " + str(utils.check_debs(deb_packages)))
    print("Vendor: " + utils.get_vendor())
    print("Model: " + utils.get_model())
    print("Serial: " + utils.get_serial())

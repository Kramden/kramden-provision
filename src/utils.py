import psutil
import subprocess
import threading
import os
from constants import snap_packages, deb_packages
import gi
gi.require_version('Snapd','2')
from gi.repository import Snapd, GLib
import apt
import dbus

# Utility class for functions used throughout the app
class Utils():
    def __init__(self):
        self.model = ""
        self.vender = ""
        self.hostname = ""
        self.os = ""
        result = subprocess.run(['hostnamectl', 'status'], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if "Hardware Model" in line:
                self.model = line.strip().split(':', 1)[1]
            elif "Hardware Vendor" in line:
                self.vender = line.strip().split(':', 1)[1]
            elif "Static hostname" in line:
                self.hostname = line.strip().split(':', 1)[1].strip()
            elif "Operating System" in line:
                self.os = line.strip().split(':', 1)[1]

    # Return size of the root drive
    def get_disk(self):
        return (str(int(psutil.disk_usage('/').total/ (1024 ** 3))))

    # Return host name
    def get_hostname(self):
        return self.hostname

    # Set the system hostname
    def set_hostname(self, hostname):
        # Ensure hostname isn't empty
        if len(hostname) < 1:
            return False
        result = subprocess.run(['hostnamectl', 'set-hostname', hostname])
        return result.returncode == 0

    # Get vender
    def get_vender(self):
        return self.vender

    # Get model
    def get_model(self):
        return self.model

    # Get OS
    def get_os(self):
        return self.os

    # Get installer
    def get_installer(self):
        return ""

    # Return MemTotal
    def get_mem(self):
        mem_info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                if line.strip():
                    key, value = line.split(':', 1)
                    mem_info[key.strip()] = value.strip()
        mem_size = int(mem_info['MemTotal'].split(" ")[0]) / 1000 ** 2
        return str(int(mem_size))

    # Return CPU model info
    def get_cpu_info(self):
        cpu_info = {}
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.strip():
                    key, value = line.split(':', 1)
                    cpu_info[key.strip()] = value.strip()

        return cpu_info['model name']

    def check_snaps(self, packages):
        result = {}
        client = Snapd.Client()
        snaps_installed = [snap.get_name() for snap in client.get_snaps_sync(Snapd.GetAppsFlags.NONE, packages, None)]
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
        upower = bus.get_object('org.freedesktop.UPower', '/org/freedesktop/UPower')
        manager = dbus.Interface(upower, 'org.freedesktop.UPower')

        # Get the list of all power devices
        devices = manager.EnumerateDevices()

        capacities = {}
        for device_path in devices:
            device = bus.get_object('org.freedesktop.UPower', device_path)
            device_properties = dbus.Interface(device, 'org.freedesktop.DBus.Properties')
            device_type = device_properties.Get('org.freedesktop.UPower.Device', 'Type')

            # UPower.DeviceType for battery is 2
            if device_type == 2:
                # display number should be an int, but float always has something after the decimal e.g. "80.0"
                capacity = int(round(float(device_properties.Get('org.freedesktop.UPower.Device', 'Capacity')), 0))
                model = device_properties.Get('org.freedesktop.UPower.Device', 'Model')
                capacities[model] = capacity

        return capacities

    # Checks to see if registered with Landscape
    def is_registered(self):
        val = False
        if not os.environ["USER"] in ["osload", "finaltest", "owner"]:
            if os.path.isfile("/etc/landscape/client.conf") and os.access("/etc/landscape/client.conf", os.R_OK):
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
            "--access-group=global"
                ]
        thread = threading.Thread(target=self._run_subprocess, args=(command, label, button, spinner, next_func))
        thread.start()

    def _run_subprocess(self, command, label=None, button=None, spinner=None, next_func=None):
        print("Utils:_run_subprocess")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            GLib.idle_add(self._update_label, label, stdout.decode(), stderr.decode())
        except Exception as e:
            GLib.idle_add(_update_label, label, f"Error: {e}", "")
        finally:
            GLib.idle_add(self._finish_run_subprocess, label, button, spinner, next_func)

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

    def _finish_run_subprocess(self, label=None, button=None, spinner=None, next_func=None):
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
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
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
        if self.file_exists_and_executable(script) and os.environ["USER"] in ["osload", "finaltest"]:
            try:
                result = subprocess.run([script], capture_output=True, text=True, check=True)
                val = result.returncode == 0
            except:
                pass
        return val

if __name__ == "__main__":
    utils = Utils()
    capacities = get_battery_capacities()
    for battery in capacities.keys():
        print(f"Battery {idx + 1} Capacity: {capacity}%")
    print("Disk Capacity: " + str(utils.get_disk()) + " GB")
    print("CPU Model: " + utils.get_cpu_info())
    print("Snaps: " + str(utils.check_snaps(snap_packages)))
    print("Debs: " + str(utils.check_debs(deb_packages)))
    print(f"Battery Capacity: {capacity}%")

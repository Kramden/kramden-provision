import psutil
import subprocess

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
                self.hostname = line.strip().split(':', 1)[1]
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

    # Get landscape_reg
    def get_landscape_reg(self):
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

if __name__ == "__main__":
    utils = Utils()
    print("Disk Capacity: " + str(utils.get_disk()) + " GB")
    print("CPU Model: " + utils.get_cpu_info())

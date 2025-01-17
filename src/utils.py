import psutil

# Utility class for functions used throughout the app
class Utils():
    def __init__(self):
        pass

    # Return size of the root drive
    def get_disk(self):
        return (str(int(psutil.disk_usage('/').total/ (1024 ** 3))))

    # Return host name
    def get_hostname(self):
        f = open('/etc/hostname', 'r')
        hostname = f.read()
        f.close()

        return hostname.rstrip()

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

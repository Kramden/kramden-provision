import psutil

# Utility class for functions used throughout the app
class Utils():
    def __init__(self):
        pass

    # Return size of the root drive
    def get_disks(self):
        return(psutil.disk_usage('/').total/ (1024 ** 3))

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
    print("Disk Capacity: " + str(utils.get_disks()) + " GB")
    print("CPU Model: " + utils.get_cpu_info())

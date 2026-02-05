import sys
import os
import unittest
import json
import subprocess
from unittest.mock import patch, mock_open, MagicMock
sys.path.insert(1, os.path.dirname(os.path.realpath(__file__))+"/../src/")
from utils import Utils

class TestUtils(unittest.TestCase):
    def setUp(self):
        # Mock the subprocess.run to return JSON formatted output
        hostnamectl_json = {
            "StaticHostname": "testhost",
            "OperatingSystemPrettyName": "Test OS 1.0",
            "HardwareVendor": "Test Vendor",
            "HardwareModel": "Test Model",
            "HardwareSerial": "TEST123"
        }
        self.hostnamectl_output = json.dumps(hostnamectl_json)
        self.mock_subproc_run = patch('subprocess.run').start()
        
        # Create a MagicMock for the result
        mock_result = MagicMock()
        mock_result.stdout = self.hostnamectl_output
        mock_result.returncode = 0
        self.mock_subproc_run.return_value = mock_result

        # Create a Utils instance
        self.utils = Utils()

    def tearDown(self):
        patch.stopall()

    def test_get_hostname(self):
        self.assertEqual(self.utils.get_hostname(), "testhost")

    @patch('subprocess.run')
    def test_set_hostname_success(self, mock_run):
        # Mock subprocess.run to simulate a successful call
        mock_run.return_value = MagicMock(returncode=0)

        # Call the function
        result = self.utils.set_hostname('new-hostname')

        # Assert that the function returns True
        self.assertTrue(result)

        # Assert that subprocess.run was called with the correct arguments
        mock_run.assert_called_with(['hostnamectl', 'set-hostname', 'new-hostname'])

    @patch('subprocess.run')
    def test_set_hostname_failure(self, mock_run):
        # Mock subprocess.run to simulate a failed call
        mock_run.return_value = MagicMock(returncode=1)

        # Call the function
        result = self.utils.set_hostname('new-hostname')

        # Assert that the function returns False
        self.assertFalse(result)

        # Assert that subprocess.run was called with the correct arguments
        mock_run.assert_called_with(['hostnamectl', 'set-hostname', 'new-hostname'])

    def test_get_os(self):
        self.assertEqual(self.utils.get_os(), "Test OS 1.0")

    def test_get_vendor(self):
        self.assertEqual(self.utils.get_vendor(), "Test Vendor")

    def test_get_model(self):
        self.assertEqual(self.utils.get_model(), "Test Model")

    def test_get_serial(self):
        self.assertEqual(self.utils.get_serial(), "TEST123")

    @patch('subprocess.run')
    def test_get_serial_lenovo_skips_hostnamectl(self, mock_run):
        # Test that Lenovo devices skip the serial from hostnamectl
        hostnamectl_json = {
            "StaticHostname": "lenovo-test",
            "OperatingSystemPrettyName": "Test OS 1.0",
            "HardwareVendor": "Lenovo",
            "HardwareModel": "ThinkPad",
            "HardwareSerial": "INVALID_SERIAL"
        }

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            mock_result = MagicMock()
            if 'hostnamectl' in cmd:
                mock_result.stdout = json.dumps(hostnamectl_json)
                mock_result.returncode = 0
                return mock_result
            else:
                # DMI fallback calls should fail
                import subprocess
                raise subprocess.CalledProcessError(1, cmd)

        mock_run.side_effect = subprocess_side_effect

        # Create Utils instance - serial should be empty since vendor is Lenovo
        # and DMI fallback will fail
        utils = Utils()

        # For Lenovo, serial from hostnamectl should be skipped
        # The DMI fallback also fails, so serial should be empty
        self.assertEqual(utils.get_serial(), "")

    @patch('utils.pyudev.Context')
    def test_get_disks(self, mock_context):
        # Create a mock device
        mock_device = MagicMock()
        mock_device.__getitem__ = MagicMock(side_effect=lambda key: '/dev/sda' if key == 'DEVNAME' else None)
        mock_device.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device.get = MagicMock(return_value=None)

        # Setup context to return our mock device
        mock_context_instance = MagicMock()
        mock_context_instance.list_devices.return_value = [mock_device]
        mock_context.return_value = mock_context_instance

        # 209715200 * 512 / 1024^3 = 100 GB
        result = self.utils.get_disks()
        self.assertEqual(result, {'/dev/sda': 100})

    @patch('utils.pyudev.Context')
    def test_get_disks_filters_dm_prefix(self, mock_context):
        """Test that devices with /dev/dm- prefix are filtered out."""
        # Create mock devices: one normal disk and one with dm- prefix
        mock_device_sda = MagicMock()
        mock_device_sda.__getitem__ = MagicMock(side_effect=lambda key: '/dev/sda' if key == 'DEVNAME' else None)
        mock_device_sda.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device_sda.get = MagicMock(return_value=None)

        mock_device_dm = MagicMock()
        mock_device_dm.__getitem__ = MagicMock(side_effect=lambda key: '/dev/dm-0' if key == 'DEVNAME' else None)
        mock_device_dm.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device_dm.get = MagicMock(return_value=None)

        # Setup context to return both devices
        mock_context_instance = MagicMock()
        mock_context_instance.list_devices.return_value = [mock_device_sda, mock_device_dm]
        mock_context.return_value = mock_context_instance

        # Only /dev/sda should be included, /dev/dm-0 should be filtered out
        result = self.utils.get_disks()
        self.assertEqual(result, {'/dev/sda': 100})

    @patch('utils.pyudev.Context')
    def test_get_disks_filters_mapper_path(self, mock_context):
        """Test that devices with /mapper/ in the path are filtered out."""
        # Create mock devices: one normal disk and one with /mapper/ in path
        mock_device_sda = MagicMock()
        mock_device_sda.__getitem__ = MagicMock(side_effect=lambda key: '/dev/sda' if key == 'DEVNAME' else None)
        mock_device_sda.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device_sda.get = MagicMock(return_value=None)

        mock_device_mapper = MagicMock()
        mock_device_mapper.__getitem__ = MagicMock(side_effect=lambda key: '/dev/mapper/vg-lv' if key == 'DEVNAME' else None)
        mock_device_mapper.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device_mapper.get = MagicMock(return_value=None)

        # Setup context to return both devices
        mock_context_instance = MagicMock()
        mock_context_instance.list_devices.return_value = [mock_device_sda, mock_device_mapper]
        mock_context.return_value = mock_context_instance

        # Only /dev/sda should be included, /dev/mapper/vg-lv should be filtered out
        result = self.utils.get_disks()
        self.assertEqual(result, {'/dev/sda': 100})

    @patch('utils.pyudev.Context')
    def test_get_disks_filters_dm_name_property(self, mock_context):
        """Test that devices with DM_NAME property are filtered out."""
        # Create mock devices: one normal disk and one with DM_NAME property
        mock_device_sda = MagicMock()
        mock_device_sda.__getitem__ = MagicMock(side_effect=lambda key: '/dev/sda' if key == 'DEVNAME' else None)
        mock_device_sda.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device_sda.get = MagicMock(return_value=None)

        mock_device_lvm = MagicMock()
        mock_device_lvm.__getitem__ = MagicMock(side_effect=lambda key: '/dev/sdb' if key == 'DEVNAME' else None)
        mock_device_lvm.attributes.asint = MagicMock(side_effect=lambda key: 0 if key == 'removable' else 209715200 if key == 'size' else 0)
        mock_device_lvm.get = MagicMock(side_effect=lambda key: 'vg-lv' if key == 'DM_NAME' else None)

        # Setup context to return both devices
        mock_context_instance = MagicMock()
        mock_context_instance.list_devices.return_value = [mock_device_sda, mock_device_lvm]
        mock_context.return_value = mock_context_instance

        # Only /dev/sda should be included, device with DM_NAME should be filtered out
        result = self.utils.get_disks()
        self.assertEqual(result, {'/dev/sda': 100})

    def test_get_mem_8gib_system(self):
    @patch('utils.Utils._get_installed_ram_from_dmi')
    def test_get_mem_8gib_system(self, mock_dmi):
        # Mock dmidecode to return None, forcing fallback to /proc/meminfo
        mock_dmi.return_value = None
        
        # Simulate 8 GiB system with ~7.3 GiB reported (reserved for video, etc.)
        # 7700000 KiB / 1024^2 = 7.34 GiB -> rounds to 8
        meminfo_content = "MemTotal:       7700000 kB"
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            self.assertEqual(self.utils.get_mem(), "8")

    @patch('utils.Utils._get_installed_ram_from_dmi')
    def test_get_mem_16gib_system(self, mock_dmi):
        # Mock dmidecode to return None, forcing fallback to /proc/meminfo
        mock_dmi.return_value = None
        
        # Simulate 16 GiB system with ~14.8 GiB reported
        # 15500000 KiB / 1024^2 = 14.78 GiB -> rounds to 16
        meminfo_content = "MemTotal:       15500000 kB"
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            self.assertEqual(self.utils.get_mem(), "16")

    def test_round_to_standard_ram(self):
        # Test the rounding helper directly
        self.assertEqual(self.utils._round_to_standard_ram(7.7), 8)
        self.assertEqual(self.utils._round_to_standard_ram(7.2), 8)
        self.assertEqual(self.utils._round_to_standard_ram(8.0), 8)
        self.assertEqual(self.utils._round_to_standard_ram(15.5), 16)
        self.assertEqual(self.utils._round_to_standard_ram(31.2), 32)
        self.assertEqual(self.utils._round_to_standard_ram(3.8), 4)
        self.assertEqual(self.utils._round_to_standard_ram(5.5), 6)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_single_module_mb(self, mock_run):
        """Test _get_installed_ram_from_dmi with single 8192 MB module."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.2.0 present.

Handle 0x0012, DMI type 17, 84 bytes
Memory Device
	Array Handle: 0x0010
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 8192 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous
	Speed: 2667 MT/s
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # 8192 MB / 1024 = 8 GiB
        result = self.utils._get_installed_ram_from_dmi()
        self.assertEqual(result, 8.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_single_module_gb(self, mock_run):
        """Test _get_installed_ram_from_dmi with single 8 GB module."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.2.0 present.

Handle 0x0012, DMI type 17, 84 bytes
Memory Device
	Array Handle: 0x0010
	Size: 8 GB
	Form Factor: SODIMM
	Locator: ChannelA-DIMM0
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # 8 GB * 1024 = 8192 MB / 1024 = 8 GiB
        result = self.utils._get_installed_ram_from_dmi()
        self.assertEqual(result, 8.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_two_modules(self, mock_run):
        """Test _get_installed_ram_from_dmi with two 8192 MB modules."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.2.0 present.

Handle 0x0012, DMI type 17, 84 bytes
Memory Device
	Array Handle: 0x0010
	Size: 8192 MB
	Form Factor: SODIMM
	Locator: ChannelA-DIMM0

Handle 0x0013, DMI type 17, 84 bytes
Memory Device
	Array Handle: 0x0010
	Size: 8192 MB
	Form Factor: SODIMM
	Locator: ChannelB-DIMM0
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # 2 * 8192 MB / 1024 = 16 GiB
        result = self.utils._get_installed_ram_from_dmi()
        self.assertEqual(result, 16.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_mixed_units(self, mock_run):
        """Test _get_installed_ram_from_dmi with mixed MB and GB units."""
        dmidecode_output = """# dmidecode 3.3

Handle 0x0012, DMI type 17, 84 bytes
Memory Device
	Size: 4096 MB
	Locator: ChannelA-DIMM0

Handle 0x0013, DMI type 17, 84 bytes
Memory Device
	Size: 8 GB
	Locator: ChannelB-DIMM0
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # 4096 MB + (8 GB * 1024 MB) = 4096 + 8192 = 12288 MB / 1024 = 12 GiB
        result = self.utils._get_installed_ram_from_dmi()
        self.assertEqual(result, 12.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_with_empty_slots(self, mock_run):
        """Test _get_installed_ram_from_dmi ignores empty memory slots."""
        dmidecode_output = """# dmidecode 3.3

Handle 0x0012, DMI type 17, 84 bytes
Memory Device
	Size: 8192 MB
	Locator: ChannelA-DIMM0

Handle 0x0013, DMI type 17, 84 bytes
Memory Device
	Size: No Module Installed
	Locator: ChannelA-DIMM1

Handle 0x0014, DMI type 17, 84 bytes
Memory Device
	Size: 8192 MB
	Locator: ChannelB-DIMM0

Handle 0x0015, DMI type 17, 84 bytes
Memory Device
	Size: Not Installed
	Locator: ChannelB-DIMM1
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Only count the two 8192 MB modules: 2 * 8192 / 1024 = 16 GiB
        result = self.utils._get_installed_ram_from_dmi()
        self.assertEqual(result, 16.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_command_fails(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when dmidecode fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ['sudo', 'dmidecode', '-t', '17'])

        result = self.utils._get_installed_ram_from_dmi()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_oserror(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when dmidecode is not found."""
        mock_run.side_effect = OSError("dmidecode not found")

        result = self.utils._get_installed_ram_from_dmi()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_no_memory_found(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when no memory is found."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.2.0 present.

Handle 0x0010, DMI type 16, 23 bytes
Physical Memory Array
	Location: System Board Or Motherboard
	Maximum Capacity: 64 GB
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = self.utils._get_installed_ram_from_dmi()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_mem_uses_dmi_when_available(self, mock_run):
        """Test get_mem uses DMI detection when available."""
        # Mock dmidecode to return 16 GB (16384 MB)
        dmidecode_output = """
Handle 0x0012, DMI type 17, 84 bytes
Memory Device
	Size: 8192 MB
	Locator: ChannelA-DIMM0

Handle 0x0013, DMI type 17, 84 bytes
Memory Device
	Size: 8192 MB
	Locator: ChannelB-DIMM0
"""
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Should return 16 GiB from DMI, not read /proc/meminfo
        result = self.utils.get_mem()
        self.assertEqual(result, "16")
        # Verify dmidecode was called
        mock_run.assert_called_once_with(
            ["sudo", "dmidecode", "-t", "17"],
            capture_output=True,
            text=True,
            check=True
        )

    @patch('subprocess.run')
    def test_get_mem_falls_back_to_meminfo_when_dmi_fails(self, mock_run):
        """Test get_mem falls back to /proc/meminfo when DMI fails."""
        # Mock dmidecode to fail
        mock_run.side_effect = subprocess.CalledProcessError(1, ['sudo', 'dmidecode', '-t', '17'])

        # Mock /proc/meminfo
        meminfo_content = "MemTotal:       15500000 kB"
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            result = self.utils.get_mem()
            # Should fall back to meminfo and return 16 (from 15500000 KiB)
            self.assertEqual(result, "16")

    def test_get_cpu_info(self):
        cpuinfo_content = "model name: Test CPU"
        with patch('builtins.open', mock_open(read_data=cpuinfo_content)):
            self.assertEqual(self.utils.get_cpu_info(), "Test CPU")

    @patch('subprocess.run')
    def test_get_discrete_gpu_no_controllers(self, mock_run):
        """Test get_discrete_gpu returns None when no VGA/3D controllers found."""
        # Mock lspci to return no VGA/3D controllers
        mock_result = MagicMock()
        mock_result.stdout = "00:00.0 Host bridge: Intel Corporation\n00:02.0 Audio device: Intel Corporation"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = self.utils.get_discrete_gpu()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_discrete_gpu_single_controller(self, mock_run):
        """Test get_discrete_gpu returns None when only one VGA controller found."""
        # Mock lspci to return only one VGA controller (integrated GPU)
        mock_result = MagicMock()
        mock_result.stdout = "00:02.0 VGA compatible controller: Intel Corporation\n00:03.0 Audio device: Intel Corporation"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = self.utils.get_discrete_gpu()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_discrete_gpu_hybrid_system_with_glxinfo(self, mock_run):
        """Test get_discrete_gpu returns formatted renderer for hybrid system with working glxinfo."""
        lspci_output = """00:02.0 VGA compatible controller: Intel Corporation UHD Graphics
01:00.0 3D controller: NVIDIA Corporation GeForce GTX 1650"""
        
        glxinfo_output = """name of display: :0
display: :0  screen: 0
direct rendering: Yes
server glx vendor string: SGI
OpenGL vendor string: NVIDIA Corporation
OpenGL renderer string: NVIDIA GeForce GTX 1650/PCIe/SSE2
OpenGL core profile version string: 4.6.0"""

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            mock_result = MagicMock()
            if 'lspci' in cmd:
                mock_result.stdout = lspci_output
                mock_result.returncode = 0
            elif 'glxinfo' in cmd:
                mock_result.stdout = glxinfo_output
                mock_result.returncode = 0
            return mock_result

        mock_run.side_effect = subprocess_side_effect

        result = self.utils.get_discrete_gpu()
        # Should strip /PCIe/SSE2
        self.assertEqual(result, "NVIDIA GeForce GTX 1650")

    @patch('subprocess.run')
    def test_get_discrete_gpu_hybrid_system_glxinfo_missing(self, mock_run):
        """Test get_discrete_gpu returns fallback when glxinfo is missing."""
        lspci_output = """00:02.0 VGA compatible controller: Intel Corporation
01:00.0 3D controller: NVIDIA Corporation"""

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'lspci' in cmd:
                mock_result = MagicMock()
                mock_result.stdout = lspci_output
                mock_result.returncode = 0
                return mock_result
            elif 'glxinfo' in cmd:
                # Simulate glxinfo not installed
                raise OSError("glxinfo not found")

        mock_run.side_effect = subprocess_side_effect

        result = self.utils.get_discrete_gpu()
        self.assertEqual(result, "Discrete GPU detected")

    @patch('subprocess.run')
    def test_get_discrete_gpu_hybrid_system_glxinfo_fails(self, mock_run):
        """Test get_discrete_gpu returns fallback when glxinfo fails."""
        lspci_output = """00:02.0 VGA compatible controller: Intel Corporation
01:00.0 VGA compatible controller: AMD Radeon"""

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'lspci' in cmd:
                mock_result = MagicMock()
                mock_result.stdout = lspci_output
                mock_result.returncode = 0
                return mock_result
            elif 'glxinfo' in cmd:
                # Simulate glxinfo failing
                raise subprocess.CalledProcessError(1, cmd)

        mock_run.side_effect = subprocess_side_effect

        result = self.utils.get_discrete_gpu()
        self.assertEqual(result, "Discrete GPU detected")

    @patch('subprocess.run')
    def test_get_discrete_gpu_lspci_fails(self, mock_run):
        """Test get_discrete_gpu returns None when lspci fails."""
        # Simulate lspci command failure
        mock_run.side_effect = subprocess.CalledProcessError(1, ['lspci'])

        result = self.utils.get_discrete_gpu()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_discrete_gpu_lspci_oserror(self, mock_run):
        """Test get_discrete_gpu returns None when lspci is not found."""
        # Simulate lspci not installed
        mock_run.side_effect = OSError("lspci not found")

        result = self.utils.get_discrete_gpu()
        self.assertIsNone(result)

    def test_format_gpu_renderer_basic(self):
        """Test _format_gpu_renderer with basic renderer string."""
        renderer = "NVIDIA GeForce RTX 3060"
        result = self.utils._format_gpu_renderer(renderer)
        self.assertEqual(result, "NVIDIA GeForce RTX 3060")

    def test_format_gpu_renderer_with_pcie_suffix(self):
        """Test _format_gpu_renderer removes /PCIe/SSE2 suffix."""
        renderer = "NVIDIA GeForce GTX 1650/PCIe/SSE2"
        result = self.utils._format_gpu_renderer(renderer)
        self.assertEqual(result, "NVIDIA GeForce GTX 1650")

    def test_format_gpu_renderer_with_driver_suffix(self):
        """Test _format_gpu_renderer removes driver suffix."""
        renderer = "AMD Radeon RX 6600 (NVIDIA_PROPRIETARY)"
        result = self.utils._format_gpu_renderer(renderer)
        self.assertEqual(result, "AMD Radeon RX 6600")

    def test_format_gpu_renderer_with_zink_wrapper(self):
        """Test _format_gpu_renderer handles zink Vulkan wrapper format."""
        renderer = "zink Vulkan 1.4(NVIDIA GeForce RTX 3060)"
        result = self.utils._format_gpu_renderer(renderer)
        self.assertEqual(result, "NVIDIA GeForce RTX 3060")

    def test_format_gpu_renderer_zink_with_pcie(self):
        """Test _format_gpu_renderer handles zink wrapper with PCIe suffix."""
        renderer = "zink Vulkan 1.3(AMD Radeon RX 6600/PCIe/SSE2)"
        result = self.utils._format_gpu_renderer(renderer)
        self.assertEqual(result, "AMD Radeon RX 6600")

    def test_format_gpu_renderer_complex(self):
        """Test _format_gpu_renderer with complex renderer string."""
        renderer = "NVIDIA GeForce RTX 3070/PCIe/SSE2 (NVIDIA_PROPRIETARY)"
        result = self.utils._format_gpu_renderer(renderer)
        self.assertEqual(result, "NVIDIA GeForce RTX 3070")

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_8gb_two_modules(self, mock_run):
        """Test _get_installed_ram_from_dmi with 8GB in 2x4GB modules."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 4096 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous

Handle 0x0011, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 4096 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelB-DIMM0
	Bank Locator: BANK 2
	Type: DDR4
	Type Detail: Synchronous"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # 4096 MB + 4096 MB = 8192 MB = 8 GiB
        self.assertEqual(result, 8.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_16gb_single_module(self, mock_run):
        """Test _get_installed_ram_from_dmi with 16GB in 1x16GB module."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 16384 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # 16384 MB = 16 GiB
        self.assertEqual(result, 16.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_with_empty_slots(self, mock_run):
        """Test _get_installed_ram_from_dmi with empty slots showing 'No Module Installed'."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 8192 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous

Handle 0x0011, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: Unknown
	Data Width: Unknown
	Size: No Module Installed
	Form Factor: Unknown
	Set: None
	Locator: ChannelB-DIMM0
	Bank Locator: BANK 2
	Type: Unknown
	Type Detail: None"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # Should only count the 8192 MB module, ignore the empty slot
        self.assertEqual(result, 8.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_gb_units(self, mock_run):
        """Test _get_installed_ram_from_dmi with sizes reported in GB."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 8 GB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous

Handle 0x0011, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 8 GB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelB-DIMM0
	Bank Locator: BANK 2
	Type: DDR4
	Type Detail: Synchronous"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # 8 GB + 8 GB = 16 GB = 16 GiB
        self.assertEqual(result, 16.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_mixed_empty_and_populated(self, mock_run):
        """Test _get_installed_ram_from_dmi with mixed empty and populated slots."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 4096 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous

Handle 0x0011, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: Unknown
	Data Width: Unknown
	Size: No Module Installed
	Form Factor: Unknown
	Set: None
	Locator: ChannelA-DIMM1
	Bank Locator: BANK 1
	Type: Unknown
	Type Detail: None

Handle 0x0012, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 8192 MB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelB-DIMM0
	Bank Locator: BANK 2
	Type: DDR4
	Type Detail: Synchronous

Handle 0x0013, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: Unknown
	Data Width: Unknown
	Size: Not Installed
	Form Factor: Unknown
	Set: None
	Locator: ChannelB-DIMM1
	Bank Locator: BANK 3
	Type: Unknown
	Type Detail: None"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # 4096 MB + 8192 MB = 12288 MB = 12 GiB
        self.assertEqual(result, 12.0)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_below_threshold(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when below 256MB threshold."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Error Information Handle: Not Provided
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 128 MB
	Form Factor: DIMM
	Set: None
	Locator: DIMM0
	Bank Locator: BANK 0
	Type: DDR
	Type Detail: Synchronous"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # 128 MB is below the 256 MB threshold, should return None
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_command_fails(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when dmidecode command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ['sudo', 'dmidecode', '-t', '17'])
        
        result = self.utils._get_installed_ram_from_dmi()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_oserror(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when dmidecode is not available."""
        mock_run.side_effect = OSError("dmidecode not found")
        
        result = self.utils._get_installed_ram_from_dmi()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_get_installed_ram_from_dmi_invalid_output(self, mock_run):
        """Test _get_installed_ram_from_dmi returns None when output has unexpected format."""
        dmidecode_output = """# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.0 present.

Handle 0x0010, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x000F
	Size: Invalid Data"""
        
        mock_result = MagicMock()
        mock_result.stdout = dmidecode_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.utils._get_installed_ram_from_dmi()
        # No valid memory sizes found, should return None
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()

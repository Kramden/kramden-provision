import sys
import os
import unittest
import json
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

        # Setup context to return our mock device
        mock_context_instance = MagicMock()
        mock_context_instance.list_devices.return_value = [mock_device]
        mock_context.return_value = mock_context_instance

        # 209715200 * 512 / 1024^3 = 100 GB
        result = self.utils.get_disks()
        self.assertEqual(result, {'/dev/sda': 100})

    def test_get_mem_8gb_system(self):
        # Simulate 8GB system with ~7.7GB reported (reserved for video, etc.)
        meminfo_content = "MemTotal:       7700000 kB"
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            self.assertEqual(self.utils.get_mem(), "8")

    def test_get_mem_16gb_system(self):
        # Simulate 16GB system with ~15.5GB reported
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

    def test_get_cpu_info(self):
        cpuinfo_content = "model name: Test CPU"
        with patch('builtins.open', mock_open(read_data=cpuinfo_content)):
            self.assertEqual(self.utils.get_cpu_info(), "Test CPU")

if __name__ == '__main__':
    unittest.main()

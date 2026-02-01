import sys, os
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
        
        # Mock hostnamectl call
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(hostnamectl_json)
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Create Utils instance - serial should be empty since vendor is Lenovo
        utils = Utils()
        
        # For Lenovo, serial from hostnamectl should be skipped
        # The actual DMI fallback won't work in tests, so serial should be empty
        self.assertEqual(utils.get_serial(), "")

    def test_get_disk(self):
        with patch('psutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value.total = 1024 ** 3 * 100  # 100 GB
            self.assertEqual(self.utils.get_disk(), "100")

    def test_get_mem(self):
        meminfo_content = "MemTotal:       2048000 kB"
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            self.assertEqual(self.utils.get_mem(), "2")

    def test_get_cpu_info(self):
        cpuinfo_content = "model name: Test CPU"
        with patch('builtins.open', mock_open(read_data=cpuinfo_content)):
            self.assertEqual(self.utils.get_cpu_info(), "Test CPU")

if __name__ == '__main__':
    unittest.main()

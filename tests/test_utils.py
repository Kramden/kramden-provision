import unittest
from unittest.mock import patch, mock_open, MagicMock
from src.utils import Utils

class TestUtils(unittest.TestCase):
    def setUp(self):
        # Mock the subprocess.run to return a specific output
        self.hostnamectl_output = '''Static hostname: testhost
Operating System: Test OS 1.0
Hardware Vendor: Test Vendor
Hardware Model: Test Model'''
        self.mock_subproc_run = patch('subprocess.run').start()
        self.mock_subproc_run.return_value.stdout = self.hostnamectl_output
        self.mock_subproc_run.return_value.returncode = 0

        # Create a Utils instance
        self.utils = Utils()

    def tearDown(self):
        patch.stopall()

    def test_get_hostname(self):
        self.assertEqual(self.utils.get_hostname(), " testhost")

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
        self.assertEqual(self.utils.get_os(), " Test OS 1.0")

    def test_get_vender(self):
        self.assertEqual(self.utils.get_vender(), " Test Vendor")

    def test_get_model(self):
        self.assertEqual(self.utils.get_model(), " Test Model")

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

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.realpath(__file__)) + "/.."
sys.path.insert(1, _REPO_ROOT + "/scripts/")

from validate_defect_types import DEFECT_TYPES_PATH, validate


class TestDefectTypesConfig(unittest.TestCase):
    def test_defect_types_config_is_valid(self):
        with open(DEFECT_TYPES_PATH) as f:
            defect_types = json.load(f)
        self.assertEqual(validate(defect_types), [])


if __name__ == "__main__":
    unittest.main()

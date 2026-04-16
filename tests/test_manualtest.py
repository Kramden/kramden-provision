import os
import sys
import unittest

sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)) + "/../src/")

from manualtest import TouchscreenTest


class TestTouchscreenTest(unittest.TestCase):
    def test_calculate_target_coordinates_waits_for_real_geometry(self):
        self.assertEqual(TouchscreenTest._calculate_target_coordinates(0, 768), [])
        self.assertEqual(TouchscreenTest._calculate_target_coordinates(1024, 1), [])

    def test_calculate_target_coordinates_stays_within_bounds(self):
        coordinates = TouchscreenTest._calculate_target_coordinates(100, 100)

        self.assertEqual(len(coordinates), len(TouchscreenTest.TARGET_POSITIONS))
        for x, y in coordinates:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x, 100 - TouchscreenTest.TARGET_SIZE)
            self.assertLessEqual(y, 100 - TouchscreenTest.TARGET_SIZE)

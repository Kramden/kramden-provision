import os
import sys
import unittest

sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)) + "/../src/")

from specinfo import RAM_DATACODE, SpecInfo, _ram_datacode_value


class TestRamDatacodeValue(unittest.TestCase):
    """RA00's compact "<soldered>S <replaceable>R" Sortly value -- see
    _ram_datacode_value's docstring for the S/R inclusion rules."""

    def test_soldered_and_replaceable(self):
        breakdown = {
            "soldered_gb": 16,
            "replaceable_gb": 8,
            "has_sodimm_slot": True,
        }
        self.assertEqual(_ram_datacode_value(breakdown), "16S 8R")

    def test_soldered_only_no_slot(self):
        breakdown = {
            "soldered_gb": 16,
            "replaceable_gb": 0,
            "has_sodimm_slot": False,
        }
        self.assertEqual(_ram_datacode_value(breakdown), "16S")

    def test_replaceable_only(self):
        breakdown = {
            "soldered_gb": 0,
            "replaceable_gb": 8,
            "has_sodimm_slot": True,
        }
        self.assertEqual(_ram_datacode_value(breakdown), "8R")

    def test_soldered_with_empty_sodimm_slot(self):
        breakdown = {
            "soldered_gb": 16,
            "replaceable_gb": 0,
            "has_sodimm_slot": True,
        }
        self.assertEqual(_ram_datacode_value(breakdown), "16S 0R")

    def test_no_soldered_no_replaceable_no_slot(self):
        breakdown = {
            "soldered_gb": 0,
            "replaceable_gb": 0,
            "has_sodimm_slot": False,
        }
        self.assertIsNone(_ram_datacode_value(breakdown))

    def test_fractional_amounts_use_g_formatting(self):
        breakdown = {
            "soldered_gb": 1.5,
            "replaceable_gb": 0,
            "has_sodimm_slot": False,
        }
        self.assertEqual(_ram_datacode_value(breakdown), "1.5S")


class TestSpecInfoGetSortlyEntries(unittest.TestCase):
    """SpecInfo.get_sortly_entries() feeds RA00 into Sortly's "Speccing
    Notes" custom attribute -- see SpecComplete._gather_sortly_notes."""

    def setUp(self):
        self.specinfo = SpecInfo.__new__(SpecInfo)

    def test_reports_ra00_entry_when_breakdown_present(self):
        self.specinfo._gathered = {
            "memory_breakdown": {
                "soldered_gb": 16,
                "replaceable_gb": 8,
                "has_sodimm_slot": True,
            }
        }
        self.assertEqual(
            self.specinfo.get_sortly_entries(), [f"{RAM_DATACODE}|16S 8R"]
        )

    def test_no_entry_when_breakdown_missing(self):
        self.specinfo._gathered = {"memory_breakdown": None}
        self.assertEqual(self.specinfo.get_sortly_entries(), [])

    def test_no_entry_when_nothing_to_report(self):
        self.specinfo._gathered = {
            "memory_breakdown": {
                "soldered_gb": 0,
                "replaceable_gb": 0,
                "has_sodimm_slot": False,
            }
        }
        self.assertEqual(self.specinfo.get_sortly_entries(), [])


if __name__ == "__main__":
    unittest.main()

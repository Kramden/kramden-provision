import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)) + "/../src/")

import sortly


class TestSortlyDebugOutput(unittest.TestCase):
    def tearDown(self):
        sortly.reset_api_call_count()

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_sortly_request_logs_counter_and_status(self, mock_print, mock_request):
        response = MagicMock(status_code=200)
        mock_request.return_value = response

        result = sortly._sortly_request(
            "post",
            "https://api.sortly.co/api/v1/items/search",
            params={"page": 1},
            json={"query": "ABC123"},
            headers={"Authorization": "Bearer test"},
        )

        self.assertIs(result, response)
        self.assertEqual(sortly.get_api_call_count(), 1)
        mock_request.assert_called_once_with(
            "post",
            "https://api.sortly.co/api/v1/items/search",
            params={"page": 1},
            json={"query": "ABC123"},
            headers={"Authorization": "Bearer test"},
        )
        self.assertEqual(
            mock_print.call_args_list[0].args[0],
            "[Sortly API #1] POST https://api.sortly.co/api/v1/items/search "
            "params={'page': 1} json={'query': 'ABC123'}",
        )
        self.assertEqual(
            mock_print.call_args_list[1].args[0],
            "[Sortly API #1] Response 200",
        )

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_search_by_serial_counts_each_api_call(self, mock_print, mock_request):
        first_page = MagicMock()
        first_page.status_code = 200
        first_page.json.return_value = {
            "data": [{"id": i, "custom_attribute_values": []} for i in range(100)]
        }

        second_page = MagicMock()
        second_page.status_code = 200
        second_page.json.return_value = {"data": []}

        mock_request.side_effect = [first_page, second_page]

        matches = sortly.search_by_serial("api-key", ["folder-1"], "ABC123")

        self.assertEqual(matches, [])
        self.assertEqual(sortly.get_api_call_count(), 2)
        self.assertEqual(mock_request.call_count, 2)
        first_call = mock_print.call_args_list[0].args[0]
        second_call = mock_print.call_args_list[2].args[0]

        self.assertIn("[Sortly API #1] POST https://api.sortly.co/api/v1/items/search", first_call)
        self.assertIn("'page': 1", first_call)
        self.assertIn("'folder_ids': ['folder-1']", first_call)
        self.assertIn("'query': 'ABC123'", first_call)

        self.assertIn("[Sortly API #2] POST https://api.sortly.co/api/v1/items/search", second_call)
        self.assertIn("'page': 2", second_call)
        self.assertIn("'folder_ids': ['folder-1']", second_call)
        self.assertIn("'query': 'ABC123'", second_call)

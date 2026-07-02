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


class TestUpdateItem(unittest.TestCase):
    def tearDown(self):
        sortly.reset_api_call_count()

    @staticmethod
    def _item_response(attr_names):
        response = MagicMock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = {
            "data": {
                "custom_attribute_values": [
                    {"custom_attribute_name": name, "custom_attribute_id": i + 1}
                    for i, name in enumerate(attr_names)
                ]
            }
        }
        return response

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_update_success_returns_no_error(self, mock_print, mock_request):
        put_response = MagicMock(status_code=200, ok=True)
        mock_request.side_effect = [
            self._item_response(["Brand", "CPU"]),
            put_response,
        ]

        success, error = sortly.update_item(
            "api-key", "item-1", {"Brand": "Asus", "CPU": "i5"}
        )

        self.assertTrue(success)
        self.assertIsNone(error)

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_rejected_update_reports_invalid_brand(self, mock_print, mock_request):
        put_response = MagicMock(status_code=422, ok=False, text="")
        put_response.json.return_value = {
            "errors": {"Brand": ["is not included in the list"]}
        }
        mock_request.side_effect = [
            self._item_response(["Brand"]),
            put_response,
        ]

        success, error = sortly.update_item(
            "api-key", "item-1", {"Brand": "ASUSTek International"}
        )

        self.assertFalse(success)
        self.assertIn(
            "Brand 'ASUSTek International' is not one of the Sortly brand options",
            error,
        )
        self.assertIn("Brand: is not included in the list", error)

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_rejected_update_with_valid_brand_reports_server_message(
        self, mock_print, mock_request
    ):
        put_response = MagicMock(status_code=422, ok=False, text="")
        put_response.json.return_value = {"error": "Something went wrong"}
        mock_request.side_effect = [
            self._item_response(["Brand"]),
            put_response,
        ]

        success, error = sortly.update_item("api-key", "item-1", {"Brand": "Asus"})

        self.assertFalse(success)
        self.assertNotIn("brand options", error)
        self.assertIn("Sortly said: Something went wrong", error)

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_rejected_update_without_details_reports_status(
        self, mock_print, mock_request
    ):
        put_response = MagicMock(status_code=500, ok=False, text="")
        put_response.json.side_effect = ValueError("no json")
        mock_request.side_effect = [
            self._item_response(["Brand"]),
            put_response,
        ]

        success, error = sortly.update_item("api-key", "item-1", {"Brand": "Asus"})

        self.assertFalse(success)
        self.assertIn("Sortly returned HTTP 500", error)

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_no_matching_attributes_lists_missing_fields(
        self, mock_print, mock_request
    ):
        mock_request.side_effect = [self._item_response(["Unrelated Field"])]

        success, error = sortly.update_item(
            "api-key", "item-1", {"Brand": "Asus", "CPU": "i5"}
        )

        self.assertFalse(success)
        self.assertIn("None of the hardware fields exist", error)
        self.assertIn("Brand", error)
        self.assertIn("CPU", error)

    @patch("sortly.requests.request")
    @patch("builtins.print")
    def test_fetch_failure_reports_reason(self, mock_print, mock_request):
        get_response = MagicMock(status_code=404, ok=False)
        get_response.raise_for_status.side_effect = sortly.requests.HTTPError(
            "404 Client Error: Not Found"
        )
        mock_request.side_effect = [get_response]

        success, error = sortly.update_item("api-key", "item-1", {"Brand": "Asus"})

        self.assertFalse(success)
        self.assertIn("Could not fetch the record from Sortly", error)
        self.assertIn("404", error)

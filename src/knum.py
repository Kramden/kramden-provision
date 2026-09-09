"""OS Load "Identify" page: the tech scans/enters the device's K-number and
clicks Search (or it's found in the EFI var and searched automatically) to
look it up in Sortly by name; the Sortly record is then updated with
current system info, and the machine's hostname is set to the K-number.

Automatic serial-number lookup on page show is currently disabled (see
_AUTO_SERIAL_LOOKUP_ENABLED below) -- searching by serial number across a
broad folder scope can force Sortly's search to page through the entire
scope before the client-side exact-match filter finds anything. The
serial-lookup code path is kept for a future, more selective use (e.g.
scoped to a narrow folder set) rather than deleted outright."""

import gi
import threading

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk, GLib

from utils import Utils
from sortly import (
    OSLOAD_SORTLY_LOOKUP_ENABLED,
    get_api_key,
    get_stage_folder_ids,
    resolve_folder_ids,
    search_by_serial,
    search_item_by_name,
    update_item,
    get_system_info,
    sortly_error_message,
)

# Kept separate from OSLOAD_SORTLY_LOOKUP_ENABLED: this only gates the
# automatic serial-number lookup on page show (see module docstring).
_AUTO_SERIAL_LOOKUP_ENABLED = False


class KramdenNumber(Adw.Bin):
    """OS Load Identify page (K-number entry + Sortly lookup/update)."""

    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Identify"
        self.next = None
        self.skip = False

        self._lookup_done = False
        self._submitted = False
        self._existing_item = None
        self._system_info = None
        self._user_edited = False

        # Main vertical layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # K-Number input row
        knumber_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        knumber_label = Gtk.Label(label="K-Number:")
        self.knumber_entry = Gtk.Entry()
        self.knumber_entry.set_placeholder_text("e.g. K-123456")
        self.knumber_entry.set_hexpand(True)
        self.knumber_entry.connect("changed", self._on_knumber_changed)
        self.knumber_entry.connect("activate", self._on_entry_activate)

        # Search button: looks up the entered K-number in Sortly. Only
        # relevant when live Sortly lookups are enabled -- with the master
        # switch off, "Set" below goes straight to setting the hostname.
        self.search_button = Gtk.Button(label="Search")
        self.search_button.set_visible(OSLOAD_SORTLY_LOOKUP_ENABLED)
        self.search_button.set_sensitive(False)
        self.search_button.connect("clicked", self._on_search_clicked)

        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)

        knumber_box.append(knumber_label)
        knumber_box.append(self.knumber_entry)
        knumber_box.append(self.search_button)
        knumber_box.append(self.spinner)

        # Status label
        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)

        # System info list box
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)

        self.info_list_box = Gtk.ListBox()
        self.info_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled_window.set_child(self.info_list_box)

        # Register/Update button
        self.register_button = Gtk.Button(label="Set")
        self.register_button.add_css_class("button-green")
        self.register_button.set_sensitive(False)
        self.register_button.connect("clicked", self._on_register_clicked)

        vbox.append(knumber_box)
        vbox.append(self.status_label)
        vbox.append(scrolled_window)
        vbox.append(self.register_button)

        self.set_child(vbox)

    def on_shown(self):
        utils = Utils()
        hostname = utils.get_hostname()
        state = self.state.get_value()
        if hostname.lower().startswith("k"):
            state["KramdenNumber"] = True
        else:
            state["KramdenNumber"] = False
        print("knum:on_shown " + str(self.state.get_value()))

        if self._lookup_done:
            return

        # Prepopulate K-Number from EFI variable if available
        efi_knumber = Utils.read_kramden_number_efivar()
        formatted_efi = None
        if efi_knumber:
            formatted_efi = Utils.format_knumber(efi_knumber)
            if formatted_efi and not self._user_edited:
                self.knumber_entry.set_text(formatted_efi)

        self._set_status("Gathering system information...")
        self._system_info = get_system_info()
        self._populate_system_info()

        if not _AUTO_SERIAL_LOOKUP_ENABLED:
            self._lookup_done = True
            if not OSLOAD_SORTLY_LOOKUP_ENABLED:
                self._set_status(
                    "Sortly lookup is temporarily disabled. Enter a K-number to continue."
                )
                return

            if not formatted_efi:
                self._set_status("Enter a K-number and click Search.")
                return

            # K-number already known from the EFI var -- search for its
            # existing Sortly record automatically instead of making the
            # tech search for a number they didn't have to type in.
            try:
                api_key = get_api_key()
            except EnvironmentError as e:
                self._set_status(str(e), error=True)
                return
            self._start_search(api_key, formatted_efi)
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            self._set_status(str(e), error=True)
            self._lookup_done = True
            return

        serial = self._system_info.get("Serial# Scanner")
        if not serial:
            self._set_status("Could not detect serial number.", error=True)
            self._lookup_done = True
            return

        if not OSLOAD_SORTLY_LOOKUP_ENABLED:
            self._lookup_done = True
            self._set_status(
                "Automatic serial lookup is temporarily disabled. Enter a K-number to continue."
            )
            return

        self._set_status(f"Looking up serial '{serial}' in Sortly...")
        self.spinner.set_visible(True)
        self.spinner.start()

        thread = threading.Thread(
            target=self._lookup_serial_thread,
            args=(api_key, serial),
            daemon=True,
        )
        thread.start()

    def _lookup_serial_thread(self, api_key, serial):
        try:
            GLib.idle_add(self._set_status, "Looking up folders...")
            folder_ids = resolve_folder_ids(get_stage_folder_ids("osload"))
            GLib.idle_add(self._set_status, f"Searching for serial '{serial}'...")
            results = search_by_serial(api_key, folder_ids, serial)
        except Exception as e:
            GLib.idle_add(self._on_lookup_complete, None, sortly_error_message(e))
            return
        GLib.idle_add(self._on_lookup_complete, results, None)

    def _on_lookup_complete(self, results, error):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self._lookup_done = True

        if error:
            self._set_status(f"Lookup failed: {error}", error=True)
            return

        if results:
            self._existing_item = results[0]
            item_name = self._existing_item.get("name", "")
            # Don't overwrite if user has already started typing
            if not self._user_edited:
                self.knumber_entry.set_text(item_name)
                self.knumber_entry.set_sensitive(False)
            self._set_status(f"Found existing record: {item_name}")
            self.register_button.set_label("Update")
            self.register_button.set_sensitive(True)

            # Auto-trigger update
            self._on_register_clicked(self.register_button)
        else:
            self._set_status(
                "No existing record found for this serial. Enter a K-number to register."
            )

    def _on_entry_activate(self, entry):
        # Enter key: register if a search already enabled it, otherwise
        # search first (mirrors clicking whichever button is available).
        if self.register_button.get_sensitive():
            self._on_register_clicked(self.register_button)
        elif self.search_button.get_sensitive():
            self._on_search_clicked(self.search_button)

    def _on_search_clicked(self, button):
        raw_value = self.knumber_entry.get_text().strip()
        formatted = Utils.format_knumber(raw_value)
        if not formatted:
            self._set_status("Invalid K-number format.", error=True)
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            self._set_status(str(e), error=True)
            return

        self._start_search(api_key, formatted)

    def _start_search(self, api_key, knumber):
        self.search_button.set_sensitive(False)
        self.register_button.set_sensitive(False)
        self.knumber_entry.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.start()
        self._set_status(f"Searching for '{knumber}' in Sortly...")

        thread = threading.Thread(
            target=self._search_knumber_thread,
            args=(api_key, knumber),
            daemon=True,
        )
        thread.start()

    def _search_knumber_thread(self, api_key, knumber):
        try:
            GLib.idle_add(self._set_status, "Looking up folders...")
            folder_ids = resolve_folder_ids(get_stage_folder_ids("osload"))
            GLib.idle_add(self._set_status, f"Searching for '{knumber}'...")
            results = search_item_by_name(api_key, folder_ids, knumber)
        except Exception as e:
            GLib.idle_add(
                self._on_search_complete, None, knumber, sortly_error_message(e)
            )
            return
        GLib.idle_add(self._on_search_complete, results, knumber, None)

    def _on_search_complete(self, results, knumber, error):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.knumber_entry.set_sensitive(not self._submitted)
        self.search_button.set_sensitive(not self._submitted)

        if error:
            self._set_status(f"Search failed: {error}", error=True)
            return

        if results:
            self._existing_item = results[0]
            self._set_status(f"Found existing record: {knumber}")
            self.register_button.set_label("Update")
        else:
            self._existing_item = None
            self._set_status(f"No existing record found for '{knumber}'.")
            self.register_button.set_label("Set")

        self.register_button.set_sensitive(not self._submitted)

    def _on_knumber_changed(self, entry):
        self._user_edited = True
        self._existing_item = None
        value = entry.get_text().strip()

        if not OSLOAD_SORTLY_LOOKUP_ENABLED:
            formatted = Utils.format_knumber(value) if value else None
            self.register_button.set_sensitive(bool(formatted) and not self._submitted)
            if formatted:
                if self.status_label.has_css_class("text-error"):
                    self.status_label.remove_css_class("text-error")
                    self.status_label.set_label("")
            elif value:
                self._set_status("Invalid K-number format.", error=True)
            return

        self.register_button.set_sensitive(False)
        if not value:
            self.search_button.set_sensitive(False)
            return

        formatted = Utils.format_knumber(value)
        if formatted:
            self.register_button.set_label("Set")
            self.search_button.set_sensitive(not self._submitted)
            if self.status_label.has_css_class("text-error"):
                self.status_label.remove_css_class("text-error")
                self.status_label.set_label("")
        else:
            self.search_button.set_sensitive(False)
            if value:
                self._set_status("Invalid K-number format.", error=True)

    def _on_register_clicked(self, widget):
        if self._submitted:
            return

        raw_value = self.knumber_entry.get_text().strip()
        formatted = Utils.format_knumber(raw_value)
        if not formatted:
            self._set_status("Invalid K-number format.", error=True)
            return

        if not OSLOAD_SORTLY_LOOKUP_ENABLED:
            # Sortly queries/updates are temporarily disabled in OSLoad: set
            # the hostname/EFI var directly without contacting Sortly.
            self.register_button.set_sensitive(False)
            self.knumber_entry.set_sensitive(False)
            self._set_status(f"Setting K-number to {formatted}...")
            self._on_register_complete(True, formatted)
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            self._set_status(str(e), error=True)
            return

        self.register_button.set_sensitive(False)
        self.search_button.set_sensitive(False)
        self.knumber_entry.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.start()

        if self._existing_item:
            self._set_status(f"Updating {formatted}...")
        else:
            self._set_status(f"Registering {formatted}...")

        thread = threading.Thread(
            target=self._register_thread,
            args=(api_key, formatted),
            daemon=True,
        )
        thread.start()

    def _register_thread(self, api_key, knumber):
        # A search (manual or EFI-var-triggered) always runs before this is
        # reachable, so self._existing_item already reflects whatever Sortly
        # record matches -- no need to search again here.
        try:
            item = self._existing_item
            if item:
                info = self._system_info or {}
                if info:
                    success, error = update_item(api_key, item["id"], info)
                    if not success:
                        GLib.idle_add(
                            self._on_register_complete,
                            False,
                            error or "Failed to update item.",
                        )
                        return

            GLib.idle_add(self._on_register_complete, True, knumber)
        except Exception as e:
            GLib.idle_add(self._on_register_complete, False, sortly_error_message(e))

    def _on_register_complete(self, success, result):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if success:
            knumber = result
            self._submitted = True
            self._set_status(f"K-number set to {knumber}.")

            # Set hostname and advance
            utils = Utils()
            utils.set_hostname(knumber)
            state = self.state.get_value()
            state["KramdenNumber"] = Utils.format_knumber(knumber) is not None
            print("knum:on_register_complete " + str(self.state.get_value()))
            if state["KramdenNumber"]:
                self.next()
                self.skip = True
        else:
            error = result
            self._set_status(f"Failed: {error}", error=True)
            self.register_button.set_sensitive(True)
            self.search_button.set_sensitive(True)
            self.knumber_entry.set_sensitive(True)

    def _populate_system_info(self):
        if not self._system_info:
            return

        field_order = [
            "Brand", "Chassis Model", "CPU", "RAM", "Storage",
            "Serial# Scanner", "Item Type", "Graphics", "Battery Health",
        ]

        for field in field_order:
            value = self._system_info.get(field)
            if value is None:
                continue
            row = Adw.ActionRow()
            row.set_title(field)
            if field in ("RAM", "Storage"):
                row.set_subtitle(f"{value} GB")
            else:
                row.set_subtitle(str(value))
            self.info_list_box.append(row)

    def _set_status(self, message, error=False):
        self.status_label.set_label(message)
        if error:
            if not self.status_label.has_css_class("text-error"):
                self.status_label.add_css_class("text-error")
        else:
            if self.status_label.has_css_class("text-error"):
                self.status_label.remove_css_class("text-error")

import gi
import threading

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gtk, GLib

from utils import Utils
from sortly import (
    get_api_key,
    get_stage_folder_ids,
    list_subfolders,
    search_by_serial,
    search_item_by_name,
    create_item,
    update_item,
    get_system_info,
)


class SortlyRegister(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Sortly Registration"
        self.next = None
        self.skip = False

        self._lookup_done = False
        self._submitted = False
        self._existing_item = None
        self._system_info = None
        self._user_edited = False
        self._folder_ids = []

        # Main vertical layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # K-Number input row
        knumber_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        knumber_label = Gtk.Label(label="K-Number:")
        self.knumber_entry = Gtk.Entry()
        self.knumber_entry.set_placeholder_text("e.g. K-123456")
        self.knumber_entry.set_hexpand(True)
        self.knumber_entry.connect("changed", self._on_knumber_changed)

        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_knumber_key_pressed)
        self.knumber_entry.add_controller(key_controller)

        self.search_button = Gtk.Button(label="Search")
        self.search_button.set_visible(False)
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

        # Register button
        self.register_button = Gtk.Button(label="Register")
        self.register_button.add_css_class("button-green")
        self.register_button.set_sensitive(False)
        self.register_button.connect("clicked", self._on_register_clicked)

        vbox.append(knumber_box)
        vbox.append(self.status_label)
        vbox.append(scrolled_window)
        vbox.append(self.register_button)

        self.set_child(vbox)

    def on_shown(self):
        if self._lookup_done:
            return

        # Prepopulate K-Number from EFI variable if available
        efi_knumber = Utils.read_kramden_number_efivar()
        if efi_knumber:
            formatted = Utils.format_knumber(efi_knumber)
            if formatted:
                self.knumber_entry.set_text(formatted)

        self._set_status("Gathering system information...")
        self._system_info = get_system_info()
        self._populate_system_info()

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            self._set_status(str(e), error=True)
            return

        serial = self._system_info.get("Serial# Scanner")
        if not serial:
            self._set_status("Could not detect serial number.", error=True)
            self._lookup_done = True
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
            GLib.idle_add(self._set_status, "Discovering subfolders...")
            folder_ids = []
            for fid in get_stage_folder_ids("spec"):
                folder_ids.extend(list_subfolders(api_key, fid))
            self._folder_ids = folder_ids
            GLib.idle_add(
                self._set_status,
                f"Searching {len(folder_ids)} folder(s) for serial '{serial}'...",
            )
            results = search_by_serial(api_key, folder_ids, serial)
        except Exception as e:
            GLib.idle_add(self._on_lookup_complete, None, str(e))
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
            self._set_status(f"Found existing record: {item_name}")
            self.register_button.set_label("Update")
            self.register_button.set_sensitive(True)
        else:
            self._set_status("No existing record found for this serial. Enter a K-number and search.")
            self.search_button.set_visible(True)
            # Enable search button if there's already a valid K-number
            value = self.knumber_entry.get_text().strip()
            if value and Utils.format_knumber(value) and not self._submitted:
                self.search_button.set_sensitive(True)

    def _on_knumber_changed(self, entry):
        self._user_edited = True
        value = entry.get_text().strip()
        formatted = Utils.format_knumber(value) if value else None

        if not value:
            self.register_button.set_sensitive(False)
            self.search_button.set_sensitive(False)
            return

        if not formatted:
            self.register_button.set_sensitive(False)
            self.search_button.set_sensitive(False)
            self._set_status("Invalid K-number format.", error=True)
            return

        self._set_status("")

        if self.search_button.get_visible():
            # Serial was not found — require explicit K-number search
            self._existing_item = None
            self.register_button.set_sensitive(False)
            self.register_button.set_label("Register")
            self.search_button.set_sensitive(not self._submitted)
        else:
            # Serial was found — existing behavior
            self.register_button.set_sensitive(not self._submitted and self._lookup_done)
            if self._existing_item and formatted == self._existing_item.get("name"):
                self.register_button.set_label("Update")
            else:
                self.register_button.set_label("Register")

    def _on_knumber_key_pressed(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self.search_button.get_visible() and self.search_button.get_sensitive():
                GLib.idle_add(self._on_search_clicked, self.search_button)
        return False

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

        self.search_button.set_sensitive(False)
        self.knumber_entry.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.start()
        self._set_status(f"Searching for '{formatted}' in Sortly...")

        thread = threading.Thread(
            target=self._search_knumber_thread,
            args=(api_key, formatted),
            daemon=True,
        )
        thread.start()

    def _search_knumber_thread(self, api_key, knumber):
        try:
            folder_ids = self._folder_ids
            if not folder_ids:
                folder_ids = []
                for fid in get_stage_folder_ids("spec"):
                    folder_ids.extend(list_subfolders(api_key, fid))
                self._folder_ids = folder_ids
            results = search_item_by_name(api_key, folder_ids, knumber)
        except Exception as e:
            GLib.idle_add(self._on_search_complete, None, knumber, str(e))
            return
        GLib.idle_add(self._on_search_complete, results, knumber, None)

    def _on_search_complete(self, results, knumber, error):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.knumber_entry.set_sensitive(True)

        if error:
            self._set_status(f"Search failed: {error}", error=True)
            self.search_button.set_sensitive(True)
            return

        if results:
            self._existing_item = results[0]
            self._set_status(f"Found existing record: {knumber}")
            self.register_button.set_label("Update")
        else:
            self._existing_item = None
            self._set_status(f"No record found for {knumber}.")
            self.register_button.set_label("Register")

        self.register_button.set_sensitive(not self._submitted)

    def _on_register_clicked(self, button):
        if self._submitted:
            return

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

        # If entry matches the existing item, update it directly
        is_update = (
            self._existing_item
            and formatted == self._existing_item.get("name")
        )

        self.register_button.set_sensitive(False)
        self.knumber_entry.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.start()

        if is_update:
            self._set_status(f"Updating {formatted}...")
        else:
            self._set_status(f"Registering {formatted}...")

        thread = threading.Thread(
            target=self._register_thread,
            args=(api_key, formatted, is_update),
            daemon=True,
        )
        thread.start()

    def _register_thread(self, api_key, knumber, is_update):
        try:
            if is_update:
                item = self._existing_item
            else:
                # Search for existing item by name
                GLib.idle_add(self._set_status, "Discovering subfolders...")
                folder_ids = []
                for fid in get_stage_folder_ids("spec"):
                    folder_ids.extend(list_subfolders(api_key, fid))
                GLib.idle_add(
                    self._set_status,
                    f"Searching {len(folder_ids)} folder(s) for '{knumber}'...",
                )
                results = search_item_by_name(api_key, folder_ids, knumber)
                if results:
                    item = results[0]
                else:
                    item = create_item(api_key, get_stage_folder_ids("spec")[0], knumber)
                    if not item:
                        GLib.idle_add(self._on_register_complete, False, "Failed to create item.")
                        return

            item_id = item["id"]
            info = self._system_info or {}
            if info:
                success = update_item(api_key, item_id, info)
                if not success:
                    GLib.idle_add(self._on_register_complete, False, "Failed to update item.")
                    return

            GLib.idle_add(self._on_register_complete, True, None)
        except Exception as e:
            GLib.idle_add(self._on_register_complete, False, str(e))

    def _on_register_complete(self, success, error):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if success:
            self._submitted = True
            # Write K-Number to EFI variable
            knumber = Utils.format_knumber(self.knumber_entry.get_text().strip())
            if knumber:
                Utils.write_kramden_number_efivar(knumber)
            if self.register_button.get_label() == "Update":
                self._set_status("Update successful!")
            else:
                self._set_status("Registration successful!")
            if self.next:
                self.next()
                self.skip = True
        else:
            self._set_status(f"Failed: {error}", error=True)
            self.register_button.set_sensitive(True)
            self.knumber_entry.set_sensitive(True)

    def _populate_system_info(self):
        if not self._system_info:
            return

        # Display order
        field_order = [
            "Brand", "Model", "CPU", "RAM", "Storage",
            "Serial# Scanner", "Item Type", "Graphics", "Battery Health",
        ]

        for field in field_order:
            value = self._system_info.get(field)
            if value is None:
                continue
            row = Adw.ActionRow()
            row.set_title(field)
            if field == "RAM":
                row.set_subtitle(f"{value} GB")
            elif field == "Storage":
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

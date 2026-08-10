"""Spec "Sortly" page: looks the device up in Sortly by serial number or
K-number, creates/updates its inventory record with gathered system info,
and later pushes the Speccing Notes datacode summary. Leaving the page
without a successful submission requires the staff override password."""

import gi
import threading
from datetime import datetime, time

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gtk, GLib

from utils import Utils
from sortly import (
    EXPANDED_FOLDER_IDS,
    INCOMING_FOLDER_ID,
    get_api_key,
    get_stage_folder_ids,
    list_subfolders,
    search_by_serial,
    search_item_by_name,
    create_item,
    update_item,
    get_system_info,
    sortly_error_message,
)

# Master switch for reporting each manual test page's failure reasons (e.g.
# "KB02|Keys do not work:A,B/TP01|Touchpad does not work at all" --
# see SpecComplete._gather_sortly_notes) back to Sortly as a follow-up
# update after the initial registration on this page -- see
# report_speccing_notes() below.
REPORT_SPECCING_NOTES_TO_SORTLY = True

# Must match the custom attribute's name on the Sortly item exactly --
# update_item() silently skips any field name it doesn't recognize.
SORTLY_SPECCING_NOTES_FIELD = "Speccing Notes"

# Separate master switch for reporting the tracking sheet's generation
# date back to Sortly as its own "Spec Date" custom attribute -- kept
# independent of REPORT_SPECCING_NOTES_TO_SORTLY so this can be flipped on
# by itself for testing without also turning on Speccing Notes reporting
# (or vice versa). See report_spec_date() below.
REPORT_SPEC_DATE_TO_SORTLY = True

# Must match the custom attribute's name on the Sortly item exactly --
# update_item() silently skips any field name it doesn't recognize.
SORTLY_SPEC_DATE_FIELD = "Spec Date"


class SortlyRegister(Adw.Bin):
    """Spec Sortly page: serial/K-number search, record create/update, staff override."""

    def __init__(self):
        super().__init__()
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.title = "Sortly Registration"
        self.next = None
        self.skip = False

        self._lookup_done = False
        self._submitted = False
        self._existing_item = None
        self._system_info = None
        self._user_edited = False
        self._folder_ids = []
        # Staff bypass for the "must submit to Sortly first" gate in
        # WizardWindow.on_next_clicked -- set once the override password is
        # accepted. Sortly is still not updated, so is_registered() stays
        # False and SpecComplete keeps flagging it on the tracking sheet.
        self.sortly_override = False

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

        self.expanded_search_button = Gtk.Button(label="Expanded Search")
        self.expanded_search_button.set_visible(False)
        self.expanded_search_button.set_sensitive(False)
        self.expanded_search_button.connect("clicked", self._on_expanded_search_clicked)

        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)

        knumber_box.append(knumber_label)
        knumber_box.append(self.knumber_entry)
        knumber_box.append(self.search_button)
        knumber_box.append(self.expanded_search_button)
        knumber_box.append(self.spinner)

        # Status label
        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)

        # System info collapsible section
        self._info_rows = []
        info_outer_list = Gtk.ListBox()
        info_outer_list.set_selection_mode(Gtk.SelectionMode.NONE)
        info_outer_list.add_css_class("boxed-list")

        self.info_expander = Adw.ExpanderRow()
        self.info_expander.set_title("Details")
        self.info_expander.set_expanded(False)
        info_outer_list.append(self.info_expander)

        # Register button
        self.register_button = Gtk.Button(label="Update")
        self.register_button.add_css_class("button-green")
        self.register_button.set_sensitive(False)
        self.register_button.set_visible(False)
        self.register_button.connect("clicked", self._on_register_clicked)

        # Staff-only bypass for techs who can't submit to Sortly (item not
        # found, Sortly down, etc.) -- same shared staff password as the
        # SpecInfo overrides.
        self.override_button = Gtk.Button(label="Override")
        self.override_button.set_halign(Gtk.Align.END)
        self.override_button.connect("clicked", self._on_override_clicked)

        vbox.append(knumber_box)
        vbox.append(self.status_label)
        vbox.append(info_outer_list)
        vbox.append(self.register_button)
        vbox.append(self.override_button)

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
            self._lookup_done = True
            return

        serial = self._system_info.get("Serial# Scanner")
        if not serial:
            self._set_status("Could not detect serial number.", error=True)
            self._lookup_done = True
            return

        # Temporarily disable the automatic serial lookup at startup in Spec.
        self._lookup_done = True
        self.search_button.set_visible(True)
        value = self.knumber_entry.get_text().strip()
        if value and Utils.format_knumber(value) and not self._submitted:
            self.search_button.set_sensitive(True)
        self._set_status(
            "Automatic serial lookup is temporarily disabled. Enter a K-number and search."
        )

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
            self._set_status(f"Found existing record: {item_name}")
            self.register_button.set_visible(True)
            self.register_button.set_sensitive(True)
        else:
            self._set_status(
                "No existing record found for this serial. Enter a K-number and search. Registration requires staff approval."
            )
            self.search_button.set_visible(True)
            # Enable search button if there's already a valid K-number
            value = self.knumber_entry.get_text().strip()
            if value and Utils.format_knumber(value) and not self._submitted:
                self.search_button.set_sensitive(True)

    def _on_knumber_changed(self, entry):
        self._user_edited = True
        self.expanded_search_button.set_visible(False)
        self.expanded_search_button.set_sensitive(False)
        if self._lookup_done and not self.search_button.get_visible():
            self.search_button.set_visible(True)
        value = entry.get_text().strip()
        formatted = Utils.format_knumber(value) if value else None

        if not value:
            self.register_button.set_visible(False)
            self.register_button.set_sensitive(False)
            self.search_button.set_sensitive(False)
            return

        if not formatted:
            self.register_button.set_visible(False)
            self.register_button.set_sensitive(False)
            self.search_button.set_sensitive(False)
            self._set_status("Invalid K-number format.", error=True)
            return

        self._set_status("")

        if self.search_button.get_visible():
            # Serial was not found — require explicit K-number search
            self._existing_item = None
            self.register_button.set_visible(False)
            self.register_button.set_sensitive(False)
            self.search_button.set_sensitive(not self._submitted)
        else:
            # Serial was found — existing behavior
            if self._existing_item and formatted == self._existing_item.get("name"):
                self.register_button.set_visible(True)
                self.register_button.set_sensitive(
                    not self._submitted and self._lookup_done
                )
            else:
                self.register_button.set_visible(False)
                self.register_button.set_sensitive(False)

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

        if not Utils.is_network_connected():
            self._show_wifi_warning()
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            self._set_status(str(e), error=True)
            return

        self.search_button.set_sensitive(False)
        self.expanded_search_button.set_sensitive(False)
        self.register_button.set_visible(False)
        self.register_button.set_sensitive(False)
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
            GLib.idle_add(
                self._on_search_complete, None, knumber, sortly_error_message(e)
            )
            return
        GLib.idle_add(self._on_search_complete, results, knumber, None)

    def _on_search_complete(self, results, knumber, error):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if error:
            self._set_status(f"Search failed: {error}", error=True)
            self.search_button.set_sensitive(True)
            return

        if results:
            self._existing_item = results[0]
            self._set_status(f"Found existing record: {knumber}")
            self.register_button.set_visible(True)
            self.register_button.set_sensitive(not self._submitted)
            self.expanded_search_button.set_visible(False)
            self.expanded_search_button.set_sensitive(False)
            self.search_button.set_visible(True)
        else:
            self._existing_item = None
            self._set_status(f"No record found for {knumber}.")
            self.register_button.set_visible(False)
            self.register_button.set_sensitive(False)
            if EXPANDED_FOLDER_IDS:
                self.expanded_search_button.set_visible(True)
                self.expanded_search_button.set_sensitive(True)
                self.search_button.set_visible(False)

    def _on_expanded_search_clicked(self, button):
        raw_value = self.knumber_entry.get_text().strip()
        formatted = Utils.format_knumber(raw_value)
        if not formatted:
            self._set_status("Invalid K-number format.", error=True)
            return

        if not Utils.is_network_connected():
            self._show_wifi_warning()
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            self._set_status(str(e), error=True)
            return

        self.search_button.set_sensitive(False)
        self.expanded_search_button.set_sensitive(False)
        self.register_button.set_visible(False)
        self.register_button.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.start()
        self._set_status(f"Expanded search for '{formatted}' in Sortly...")

        thread = threading.Thread(
            target=self._expanded_search_knumber_thread,
            args=(api_key, formatted),
            daemon=True,
        )
        thread.start()

    def _expanded_search_knumber_thread(self, api_key, knumber):
        try:
            GLib.idle_add(self._set_status, "Discovering expanded folders...")
            folder_ids = []
            for fid in EXPANDED_FOLDER_IDS:
                folder_ids.extend(list_subfolders(api_key, fid))
            GLib.idle_add(
                self._set_status,
                f"Searching {len(folder_ids)} expanded folder(s) for '{knumber}'...",
            )
            results = search_item_by_name(api_key, folder_ids, knumber)
        except Exception as e:
            GLib.idle_add(
                self._on_search_complete, None, knumber, sortly_error_message(e)
            )
            return
        GLib.idle_add(self._on_search_complete, results, knumber, None)

    def _on_register_clicked(self, button):
        if self._submitted:
            return
        self._do_register()

    def _do_register(self):
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

        # Only updates are supported; guard against accidentally creating new records
        if not self._existing_item or formatted != self._existing_item.get("name"):
            self._set_status("No existing record to update.", error=True)
            return

        is_update = True

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
                item = create_item(api_key, INCOMING_FOLDER_ID, knumber)
                if not item:
                    GLib.idle_add(
                        self._on_register_complete, False, "Failed to create item."
                    )
                    return

            item_id = item["id"]
            info = self._system_info or {}
            if info:
                success, error = update_item(api_key, item_id, info)
                if not success:
                    GLib.idle_add(
                        self._on_register_complete,
                        False,
                        error or "Failed to update item.",
                    )
                    return

            GLib.idle_add(self._on_register_complete, True, None)
        except Exception as e:
            GLib.idle_add(self._on_register_complete, False, sortly_error_message(e))

    def _on_register_complete(self, success, error):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if success:
            self._submitted = True
            # Write K-Number to EFI variable
            knumber = Utils.format_knumber(self.knumber_entry.get_text().strip())
            if knumber:
                Utils.write_kramden_number_efivar(knumber)
            self._set_status("Update successful!")
            if self.next:
                self.next()
                self.skip = True
        else:
            self._set_status(f"Failed: {error}", error=True)
            self.register_button.set_sensitive(True)
            self.knumber_entry.set_sensitive(True)

    def _on_override_clicked(self, button, on_success=None):
        dialog = Gtk.Window()
        dialog.set_title("Sortly Override")
        dialog.set_transient_for(self.get_root())
        dialog.set_modal(True)
        dialog.set_default_size(350, -1)
        dialog.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        label = Gtk.Label(label="Enter staff password to override:")
        box.append(label)

        entry = Gtk.PasswordEntry()
        entry.set_show_peek_icon(True)
        box.append(entry)

        error_label = Gtk.Label(label="")
        error_label.add_css_class("text-error")
        box.append(error_label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: dialog.close())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect(
            "clicked", self._on_override_ok, entry, error_label, dialog, on_success
        )
        btn_box.append(ok_btn)

        entry.connect(
            "activate",
            lambda e: self._on_override_ok(
                ok_btn, entry, error_label, dialog, on_success
            ),
        )

        box.append(btn_box)
        dialog.set_child(box)
        dialog.present()

    def _on_override_ok(self, button, entry, error_label, dialog, on_success=None):
        if entry.get_text() == "kramdenok":
            self.sortly_override = True
            self.override_button.set_visible(False)
            self._set_status("Sortly update overridden by staff.")
            dialog.close()
            if on_success:
                on_success()
        else:
            error_label.set_label("Incorrect password")

    def is_registered(self):
        """Whether this machine's Sortly record has been successfully
        updated from this page -- used by SpecComplete's System Info
        summary to flag "Sortly data not updated" before printing."""
        return self._submitted

    def report_speccing_notes(self, speccing_notes, on_complete=None):
        """Push the machine's aggregated Sortly notes string (see
        SpecComplete._gather_sortly_notes/manualtest._sortly_entry for
        the "<code>|<description>[:<locations>]" format, entries joined by
        "/") to Sortly as a follow-up update to the item registered on this
        page. Called from SpecComplete once every manual test page has
        reported in -- those results don't exist yet when _do_register()
        runs at the start of the wizard, so this fires later instead.

        `on_complete`, if given, is called as `on_complete(success, error)`
        -- via GLib.idle_add once the background request finishes, so it's
        always safe to touch widgets from it -- so a caller that needs to
        know the outcome (see SpecComplete.complete(), which blocks
        powering off the machine on this) can react to it. It still fires
        (with success=True) for every case below that skips the network
        call entirely, since none of them represent an actual failure to
        report; the fire-and-forget call from _generate_tracking_sheet
        passes no callback and doesn't care either way.
        """
        if not REPORT_SPECCING_NOTES_TO_SORTLY:
            if on_complete:
                GLib.idle_add(on_complete, True, None)
            return
        if not self._existing_item:
            if on_complete:
                GLib.idle_add(
                    on_complete,
                    False,
                    "This machine has no Sortly record to update -- "
                    "registration on the Sortly Registration page never "
                    "completed.",
                )
            return
        if not speccing_notes:
            # Nothing to report (no defects found) -- leave the existing
            # Sortly record's Speccing Notes field alone rather than making
            # an unnecessary API call.
            if on_complete:
                GLib.idle_add(on_complete, True, None)
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            print(f"Skipping Speccing Notes report: {e}")
            if on_complete:
                GLib.idle_add(on_complete, False, str(e))
            return

        item_id = self._existing_item["id"]
        thread = threading.Thread(
            target=self._report_speccing_notes_thread,
            args=(api_key, item_id, speccing_notes, on_complete),
            daemon=True,
        )
        thread.start()

    def _report_speccing_notes_thread(
        self, api_key, item_id, speccing_notes, on_complete
    ):
        try:
            success, error = update_item(
                api_key, item_id, {SORTLY_SPECCING_NOTES_FIELD: speccing_notes}
            )
            if not success:
                print(f"Failed to report Speccing Notes to Sortly: {error}")
        except Exception as e:
            success, error = False, sortly_error_message(e)
            print(f"Failed to report Speccing Notes to Sortly: {error}")
        if on_complete:
            GLib.idle_add(on_complete, success, error)

    def report_spec_date(self, spec_date, on_complete=None):
        """Push the date the tracking sheet was generated to Sortly as a
        follow-up update to the item registered on this page, mirroring
        report_speccing_notes() above but gated by its own
        REPORT_SPEC_DATE_TO_SORTLY switch (testing-only, independent of
        Speccing Notes reporting) instead. Called from SpecComplete as
        soon as tracking sheet generation starts, in parallel with the PDF
        itself, passing the same date that gets stamped in the PDF's
        "Generated" line. May be called again by the same caller's retry
        button if the first attempt failed.

        `on_complete`, if given, is called as `on_complete(success, error)`
        via GLib.idle_add once the background request finishes -- see
        report_speccing_notes() for the full rationale, which applies
        identically here.
        """
        if not REPORT_SPEC_DATE_TO_SORTLY:
            if on_complete:
                GLib.idle_add(on_complete, True, None)
            return
        if not self._existing_item:
            if on_complete:
                GLib.idle_add(
                    on_complete,
                    False,
                    "This machine has no Sortly record to update -- "
                    "registration on the Sortly Registration page never "
                    "completed.",
                )
            return

        try:
            api_key = get_api_key()
        except EnvironmentError as e:
            print(f"Skipping spec date report: {e}")
            if on_complete:
                GLib.idle_add(on_complete, False, str(e))
            return

        item_id = self._existing_item["id"]
        thread = threading.Thread(
            target=self._report_spec_date_thread,
            args=(api_key, item_id, spec_date, on_complete),
            daemon=True,
        )
        thread.start()

    def _report_spec_date_thread(self, api_key, item_id, spec_date, on_complete):
        try:
            # A bare "YYYY-MM-DD" string gets rejected by Sortly with
            # "must be a datetime instance" -- this custom attribute is
            # provisioned on Sortly's side as a full Date & Time type, so
            # it needs a complete ISO 8601 datetime. Tag it with this
            # machine's actual UTC offset via astimezone() -- but even
            # with the correct offset attached, Sortly still displayed the
            # previous day, which means it isn't honoring the offset on
            # its end. Sending local *noon* instead of local midnight
            # keeps the calendar date correct no matter how Sortly (or
            # whatever timezone its UI renders in) interprets the
            # timestamp, since noon survives a shift of several hours
            # either direction without crossing into the next/previous
            # day.
            spec_datetime = (
                datetime.combine(spec_date, time(12, 0))
                .astimezone()
                .isoformat(timespec="milliseconds")
            )
            success, error = update_item(
                api_key,
                item_id,
                {SORTLY_SPEC_DATE_FIELD: spec_datetime},
            )
            if not success:
                print(f"Failed to report spec date to Sortly: {error}")
        except Exception as e:
            success, error = False, sortly_error_message(e)
            print(f"Failed to report spec date to Sortly: {error}")
        if on_complete:
            GLib.idle_add(on_complete, success, error)

    def _populate_system_info(self):
        if not self._system_info:
            return
        for row in self._info_rows:
            self.info_expander.remove(row)
        self._info_rows.clear()

        # Display order
        field_order = [
            "Brand",
            "Chassis Model",
            "CPU",
            "RAM",
            "Storage",
            "Serial# Scanner",
            "Item Type",
            "Graphics",
            "Battery Health",
        ]

        for field in field_order:
            value = self._system_info.get(field)
            if value is None:
                continue
            row = Adw.ActionRow()
            row.set_title(field)
            if field == "RAM":
                # Soldered/Replaceable only show if that kind of RAM is
                # actually present -- see Utils.get_memory_module_breakdown.
                subtitle_lines = [f"{value} GB"]
                soldered = self._system_info.get("RAM Soldered")
                if soldered:
                    subtitle_lines.append(f"Soldered: {soldered} GB")
                replaceable = self._system_info.get("RAM Replaceable")
                if replaceable:
                    subtitle_lines.append(f"Replaceable: {replaceable} GB")
                row.set_subtitle("\n".join(subtitle_lines))
            elif field == "Storage":
                row.set_subtitle(f"{value} GB")
            else:
                row.set_subtitle(str(value))
            self.info_expander.add_row(row)
            self._info_rows.append(row)

    def _show_wifi_warning(self):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="Not connected to a network",
            secondary_text="This laptop isn't connected to WiFi or Ethernet, so Sortly can't be reached. Connect to a network and try again.",
        )
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()

    def _set_status(self, message, error=False):
        self.status_label.set_label(message)
        if error:
            if not self.status_label.has_css_class("text-error"):
                self.status_label.add_css_class("text-error")
        else:
            if self.status_label.has_css_class("text-error"):
                self.status_label.remove_css_class("text-error")

import gi
import os
import subprocess
import threading

gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib
from utils import Utils
from generate_tracking_sheet import generate_tracking_sheet


class SpecComplete(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.title = "Kramden Spec Complete"
        self.skip = False
        self.sortly_register = None
        self.manual_test = None
        self.specinfo = None

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        page_header = Gtk.Label(label="Spec Complete")
        page_header.add_css_class("title-3")
        page_header.set_halign(Gtk.Align.START)

        # Overall pass/fail row
        complete_list = Gtk.ListBox()
        complete_list.set_selection_mode(Gtk.SelectionMode.NONE)
        complete_list.add_css_class("boxed-list")
        complete_list.set_valign(Gtk.Align.START)

        self.complete_row = Adw.ActionRow()
        self.complete_row.set_title("")
        complete_list.append(self.complete_row)

        # Left column: System Info
        specinfo_header = Gtk.Label(label="System Info")
        specinfo_header.add_css_class("title-3")
        specinfo_header.set_halign(Gtk.Align.START)

        self.specinfo_list = Gtk.ListBox()
        self.specinfo_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.specinfo_list.add_css_class("boxed-list")
        self.specinfo_list.set_valign(Gtk.Align.START)
        self.specinfo_list.set_hexpand(True)

        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left_col.set_hexpand(True)
        left_col.append(specinfo_header)
        left_col.append(self.specinfo_list)

        # Right column: Manual Tests
        manualtest_header = Gtk.Label(label="Manual Tests")
        manualtest_header.add_css_class("title-3")
        manualtest_header.set_halign(Gtk.Align.START)

        self.manualtest_list = Gtk.ListBox()
        self.manualtest_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.manualtest_list.add_css_class("boxed-list")
        self.manualtest_list.set_valign(Gtk.Align.START)
        self.manualtest_list.set_hexpand(True)

        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_col.set_hexpand(True)
        right_col.append(manualtest_header)
        right_col.append(self.manualtest_list)

        columns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        columns_box.append(left_col)
        columns_box.append(right_col)

        # Status label for tracking sheet feedback
        self.tracking_status = Gtk.Label(label="")
        self.tracking_status.set_xalign(0)
        self.tracking_status.set_wrap(True)

        # Print Tracking Sheet button
        self.tracking_button = Gtk.Button(label="Print Tracking Sheet")
        self.tracking_button.add_css_class("button-green")
        self.tracking_button.connect("clicked", self._on_tracking_clicked)

        vbox.append(page_header)
        vbox.append(complete_list)
        vbox.append(columns_box)
        vbox.append(self.tracking_status)
        vbox.append(self.tracking_button)

        self.set_child(vbox)

    def _clear_list(self, list_box):
        while True:
            child = list_box.get_first_child()
            if child is None:
                break
            list_box.remove(child)

    def _passed_row(self):
        row = Adw.ActionRow()
        row.set_title("<span foreground='#3fe35a'><b>Passed</b></span>")
        row.set_icon_name("emblem-ok-symbolic")
        return row

    def _failure_row(self, reason):
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(reason))
        row.set_icon_name("emblem-important-symbolic")
        row.add_css_class("text-error")
        return row

    def complete(self):
        print("SpecComplete: complete")
        utils = Utils()
        utils.complete_reset("spec")

    def _on_tracking_clicked(self, button):
        knumber = ""
        if self.sortly_register:
            raw = self.sortly_register.knumber_entry.get_text().strip()
            formatted = Utils.format_knumber(raw)
            knumber = formatted or raw

        state = self.state.get_value()
        spec_passed = all(state.values())

        manual_test_results = None
        if self.manual_test:
            manual_test_results = self.manual_test.get_all_test_results()

        self.tracking_button.set_sensitive(False)
        if not knumber:
            # TODO: remove this fallback once Sortly registration is required
            # before reaching this page. For now, allow printing a blank-K-number
            # sheet so techs aren't blocked when Sortly is unavailable.
            self.tracking_status.set_label(
                "No K-Number set — generating a sheet with a blank K-Number field..."
            )
        else:
            self.tracking_status.set_label("Generating tracking sheet...")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        thread = threading.Thread(
            target=self._generate_thread,
            args=(knumber, spec_passed, manual_test_results),
            daemon=True,
        )
        thread.start()

    def _generate_thread(self, knumber, spec_passed, manual_test_results):
        try:
            output_path = generate_tracking_sheet(
                knumber,
                spec_passed=spec_passed,
                manual_test_results=manual_test_results,
            )
            GLib.idle_add(self._on_generate_complete, output_path, None)
        except Exception as e:
            GLib.idle_add(self._on_generate_complete, None, str(e))

    def _on_generate_complete(self, output_path, error):
        self.tracking_button.set_sensitive(True)
        if error:
            self.tracking_status.set_label(f"Failed: {error}")
            self.tracking_status.add_css_class("text-error")
            return

        self.tracking_status.set_label(f"Saved: {output_path}")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        viewer = (
            "/usr/bin/evince"
            if os.path.exists("/usr/bin/evince")
            else "/usr/bin/papers"
        )
        try:
            subprocess.Popen([viewer, output_path])
        except Exception as e:
            self.tracking_status.set_label(
                f"Saved: {output_path} (could not open viewer: {e})"
            )

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("SpecComplete: on_shown")
        state = self.state.get_value()

        self._clear_list(self.specinfo_list)
        self._clear_list(self.manualtest_list)

        if all(state.values()):
            print("SpecComplete: All passed")
            self.complete_row.set_title("Kramden Spec Complete: <b>PASSED</b>!")
        else:
            print("SpecComplete: Failed")
            self.complete_row.set_title("Kramden Spec Complete: <b>FAILED</b>!")

        # System Info column
        if not state.get("SpecInfo", True) and self.specinfo:
            for reason in self.specinfo.get_failure_reasons():
                self.specinfo_list.append(self._failure_row(reason))
        else:
            self.specinfo_list.append(self._passed_row())

        # Manual Tests column
        if not state.get("ManualTest", True) and self.manual_test:
            for reason in self.manual_test.get_failure_reasons():
                self.manualtest_list.append(self._failure_row(reason))
        else:
            self.manualtest_list.append(self._passed_row())

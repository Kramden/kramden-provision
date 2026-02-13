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
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Kramden Spec Complete"
        self.skip = False
        self.sortly_register = None
        self.manual_test = None

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        self.title_row = Adw.ActionRow()
        self.title_row.set_title("<b>Kramden Spec Complete</b>")

        self.complete_row = Adw.ActionRow()
        self.complete_row.set_title("")

        list_box.append(self.title_row)
        list_box.append(self.complete_row)

        # Status label for tracking sheet feedback
        self.tracking_status = Gtk.Label(label="")
        self.tracking_status.set_xalign(0)
        self.tracking_status.set_wrap(True)

        # Print Tracking Sheet button
        self.tracking_button = Gtk.Button(label="Print Tracking Sheet")
        self.tracking_button.add_css_class("button-green")
        self.tracking_button.connect("clicked", self._on_tracking_clicked)

        vbox.append(list_box)
        vbox.append(self.tracking_status)
        vbox.append(self.tracking_button)

        self.set_child(vbox)

    def complete(self):
        print("SpecComplete: complete")
        utils = Utils()
        utils.complete_reset("spec")

    def _on_tracking_clicked(self, button):
        # Get K-number from Sortly registration page
        knumber = ""
        if self.sortly_register:
            raw = self.sortly_register.knumber_entry.get_text().strip()
            formatted = Utils.format_knumber(raw)
            knumber = formatted or raw

        if not knumber:
            self.tracking_status.set_label(
                "No K-Number set. Go back to the registration page."
            )
            self.tracking_status.add_css_class("text-error")
            return

        state = self.state.get_value()
        spec_passed = all(state.values())

        manual_test_results = None
        if self.manual_test:
            manual_test_results = self.manual_test.get_all_test_results()

        self.tracking_button.set_sensitive(False)
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
        if all(state.values()):
            print("SpecComplete: All passed")
            self.complete_row.set_title("Kramden Spec Complete: <b>PASSED</b>!")
            self.complete_row.set_subtitle(str(state))
        else:
            print("SpecComplete: Failed")
            self.complete_row.set_title("Kramden Spec Complete: <b>FAILED</b>!")
            self.complete_row.set_subtitle(str(state))

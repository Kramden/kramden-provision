import gi
import os
import re
import shlex
import subprocess
import tempfile
import threading
from datetime import date

gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib
from utils import Utils
from generate_tracking_sheet_v3 import generate_tracking_sheet, prefetch_tracking_sheet_data
from sortly_register import REPORT_DATACODES_TO_SORTLY

# Once the Manual Tests failure/incomplete list exceeds this many rows, the
# remainder spills into a second column instead of growing the page past the
# screen.
MANUALTEST_ROWS_PER_COLUMN = 5

# The tracking sheet printer at every station is a Brother MFC-L2710DW
# series; used to pick its CUPS queue out of whatever else is configured
# when falling back to USB or an existing cups-browsed queue (see
# _find_ipp_usb_port/_resolve_browsed_printer_name).
TRACKING_SHEET_PRINTER_MODEL = "mfc-l2710dw"

# Over the network there are two of these printers, physically labeled 1
# and 2 so volunteers can tell them apart. Each has its Bonjour/mDNS name
# set (in its own web admin) to "KramdenSpec1"/"KramdenSpec2" so
# _find_network_printers() can do the same -- see _resolve_printer_name().
# The tech-facing label shown on screen is spelled out separately (see
# _resolve_printer_name) rather than reusing this raw mDNS name.
NETWORK_PRINTER_NAME_RE = re.compile(r"kramden\s*spec\s*(\d+)", re.IGNORECASE)

# A minimal ipptool script requesting just the one attribute
# _printer_queued_job_count() needs -- $uri is filled in by ipptool itself
# from the URI passed on its command line.
QUEUED_JOB_COUNT_TEST = """{
    OPERATION Get-Printer-Attributes
    GROUP operation-attributes-tag
    ATTR charset attributes-charset utf-8
    ATTR language attributes-natural-language en
    ATTR uri printer-uri $uri
    ATTR keyword requested-attributes queued-job-count
    STATUS successful-ok
    EXPECT queued-job-count
}
"""


class SpecCompleteV3(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.title = "Kramden Spec Complete"
        self.skip = False
        self.sortly_register = None
        self.manual_test_pages = []
        self.specinfo = None
        self.on_navigate_to_page = None

        # Print Tracking Sheet's biggest cost (variable-font instancing,
        # discrete-GPU lookup) doesn't depend on anything the tech does in
        # the wizard, so warm it up now, in the background, while they work
        # through the manual test pages -- by the time they reach this page
        # and click Print, it should already be done.
        prefetch_tracking_sheet_data()

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

        # Second column, only populated/shown once the first column has more
        # than MANUALTEST_ROWS_PER_COLUMN rows -- keeps a long failure list
        # from growing the page past the screen instead of wrapping sideways.
        self.manualtest_list_2 = Gtk.ListBox()
        self.manualtest_list_2.set_selection_mode(Gtk.SelectionMode.NONE)
        self.manualtest_list_2.add_css_class("boxed-list")
        self.manualtest_list_2.set_valign(Gtk.Align.START)
        self.manualtest_list_2.set_hexpand(True)
        self.manualtest_list_2.set_visible(False)

        manualtest_lists_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        manualtest_lists_box.append(self.manualtest_list)
        manualtest_lists_box.append(self.manualtest_list_2)

        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_col.set_hexpand(True)
        right_col.append(manualtest_header)
        right_col.append(manualtest_lists_box)

        columns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        columns_box.append(left_col)
        columns_box.append(right_col)

        # Status label for tracking sheet feedback
        self.tracking_status = Gtk.Label(label="")
        self.tracking_status.set_xalign(0)
        self.tracking_status.set_wrap(True)

        # Tracking Sheet button: starts as "Review" (blue) to generate the PDF
        # and open it for a look; once that's done it flips to "Print" (green)
        # and the same button sends it straight to the printer with the paper
        # size forced to A5. Forcing A5 here -- rather than depending on the
        # printer's default media or a tech picking it in the viewer's print
        # dialog -- matters because every one of these machines is a fresh
        # boot with its own from-scratch CUPS state; a default or a manual
        # dialog selection on one machine doesn't carry over to the next one.
        self.tracking_button = Gtk.Button(label="Review Tracking Sheet")
        self.tracking_button.add_css_class("suggested-action")
        self.tracking_button.connect("clicked", self._on_tracking_clicked)
        self._tracking_output_path = None
        self._tracking_viewer_error = None
        self._tracking_ready_to_print = False
        self._tracking_initials = ""
        # The date.today() computed in _generate_tracking_sheet() and
        # stamped on the PDF -- reused there to kick off the Sortly
        # "Spec Date" report in parallel with PDF generation, so the two
        # can't disagree. See generate_tracking_sheet_v3.py's
        # generated_date parameter.
        self._tracking_generated_date = None
        # Tri-state outcome of the Sortly "Spec Date" report kicked off
        # from _generate_tracking_sheet(): None while no attempt has
        # resolved yet (still in flight, or none made because
        # self.sortly_register is unset), True/False once
        # _on_spec_date_report_complete() hears back. Combined with
        # _tracking_output_path in _refresh_tracking_status() to build the
        # status line, and drives whether the retry button below shows.
        self._spec_date_reported = None
        self._spec_date_error = None
        self.spec_date_retry_button = Gtk.Button(label="Retry Spec Date Update")
        self.spec_date_retry_button.connect(
            "clicked", self._on_spec_date_retry_clicked
        )
        self.spec_date_retry_button.set_visible(False)
        self.spec_date_retry_button.set_halign(Gtk.Align.START)
        # Set once the tech has clicked "Print Tracking Sheet" at least
        # once, so a subsequent click (e.g. because the sheet hasn't come
        # out yet) prompts for confirmation instead of silently queuing
        # another print job -- see _on_tracking_clicked().
        self._tracking_print_requested = False
        # Both must happen at least once (in order) before is_complete()
        # allows the wizard's "Complete" button to be clicked -- see
        # is_complete() and on_shown() below.
        self._tracking_reviewed = False
        self._tracking_printed = False
        # Set while complete() is waiting on the Sortly datacodes update
        # it kicked off (see _complete_with_sortly_report) -- keeps
        # is_complete() (and so the wizard's "Complete" button) disabled
        # for that window so a second click can't fire a duplicate report
        # or race the power-off dialog.
        self._sortly_send_in_progress = False
        # Tracks the "Power off in N seconds" dialog/countdown so a
        # response can cancel the pending timeout -- see
        # _show_sortly_success_dialog/_on_sortly_success_response.
        self._poweroff_countdown = 0
        self._poweroff_timeout_id = None
        # Set by spec_v3.py to WizardWindow.update_buttons, so the
        # "Complete" button's sensitivity updates immediately when review/
        # print finish, rather than waiting for the next page navigation.
        self.on_status_changed = None

        vbox.append(page_header)
        vbox.append(complete_list)
        vbox.append(columns_box)
        vbox.append(self.tracking_status)
        vbox.append(self.spec_date_retry_button)
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

    def _incomplete_row(self, page):
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(f"{page.title}: not filled out"))
        row.set_icon_name("emblem-important-symbolic")
        row.add_css_class("text-warning")
        row.set_activatable(True)
        row.connect("activated", self._on_incomplete_row_activated, page)
        return row

    def _on_incomplete_row_activated(self, row, page):
        if self.on_navigate_to_page:
            self.on_navigate_to_page(page)

    def complete(self):
        print("SpecCompleteV3: complete")
        if REPORT_DATACODES_TO_SORTLY and self.sortly_register:
            self._complete_with_sortly_report()
        else:
            self._power_off()

    def _complete_with_sortly_report(self):
        """Send this machine's aggregated datacodes to Sortly and block
        powering off until that's confirmed one way or the other -- see
        _on_sortly_report_complete for what happens next. Disables the
        "Complete" button for the duration (see is_complete()) so a
        double-click can't fire this twice."""
        self._sortly_send_in_progress = True
        if self.on_status_changed:
            self.on_status_changed()
        self.tracking_status.set_label("Sending Data Codes to Sortly...")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        notes = self._gather_sortly_notes()
        self.sortly_register.report_datacodes(
            notes, on_complete=self._on_sortly_report_complete
        )

    def _on_sortly_report_complete(self, success, error):
        self._sortly_send_in_progress = False
        if self.on_status_changed:
            self.on_status_changed()
        if success:
            self.tracking_status.set_label("Sortly information updated.")
            if self.tracking_status.has_css_class("text-error"):
                self.tracking_status.remove_css_class("text-error")
            self._show_sortly_success_dialog()
        else:
            self.tracking_status.set_label(f"Sortly update failed: {error}")
            self.tracking_status.add_css_class("text-error")
            self._show_sortly_failure_dialog(error)

    def _show_sortly_success_dialog(self):
        """Confirms the Sortly update succeeded and gives the tech a
        "Power Off" button -- but powers off automatically after a 10
        second countdown regardless of whether it's clicked, since the
        point of this dialog is just to make sure the tech saw the
        confirmation before the machine shuts down, not to make powering
        off conditional on them clicking anything."""
        self._poweroff_countdown = 10
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Sortly information updated",
            body=self._poweroff_countdown_body(),
        )
        dialog.add_response("power_off", "Power Off")
        dialog.set_response_appearance("power_off", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("power_off")
        # There's no way to opt out of powering off from here -- the
        # countdown below fires regardless, so treat any dismissal
        # (Escape, etc.) the same as clicking "Power Off".
        dialog.set_close_response("power_off")
        dialog.connect("response", self._on_sortly_success_response)
        dialog.present()
        self._poweroff_timeout_id = GLib.timeout_add(
            1000, self._tick_poweroff_countdown, dialog
        )

    def _poweroff_countdown_body(self):
        seconds = self._poweroff_countdown
        return (
            f"This machine will power off automatically in {seconds} "
            f"second{'s' if seconds != 1 else ''}. Click \"Power Off\" to "
            "do it now."
        )

    def _tick_poweroff_countdown(self, dialog):
        self._poweroff_countdown -= 1
        if self._poweroff_countdown <= 0:
            # Trigger the same response path as clicking/dismissing the dialog,
            # so _power_off() is called exactly once.
            self._poweroff_timeout_id = None
            dialog.response("power_off")
            return GLib.SOURCE_REMOVE
        dialog.set_body(self._poweroff_countdown_body())
        return GLib.SOURCE_CONTINUE

    def _on_sortly_success_response(self, dialog, response):
        # Reached if the tech clicks "Power Off" (or dismisses the
        # dialog) before the countdown finishes on its own -- cancel the
        # pending timeout so it doesn't also fire _power_off() a second
        # time once the machine is already on its way down.
        if self._poweroff_timeout_id is not None:
            GLib.source_remove(self._poweroff_timeout_id)
            self._poweroff_timeout_id = None
        self._power_off()

    def _show_sortly_failure_dialog(self, error):
        """Explains why the Sortly update failed and how to move past it
        -- does NOT power off the machine, since the whole point is that
        Sortly is not yet confirmed up to date. Clicking "Complete" again
        (once whatever's wrong is fixed) re-attempts the whole thing."""
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Couldn't update Sortly",
            body=(
                "This machine's Data Codes could not be sent to Sortly, "
                "so it has not been powered off.\n\n"
                f"Reason: {error}\n\n"
                "This is usually because the laptop isn't connected to "
                "WiFi or Ethernet right now, or because something about "
                "this machine's Sortly record needs fixing (e.g. the "
                "wrong K-Number was entered on the Sortly Registration "
                "page). Check the network connection, then click "
                '"Complete" again to retry. If it keeps failing, find a '
                "Staff member or Super Geek for help."
            ),
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()

    def _power_off(self):
        utils = Utils()
        utils.complete_reset("spec")

    def _on_tracking_clicked(self, button):
        if self._tracking_ready_to_print:
            if self._tracking_print_requested:
                self._prompt_reprint_confirmation()
            else:
                self._print_tracking_sheet()
        else:
            self._prompt_for_initials()

    def _prompt_reprint_confirmation(self):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Print Again?",
            body=(
                "Please wait up to 10 seconds for the tracking sheet to "
                "print before trying again. If you are sure you want to "
                "print again, click the button below.\n\n"
                "If the printer is not receiving your print request, "
                "please take a mental note of any failures, or write a "
                "note so you don't forget, and restart the laptop. Fill "
                "out all of the manual test pages just like before, and "
                "retry printing. If it still doesn't work, find a Super "
                "Geek or Staff Member to help you."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("print_again", "Print Again")
        dialog.set_response_appearance(
            "print_again", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_reprint_confirmation_response)
        dialog.present()

    def _on_reprint_confirmation_response(self, dialog, response):
        if response == "print_again":
            self._print_tracking_sheet()

    def _prompt_for_initials(self):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Type Initials Here",
            body="Enter your initials to print on the tracking sheet.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("continue", "Continue")
        dialog.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("continue")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_placeholder_text("Initials")
        entry.set_halign(Gtk.Align.CENTER)
        entry.set_max_length(10)
        dialog.set_extra_child(entry)

        dialog.set_response_enabled("continue", False)
        entry.connect(
            "changed",
            lambda e: dialog.set_response_enabled(
                "continue", bool(e.get_text().strip())
            ),
        )
        # Makes Enter in the entry activate the dialog's default response
        # ("continue") exactly as if its button were clicked -- same code
        # path, so it respects "continue" being disabled while the entry
        # is empty, and reliably closes the dialog (a plain "activate"
        # signal handler calling dialog.response() directly does not).
        entry.set_activates_default(True)

        dialog.connect("response", self._on_initials_response, entry)
        # Without this, keyboard focus stays on the "Review Tracking Sheet"
        # button that was just clicked to open this dialog, so pressing
        # Enter re-triggers that button instead of submitting the initials.
        self.tracking_button.set_sensitive(False)
        dialog.present()
        entry.grab_focus()

    def _on_initials_response(self, dialog, response, entry):
        if response != "continue":
            self.tracking_button.set_sensitive(True)
            return
        self._tracking_initials = entry.get_text().strip()
        self._generate_tracking_sheet()

    def _gather_sortly_notes(self):
        """Every manual test page's failure reasons, formatted for
        Sortly's "Speccing Notes" custom attribute (see
        manualtest_v3.TogglePage.get_sortly_entries/_sortly_entry) and
        concatenated across all pages into one "/"-joined string with no
        spaces around any delimiter, e.g. "KB01|Keys do not
        work:A,B/TP01|Touchpad does not work at all" -- the format fed to
        SortlyRegister.report_datacodes(). Pages that passed, weren't
        tested, or have no get_sortly_entries() (SpecInfo isn't a manual
        test page) contribute nothing."""
        entries = []
        for page in self.manual_test_pages:
            if hasattr(page, "get_sortly_entries"):
                entries.extend(page.get_sortly_entries())
        return "/".join(entries)

    def _generate_tracking_sheet(self):
        knumber = ""
        if self.sortly_register:
            raw = self.sortly_register.knumber_entry.get_text().strip()
            formatted = Utils.format_knumber(raw)
            knumber = formatted or raw

        state = self.state.get_value()
        spec_passed = all(state.values())

        manual_test_results = {}
        notes_entries = []
        for page in self.manual_test_pages:
            manual_test_results[page.key] = page.get_result()
            if hasattr(page, "get_notes_entries"):
                notes_entries.extend(page.get_notes_entries())

        # The tracking sheet's "Sound:" field has no dedicated test page --
        # it's derived from the Browser page (video and audio playback):
        # GOOD unless Browser failed specifically due to an "Audio" defect.
        browser_page = next(
            (p for p in self.manual_test_pages if p.key == "Browser"), None
        )
        if browser_page is not None:
            if not browser_page.is_complete():
                manual_test_results["Sound"] = "Untested"
            elif not browser_page.passed and browser_page.has_reason("Audio"):
                manual_test_results["Sound"] = "Fail"
            else:
                manual_test_results["Sound"] = "Pass"

        if self.specinfo is not None:
            notes_entries.extend(self.specinfo.get_notes_entries())

        if self.sortly_register:
            self.sortly_register.report_datacodes(self._gather_sortly_notes())

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

        # Computed once here and threaded through to both the PDF (as
        # generated_date) and the Sortly "Spec Date" report kicked off
        # immediately below -- so the two can't disagree if generation
        # happens to straddle a midnight boundary.
        self._tracking_generated_date = date.today()

        # Fired here, in parallel with PDF generation below, rather than
        # waiting for it to finish -- the report doesn't depend on the PDF
        # existing, and doing both at once means a slow Sortly response
        # doesn't add to the wait before the tech sees the reviewed sheet.
        # _refresh_tracking_status() reconciles whichever of the two
        # finishes last against the other's already-known outcome.
        self._spec_date_reported = None
        self._spec_date_error = None
        self.spec_date_retry_button.set_visible(False)
        if self.sortly_register:
            self.sortly_register.report_spec_date(
                self._tracking_generated_date,
                on_complete=self._on_spec_date_report_complete,
            )

        thread = threading.Thread(
            target=self._generate_thread,
            args=(
                knumber,
                spec_passed,
                manual_test_results,
                notes_entries,
                self._tracking_generated_date,
            ),
            daemon=True,
        )
        thread.start()

    def _generate_thread(
        self, knumber, spec_passed, manual_test_results, notes_entries, generated_date
    ):
        try:
            output_path = generate_tracking_sheet(
                knumber,
                spec_passed=spec_passed,
                manual_test_results=manual_test_results,
                notes_entries=notes_entries,
                initials=self._tracking_initials,
                generated_date=generated_date,
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

        self._tracking_output_path = output_path
        self._tracking_viewer_error = None
        self._refresh_tracking_status()
        self._tracking_ready_to_print = True
        self._tracking_reviewed = True
        self.tracking_button.set_label("Print Tracking Sheet")
        self.tracking_button.remove_css_class("suggested-action")
        self.tracking_button.add_css_class("button-green")

        viewer = (
            "/usr/bin/evince"
            if os.path.exists("/usr/bin/evince")
            else "/usr/bin/papers"
        )
        # Evince/Papers persists its last window state (maximized/fullscreen)
        # in GSettings and restores it on the next launch -- these are
        # freshly-imaged, single-use machines, so without resetting this
        # first the viewer tends to come up covering the whole screen
        # instead of a normal window.
        schema = (
            "org.gnome.Evince.Default"
            if viewer.endswith("evince")
            else "org.gnome.Papers.Default"
        )
        try:
            subprocess.run(
                ["gsettings", "set", schema, "window-maximized", "false"],
                check=False,
                capture_output=True,
                timeout=5,
            )
            # "maximized" and "fullscreen" are tracked separately -- e.g.
            # a tech hitting F11 while reviewing a previous sheet leaves
            # fullscreen=true even though the window was never maximized
            # -- so both need resetting or the viewer can still come up
            # covering the whole screen and blocking the app underneath.
            subprocess.run(
                ["gsettings", "set", schema, "fullscreen", "false"],
                check=False,
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
        try:
            subprocess.Popen([viewer, output_path])
        except Exception as e:
            self._tracking_viewer_error = str(e)
            self._refresh_tracking_status()
        if self.on_status_changed:
            self.on_status_changed()

    def _refresh_tracking_status(self):
        """Rebuild the tracking-sheet status line from whatever's currently
        known about the PDF and the Sortly "Spec Date" report -- the two
        are kicked off in parallel from _generate_tracking_sheet() and can
        resolve in either order, so both _on_generate_complete() and
        _on_spec_date_report_complete() funnel through here instead of each
        writing the label directly and risking clobbering the other's
        result."""
        if self._tracking_output_path is None:
            # PDF generation hasn't finished yet -- leave whatever status
            # it's currently showing (e.g. "Generating tracking sheet...")
            # alone rather than getting ahead of it.
            return

        line = f"Saved: {self._tracking_output_path}"
        if self._tracking_viewer_error:
            line += f" (could not open viewer: {self._tracking_viewer_error})"

        if self._spec_date_reported is None:
            spec_line = "Spec date: updating Sortly..."
        elif self._spec_date_reported:
            spec_line = "Spec date: updated in Sortly."
        else:
            spec_line = f"Spec date: FAILED to update in Sortly ({self._spec_date_error})"

        self.tracking_status.set_label(f"{line}\n{spec_line}")

        has_error = bool(self._tracking_viewer_error) or self._spec_date_reported is False
        if has_error:
            self.tracking_status.add_css_class("text-error")
        elif self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        self.spec_date_retry_button.set_visible(self._spec_date_reported is False)

    def _on_spec_date_report_complete(self, success, error):
        """Record the outcome of the Sortly "Spec Date" report kicked off
        from _generate_tracking_sheet() and refresh the status line to
        show it -- this fires asynchronously and can resolve before or
        after PDF generation finishes, so _refresh_tracking_status()
        reconciles it against whatever else is known rather than writing
        the label directly here."""
        self._spec_date_reported = success
        self._spec_date_error = error
        self._refresh_tracking_status()

    def _on_spec_date_retry_clicked(self, button):
        if not self.sortly_register or self._tracking_generated_date is None:
            return
        self._spec_date_reported = None
        self._spec_date_error = None
        self.spec_date_retry_button.set_visible(False)
        self._refresh_tracking_status()
        self.sortly_register.report_spec_date(
            self._tracking_generated_date,
            on_complete=self._on_spec_date_report_complete,
        )

    def _resolve_printer_name(self):
        """Pick which CUPS destination to print to, trying three tiers in
        order and re-resolving from scratch every time (never trusting a
        queue found on a previous print attempt), since which of these is
        reachable can change between one tracking sheet and the next:

        1. USB, if the printer is plugged in -- talk straight to the local
           loopback IPP service Ubuntu's ipp-usb daemon already runs for
           it, via our own dedicated queue (see _find_ipp_usb_port/
           _ensure_direct_usb_queue).
        2. The network otherwise -- there are two network printers
           ("KramdenSpec1"/"KramdenSpec2" over mDNS, physically labeled 1
           and 2 so volunteers can tell them apart), so resolve both of
           their current addresses straight from mDNS/DNS-SD, talk
           directly to each one's own IPP endpoint via our own dedicated
           queue (see _find_network_printers/_ensure_direct_network_queue),
           and print to whichever one's real queue is shortest right now
           (see _printer_queued_job_count). This is interface-agnostic: it
           works the same whether this laptop reaches the printers over
           WiFi or over Ethernet -- mDNS discovery just needs *some* path
           to their network segment, not a direct physical link to them.
           This is tried automatically whenever USB isn't available, so
           WiFi (or Ethernet) is always the default the moment USB isn't
           an option.
        3. Matching an existing cups-browsed-discovered queue by name, as
           a last resort if neither of the above found anything (e.g.
           avahi-browse isn't installed, or a printer answers IPP
           requests but isn't advertising itself over mDNS for some
           reason).

        Both dedicated-queue tiers deliberately bypass cups-browsed's own
        auto-discovered queues, since those have repeatedly proven
        unreliable: an "implicitclass" queue hangs/fails whenever
        cups-browsed sees the same printer over more than one path (USB
        and network at once) and can't resolve a destination, and a
        "dnssd" (network) queue fails outright if the printer isn't
        actually reachable on the network at that moment (e.g. it's only
        really connected via USB right now, even though a stale mDNS
        record for it is still floating around).

        Returns (queue_name, display_label). display_label is a
        tech-facing name like "Kramden Spec Printer 1" for the network
        tier, so the UI can tell the tech which of the two physical,
        physically-labeled printers the job actually went to -- or None
        for the USB and last-resort tiers, which only ever deal with a
        single printer.
        """
        usb_port = self._find_ipp_usb_port()
        if usb_port:
            queue = self._ensure_direct_usb_queue(usb_port)
            if queue:
                return queue, None

        network_printers = self._find_network_printers()
        if network_printers:
            candidates = []
            for printer in network_printers:
                queue = self._ensure_direct_network_queue(
                    printer["address"],
                    printer["port"],
                    printer["resource_path"],
                    printer["label"],
                )
                if not queue:
                    continue
                depth = self._printer_queued_job_count(
                    printer["address"], printer["port"], printer["resource_path"]
                )
                candidates.append((depth, printer["label"], queue))
            if candidates:
                # Prefer a printer whose queue depth we could actually
                # measure, then the shortest queue, then (only if still
                # tied -- e.g. neither answered) the lower-numbered
                # printer, so the choice is deterministic rather than
                # depending on avahi's report order.
                candidates.sort(
                    key=lambda c: (c[0] is None, c[0] if c[0] is not None else 0, c[1])
                )
                _, label, queue = candidates[0]
                return queue, f"Kramden Spec Printer {label}"

        return self._resolve_browsed_printer_name(), None

    def _find_ipp_usb_port(self):
        """Return the local loopback port ipp-usb is serving the tracking
        sheet printer on, if it's currently plugged in via USB."""
        try:
            result = subprocess.run(
                ["ipp-usb", "status"], capture_output=True, text=True, timeout=5
            )
        except Exception:
            return None

        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            match = re.match(r"\s*\d+\.\s+.*\s(\d+)\s+\"(.+)\"\s*$", line)
            if not match:
                continue
            port, model = match.group(1), match.group(2)
            if TRACKING_SHEET_PRINTER_MODEL not in model.lower().replace("_", "-"):
                continue
            status_line = lines[i + 1].strip().lower() if i + 1 < len(lines) else ""
            if "status: ok" in status_line:
                return port
        return None

    def _ensure_direct_usb_queue(self, port):
        """Create (or update, harmlessly, if it already exists) a queue
        pointed straight at ipp-usb's loopback service for this printer."""
        queue_name = "KramdenTrackingSheetPrinter"
        try:
            subprocess.run(
                [
                    "lpadmin",
                    "-p", queue_name,
                    "-E",
                    "-v", f"ipp://localhost:{port}/ipp/print",
                    "-m", "everywhere",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return queue_name
        except Exception:
            return None

    def _find_network_printers(self):
        """Resolve both network tracking-sheet printers' current
        addresses, ports, and IPP resource paths straight from mDNS/
        DNS-SD, for whichever of the two ("KramdenSpec1"/"KramdenSpec2")
        are reachable on the network right now. Re-resolved fresh on
        every print attempt (like _find_ipp_usb_port() does for the USB
        path) so a changed DHCP lease, or a printer that's only just come
        up, doesn't get stuck on a stale address. This is
        interface-agnostic -- it works the same whether this laptop is on
        WiFi or Ethernet, since mDNS discovery just needs some path to
        the printers' network segment, not a direct physical link to
        them.

        Returns a list of dicts: {"label": <int>, "address", "port",
        "resource_path"} -- one per printer found (zero, one, or two),
        in whatever order avahi-browse reported them. The caller is
        responsible for choosing between them (see _resolve_printer_name)."""
        try:
            result = subprocess.run(
                ["avahi-browse", "-r", "-p", "-t", "_ipp._tcp"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return []

        found = {}
        for line in result.stdout.splitlines():
            if not line.startswith("="):
                continue
            fields = line.split(";")
            if len(fields) < 10:
                continue
            protocol, name, address, port, txt = (
                fields[2], fields[3], fields[7], fields[8], fields[9]
            )
            if protocol != "IPv4":
                # Keep the ipp:// URI construction below simple -- an
                # IPv4 record for the same printer is always advertised
                # alongside any IPv6 one.
                continue
            match = NETWORK_PRINTER_NAME_RE.search(name)
            if not match:
                continue
            label = int(match.group(1))
            # avahi can report the same printer more than once (e.g. one
            # record per network interface) -- keep the first sighting
            # of each label rather than treating it as a second printer.
            if label in found:
                continue
            found[label] = {
                "label": label,
                "address": address,
                "port": port,
                "resource_path": self._extract_ipp_resource_path(txt),
            }
        return list(found.values())

    @staticmethod
    def _extract_ipp_resource_path(txt_field):
        """Pull the "rp=" (resource path) token out of avahi-browse's -p
        TXT field, e.g. 'rp=ipp/print' -> 'ipp/print' -- falls back to
        "ipp/print", the IPP Everywhere convention this file's other IPP
        URIs already assume, if the printer's TXT records don't advertise
        one."""
        for token in shlex.split(txt_field):
            if token.startswith("rp="):
                return token[len("rp="):]
        return "ipp/print"

    def _ensure_direct_network_queue(self, address, port, resource_path, label):
        """Create (or update, harmlessly, if it already exists) a queue
        pointed straight at this network printer's own IPP endpoint --
        same "bypass cups-browsed's flaky auto-discovered queues, talk
        directly" approach as _ensure_direct_usb_queue(), just reaching
        the printer over the network instead of ipp-usb's loopback. A
        separate queue per label (KramdenTrackingSheetPrinterNetwork1/2)
        so both network printers can have a live queue at once instead
        of one clobbering the other's."""
        queue_name = f"KramdenTrackingSheetPrinterNetwork{label}"
        try:
            subprocess.run(
                [
                    "lpadmin",
                    "-p", queue_name,
                    "-E",
                    "-v", f"ipp://{address}:{port}/{resource_path}",
                    "-m", "everywhere",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return queue_name
        except Exception:
            return None

    def _printer_queued_job_count(self, address, port, resource_path):
        """How many jobs are queued at the printer itself right now, via
        a direct IPP Get-Printer-Attributes query -- not this laptop's
        own local CUPS state, which would only ever reflect jobs *this*
        laptop has submitted. Since both network printers are shared by
        every spec station at once, load-balancing between them has to
        be based on each printer's real queue, not a per-laptop count.

        Returns None if it couldn't be determined (e.g. ipptool isn't
        installed, or the printer didn't answer), so the caller can fall
        back to some other tie-breaker instead of treating "unknown" the
        same as "empty"."""
        uri = f"ipp://{address}:{port}/{resource_path}"
        test_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".test", delete=False
            ) as f:
                f.write(QUEUED_JOB_COUNT_TEST)
                test_path = f.name
            result = subprocess.run(
                ["ipptool", "-t", uri, test_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return None
        finally:
            if test_path:
                try:
                    os.unlink(test_path)
                except OSError:
                    pass

        match = re.search(r"queued-job-count[^=]*=\s*(\d+)", result.stdout)
        return int(match.group(1)) if match else None

    def _resolve_browsed_printer_name(self):
        """Match an existing cups-browsed-discovered queue by name/
        description, preferring a non-implicitclass one, least-busy first.
        See _resolve_printer_name() for why this is only a fallback."""
        try:
            result = subprocess.run(
                ["lpstat", "-l", "-p"], capture_output=True, text=True, timeout=5
            )
            device_result = subprocess.run(
                ["lpstat", "-v"], capture_output=True, text=True, timeout=5
            )
        except Exception:
            return None

        device_uris = {}
        for line in device_result.stdout.splitlines():
            # "device for <name>: <uri>"
            if line.startswith("device for "):
                name, _, uri = line[len("device for "):].partition(":")
                device_uris[name.strip()] = uri.strip()

        candidates = []
        current_name = None
        for line in result.stdout.splitlines():
            if line.startswith("printer "):
                current_name = line.split()[1]
            elif current_name and line.strip().startswith("Description:"):
                description = line.split(":", 1)[1].strip()
                haystack = f"{current_name} {description}".lower().replace("_", "-")
                if TRACKING_SHEET_PRINTER_MODEL in haystack:
                    candidates.append(current_name)

        if not candidates:
            return None

        direct = [
            c for c in candidates
            if not device_uris.get(c, "").startswith("implicitclass://")
        ]
        pool = direct or candidates
        if len(pool) == 1:
            return pool[0]
        return min(pool, key=self._queued_job_count)

    def _queued_job_count(self, printer_name):
        try:
            result = subprocess.run(
                ["lpstat", "-o", printer_name], capture_output=True, text=True, timeout=5
            )
            return len([line for line in result.stdout.splitlines() if line.strip()])
        except Exception:
            return 0

    def _print_tracking_sheet(self):
        output_path = self._tracking_output_path
        if not output_path:
            return

        self._tracking_print_requested = True
        self.tracking_button.set_sensitive(False)
        self.tracking_status.set_label("Printing...")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        thread = threading.Thread(
            target=self._print_thread, args=(output_path,), daemon=True
        )
        thread.start()

    def _print_thread(self, output_path):
        printer, label = self._resolve_printer_name()
        if not printer:
            GLib.idle_add(
                self._on_print_complete,
                "No Brother MFC-L2710DW printer found. Check the USB cable, "
                "or that Kramden Spec Printer 1 or 2 is powered on and "
                "connected to the network.",
                None,
            )
            return
        try:
            # print-scaling=none: the sheet is already sized exactly to A5,
            # so scaling should never kick in -- if it did, that's a sign
            # something about the sheet or printer changed and is worth
            # noticing rather than silently compensating for.
            subprocess.run(
                [
                    "lp",
                    "-d",
                    printer,
                    "-o",
                    "media=A5",
                    "-o",
                    "print-scaling=none",
                    output_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            GLib.idle_add(self._on_print_complete, None, label)
        except subprocess.CalledProcessError as e:
            GLib.idle_add(self._on_print_complete, e.stderr.strip() or str(e), None)
        except Exception as e:
            GLib.idle_add(self._on_print_complete, str(e), None)

    def _on_print_complete(self, error, label=None):
        self.tracking_button.set_sensitive(True)
        if error:
            self.tracking_status.set_label(f"Print failed: {error}")
            self.tracking_status.add_css_class("text-error")
            return

        self.tracking_status.set_label(f"Sent to {label}." if label else "Sent to printer.")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")
        self._tracking_printed = True
        if self.on_status_changed:
            self.on_status_changed()

    def is_complete(self):
        """The wizard's "Complete" button stays disabled until the tech has
        both reviewed and printed the tracking sheet at least once (see
        on_shown(), which resets this if they navigate away and the
        underlying results change), and re-disables it for as long as a
        Sortly datacodes report kicked off by clicking "Complete" is still
        in flight (see _complete_with_sortly_report), so a second click
        can't fire a duplicate report."""
        return (
            self._tracking_reviewed
            and self._tracking_printed
            and not self._sortly_send_in_progress
        )

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("SpecCompleteV3: on_shown")
        state = self.state.get_value()

        # Results may have changed since the last visit (e.g. the tech went
        # back and redid a test), so any previously generated sheet is
        # stale -- reset to "Review" rather than risk printing outdated data.
        self._tracking_output_path = None
        self._tracking_ready_to_print = False
        self._tracking_reviewed = False
        self._tracking_printed = False
        self._tracking_print_requested = False
        self._tracking_initials = ""
        self._tracking_generated_date = None
        self.tracking_button.set_label("Review Tracking Sheet")
        self.tracking_button.remove_css_class("button-green")
        self.tracking_button.add_css_class("suggested-action")
        self.tracking_status.set_label("")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        self._clear_list(self.specinfo_list)
        self._clear_list(self.manualtest_list)
        self._clear_list(self.manualtest_list_2)
        self.manualtest_list_2.set_visible(False)

        all_complete = all(page.is_complete() for page in self.manual_test_pages)
        # A test marked "Has Issues" with no fully-filled-out reason (still)
        # counts as incomplete (see TogglePage.is_complete), so printing a
        # tracking sheet is blocked until every reported issue has its
        # specifics filled in, not just an overall pass/fail.
        self.tracking_button.set_sensitive(all_complete)
        if not all_complete:
            print("SpecCompleteV3: Incomplete")
            self.complete_row.set_title("Kramden Spec Complete: <b>INCOMPLETE</b>")
            self.tracking_status.set_label(
                "Complete all manual tests (with full details for any "
                "reported issues) before printing the tracking sheet."
            )
        else:
            print("SpecCompleteV3: Complete")
            self.complete_row.set_title("Kramden Spec Complete: <b>COMPLETE</b>")

        # System Info column
        if not state.get("SpecInfo", True) and self.specinfo:
            for reason in self.specinfo.get_failure_reasons():
                self.specinfo_list.append(self._failure_row(reason))
        else:
            self.specinfo_list.append(self._passed_row())

        # Manual Tests column — one page per test now, rather than one
        # combined ManualTest page. Pages with neither toggle selected yet
        # get a clickable orange row instead of being lumped in with failures.
        # Rows are collected first and only assigned to list boxes afterward,
        # since a widget can only ever belong to one container -- once we
        # know the total count we can decide whether to split into a second
        # column instead of letting a long list run off the bottom of the
        # screen.
        rows = []
        for page in self.manual_test_pages:
            if not page.is_complete():
                rows.append(self._incomplete_row(page))
                continue
            if not state.get(page.key, True):
                for reason in page.get_failure_reasons():
                    rows.append(self._failure_row(reason))
        if not rows:
            rows.append(self._passed_row())

        if len(rows) > MANUALTEST_ROWS_PER_COLUMN:
            split = (len(rows) + 1) // 2
            first_column, second_column = rows[:split], rows[split:]
        else:
            first_column, second_column = rows, []

        for row in first_column:
            self.manualtest_list.append(row)
        for row in second_column:
            self.manualtest_list_2.append(row)
        self.manualtest_list_2.set_visible(bool(second_column))

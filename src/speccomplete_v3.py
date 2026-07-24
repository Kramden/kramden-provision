import gi
import os
import re
import subprocess
import threading

gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib
from utils import Utils
from generate_tracking_sheet_v3 import generate_tracking_sheet, prefetch_tracking_sheet_data

# Once the Manual Tests failure/incomplete list exceeds this many rows, the
# remainder spills into a second column instead of growing the page past the
# screen.
MANUALTEST_ROWS_PER_COLUMN = 5

# The tracking sheet printer at every station is a Brother MFC-L2710DW
# series; used to pick its CUPS queue out of whatever else is configured.
TRACKING_SHEET_PRINTER_MODEL = "mfc-l2710dw"


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
        self._tracking_ready_to_print = False

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
        utils = Utils()
        utils.complete_reset("spec")

    def _on_tracking_clicked(self, button):
        if self._tracking_ready_to_print:
            self._print_tracking_sheet()
        else:
            self._generate_tracking_sheet()

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

        if self.specinfo is not None and not state.get("SpecInfo", True):
            for reason in self.specinfo.get_failure_reasons():
                notes_entries.append({"text": f"System Info: {reason}"})

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
            args=(knumber, spec_passed, manual_test_results, notes_entries),
            daemon=True,
        )
        thread.start()

    def _generate_thread(self, knumber, spec_passed, manual_test_results, notes_entries):
        try:
            output_path = generate_tracking_sheet(
                knumber,
                spec_passed=spec_passed,
                manual_test_results=manual_test_results,
                notes_entries=notes_entries,
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

        self._tracking_output_path = output_path
        self._tracking_ready_to_print = True
        self.tracking_button.set_label("Print Tracking Sheet")
        self.tracking_button.remove_css_class("suggested-action")
        self.tracking_button.add_css_class("button-green")

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

    def _resolve_printer_name(self):
        """Pick which CUPS destination to print to.

        The reliable path, when the printer is plugged in via USB, is to
        talk straight to the local loopback IPP service that Ubuntu's
        ipp-usb daemon already runs for it, via our own dedicated queue --
        bypassing cups-browsed's auto-discovered queues entirely, since
        those have repeatedly proven unreliable: an "implicitclass" queue
        hangs/fails whenever cups-browsed sees the same printer over more
        than one path (USB and network at once) and can't resolve a
        destination, and a "dnssd" (network) queue fails outright if the
        printer isn't actually reachable on the network at that moment
        (e.g. it's only really connected via USB right now, even though a
        stale mDNS record for it is still floating around).

        Falls back to matching an existing cups-browsed queue by name only
        if ipp-usb doesn't see a matching device at all (e.g. the printer
        really is network-only at this station).
        """
        port = self._find_ipp_usb_port()
        if port:
            queue = self._ensure_direct_usb_queue(port)
            if queue:
                return queue
        return self._resolve_browsed_printer_name()

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

        self.tracking_button.set_sensitive(False)
        self.tracking_status.set_label("Printing...")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

        thread = threading.Thread(
            target=self._print_thread, args=(output_path,), daemon=True
        )
        thread.start()

    def _print_thread(self, output_path):
        printer = self._resolve_printer_name()
        if not printer:
            GLib.idle_add(
                self._on_print_complete,
                "No Brother MFC-L2710DW printer found. Check the USB cable "
                "and that the printer is powered on.",
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
            GLib.idle_add(self._on_print_complete, None)
        except subprocess.CalledProcessError as e:
            GLib.idle_add(self._on_print_complete, e.stderr.strip() or str(e))
        except Exception as e:
            GLib.idle_add(self._on_print_complete, str(e))

    def _on_print_complete(self, error):
        self.tracking_button.set_sensitive(True)
        if error:
            self.tracking_status.set_label(f"Print failed: {error}")
            self.tracking_status.add_css_class("text-error")
            return

        self.tracking_status.set_label("Sent to printer.")
        if self.tracking_status.has_css_class("text-error"):
            self.tracking_status.remove_css_class("text-error")

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("SpecCompleteV3: on_shown")
        state = self.state.get_value()

        # Results may have changed since the last visit (e.g. the tech went
        # back and redid a test), so any previously generated sheet is
        # stale -- reset to "Review" rather than risk printing outdated data.
        self._tracking_output_path = None
        self._tracking_ready_to_print = False
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
        if not all_complete:
            print("SpecCompleteV3: Incomplete")
            self.complete_row.set_title("Kramden Spec Complete: <b>INCOMPLETE</b>")
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

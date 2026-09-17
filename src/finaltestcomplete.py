"""Last page of the Final Test wizard: reports overall pass/fail and, for
each manual test page, its result and any reported failure reasons --
same "green+check title row, plain-text failures listed underneath;
yellow+warning row instead if a page was left incomplete" display used by
Spec Complete (see speccomplete.SpecComplete)."""

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GLib
from utils import Utils


class FinalTestComplete(Adw.Bin):
    """Wizard page shown when Final Test is done; reports pass/fail."""

    def __init__(self):
        super().__init__()
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.title = "Final Test Complete"
        self.skip = False
        self.manual_test_pages = []
        self.on_navigate_to_page = None

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        page_header = Gtk.Label(label="Final Test Complete")
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

        manualtest_header = Gtk.Label(label="Manual Tests")
        manualtest_header.add_css_class("title-3")
        manualtest_header.set_halign(Gtk.Align.START)

        self.manualtest_list = Gtk.ListBox()
        self.manualtest_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.manualtest_list.add_css_class("boxed-list")
        self.manualtest_list.set_valign(Gtk.Align.START)

        manualtest_scroller = Gtk.ScrolledWindow()
        manualtest_scroller.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        manualtest_scroller.set_vexpand(True)
        manualtest_scroller.set_child(self.manualtest_list)

        vbox.append(page_header)
        vbox.append(complete_list)
        vbox.append(manualtest_header)
        vbox.append(manualtest_scroller)

        self.set_child(vbox)

    def _clear_list(self, list_box):
        while True:
            child = list_box.get_first_child()
            if child is None:
                break
            list_box.remove(child)

    def _title_row(self, title):
        """A manual test page that's filled out correctly -- green title
        text with a checkmark to the left, matching Spec Complete's color
        scheme (see speccomplete.SpecComplete._title_row)."""
        row = Adw.ActionRow()
        row.set_title(
            f"<span foreground='#3fe35a'><b>{GLib.markup_escape_text(title)}</b></span>"
        )
        row.set_icon_name("emblem-ok-symbolic")
        return row

    def _review_row(self, reason):
        """A reported failure reason on a page that's otherwise filled out
        correctly -- plain text, no color/icon, just for the tech to read
        over."""
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(reason))
        return row

    def _warning_row(self, title, target_page):
        """A manual test page left incomplete -- yellow text with a
        warning icon, clickable to jump straight to that page."""
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(title))
        row.set_icon_name("emblem-important-symbolic")
        row.add_css_class("text-warning")
        if target_page is not None:
            row.set_activatable(True)
            row.connect("activated", self._on_warning_row_activated, target_page)
        return row

    def _incomplete_row(self, page):
        return self._warning_row(f"{page.title}: not filled out", page)

    def _on_warning_row_activated(self, row, page):
        if self.on_navigate_to_page:
            self.on_navigate_to_page(page)

    def complete(self):
        print("FinatTestComplete: complete")
        utils = Utils()
        utils.complete_reset("finaltest")

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("FinalTestComplete: on_shown")
        state = self.state.get_value()

        manual_tests_complete = all(
            page.is_complete() for page in self.manual_test_pages
        )
        if not manual_tests_complete:
            print("FinalTestComplete: Incomplete")
            self.complete_row.set_title("Final Test Complete: <b>INCOMPLETE</b>")
        elif all(state.values()):
            print("FinalTestComplete: All passed")
            self.complete_row.set_title("Final Test Complete: <b>PASSED</b>!")
        else:
            print("FinalTestComplete: Failed")
            self.complete_row.set_title("Final Test Complete: <b>FAILED</b>!")

        # Manual Tests list -- one entry per test: green+check with its
        # reported failures (if any) listed underneath in plain text when
        # it's filled out correctly, or a single yellow+warning row linking
        # straight to the page when it isn't. See speccomplete.SpecComplete
        # for the matching Spec Complete display.
        self._clear_list(self.manualtest_list)
        for page in self.manual_test_pages:
            if not page.is_complete():
                self.manualtest_list.append(self._incomplete_row(page))
                continue
            self.manualtest_list.append(self._title_row(page.title))
            if not state.get(page.key, True):
                for reason in page.get_failure_summaries():
                    self.manualtest_list.append(self._review_row(reason))

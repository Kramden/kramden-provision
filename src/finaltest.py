#!/usr/bin/env python3
"""Final Test wizard entry point (kramden-provision-finaltest): steps a
tech through System Information, software checks, the manual hardware
tests, and Final Test Complete."""


import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gtk, Adw

import os
from sysinfo import SysInfo
from check_packages import CheckPackages
from manualtest import (
    PhysicalDefectsPage,
    WiFiPage,
    TouchpadPage,
    KeyboardPage,
    ScreenPage,
    TouchscreenPage,
    BrowserPage,
    WebcamPage,
    UsbAPage,
    UsbCPage,
)
from finaltestcomplete import FinalTestComplete
from observable import ObservableProperty, StateObserver
from utils import Utils


class WizardWindow(Gtk.ApplicationWindow):
    """Final Test main window: a Gtk.Stack of pages with Prev/Next navigation."""

    def __init__(self, app):
        super().__init__(application=app, title="Kramden - Final Test")

        self.set_icon_name("kramden")
        self.set_default_size(800, 800)
        display = Gdk.Display.get_default()
        if display:
            monitors = display.get_monitors()
            if monitors.get_n_items() > 0:
                self._apply_monitor_size(monitors.get_item(0))
            else:
                monitors.connect("items-changed", self._on_monitors_changed)

        # Initialize the observable property for tracking state. One entry
        # per page below (Touchscreen and USB-C only exist on capable
        # devices).
        initial_state = {
            "SysInfo": False,
            "CheckPackages": False,
            "PhysicalDefects": False,
            "WiFi": False,
            "Touchpad": False,
            "Keyboard": False,
            "ScreenTest": False,
            "Browser": False,
            "WebCam": False,
            "USBA": False,
        }
        has_touchscreen = Utils.has_touchscreen()
        if has_touchscreen:
            initial_state["Touchscreen"] = False
        show_usb_c_page = Utils.should_show_usb_c_page()
        if show_usb_c_page:
            initial_state["USBC"] = False
        self.observable_property = ObservableProperty(initial_state)
        # Create and add an observer
        observer = StateObserver()
        self.observable_property.add_observer(observer)

        # Create Gtk.HeaderBar
        header_bar = Gtk.HeaderBar()
        header_bar_title = Gtk.Label(label="Kramden - Final Test")
        header_bar.set_title_widget(header_bar_title)
        header_bar.set_show_title_buttons(True)

        # Navigation Buttons
        self.prev_button = Gtk.Button(label="Previous")
        self.prev_button.connect("clicked", self.on_prev_clicked)
        self.next_button = Gtk.Button(label="Next")
        self.next_button.connect("clicked", self.on_next_clicked)

        header_bar.pack_start(self.prev_button)
        header_bar.pack_end(self.next_button)

        self.set_titlebar(header_bar)

        # Create a page title widget
        self.title_widget = Gtk.Label(label="Final Test")

        # Create a header
        header = Adw.HeaderBar()
        header.set_decoration_layout("")  # Remove window controls
        header.set_title_widget(self.title_widget)

        # View Stack
        self.stack = Adw.ViewStack()

        sysinfo = SysInfo()
        check_packages = CheckPackages()
        physical_defects = PhysicalDefectsPage()
        wifi = WiFiPage()
        touchpad = TouchpadPage()
        keyboard = KeyboardPage()
        screen = ScreenPage()
        touchscreen_pages = [TouchscreenPage()] if has_touchscreen else []
        browser = BrowserPage()
        webcam = WebcamPage()
        usb_a = UsbAPage()
        usb_c_pages = [UsbCPage()] if show_usb_c_page else []
        physical_defects.usb_a_page = usb_a
        physical_defects.usb_c_page = usb_c_pages[0] if usb_c_pages else None
        physical_defects.keyboard_page = keyboard
        physical_defects.screen_page = screen

        # Desktops/All-In-Ones have no built-in touchpad or keyboard, and
        # plain desktop towers (unlike All-In-Ones) have no built-in screen
        # either -- skip those pages rather than asking a tech to test
        # hardware the chassis doesn't have. Defaults to laptop behavior
        # (skip nothing) when the chassis type can't be detected.
        chassis_type = Utils.get_chassis_type()
        if chassis_type in ("Desktop", "All-In-One"):
            touchpad.mark_not_applicable()
            keyboard.mark_not_applicable()
        if chassis_type == "Desktop":
            screen.mark_not_applicable()

        complete = FinalTestComplete()

        manual_test_pages = (
            [physical_defects, wifi, touchpad, keyboard, screen]
            + touchscreen_pages
            + [browser, webcam, usb_a]
            + usb_c_pages
        )
        self.pages = [sysinfo, check_packages] + manual_test_pages + [complete]

        sysinfo.state = self.observable_property
        sysinfo.on_loading_changed = self._on_sysinfo_loading_changed
        self._sysinfo_loading = False
        check_packages.state = self.observable_property

        for page in manual_test_pages:
            page.state = self.observable_property
            page.on_status_changed = self.update_buttons

        complete.manual_test_pages = manual_test_pages
        complete.state = self.observable_property

        self.manual_test_pages = manual_test_pages

        for index, page in enumerate(self.pages):
            self.stack.add_named(page, f"page{index + 1}")

        self.stack.set_vexpand(True)  # Ensure the stack expands vertically

        # Content Box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(header)
        content_box.append(self.stack)

        self.set_child(content_box)
        self.current_page = 0
        self.update_buttons(focus_next=True)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(
            os.path.dirname(os.path.realpath(__file__)) + "/css/style.css"
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Set title_widget after page was set
        self.stack.connect("notify::visible-child", self.on_visible_page_changed)
        self.title_widget.set_label(self.stack.get_visible_child().title)

        # Fake visible change to set state info
        self.pages[0].on_shown()

    def _apply_monitor_size(self, monitor):
        geo = monitor.get_geometry()
        self.set_default_size(
            min(800, int(geo.width * 0.8)),
            min(800, int(geo.height * 0.8)),
        )

    def _on_monitors_changed(self, monitors, position, removed, added):
        if monitors.get_n_items() > 0:
            self._apply_monitor_size(monitors.get_item(0))

    def on_visible_page_changed(self, stack, params):
        print("on_visible_page_changed")
        current = stack.get_visible_child()
        self.title_widget.set_label(current.title)
        current.on_shown()

    def on_prev_clicked(self, button=None):
        if self.current_page > 0:
            self.current_page -= 1
            self.stack.set_visible_child_name(f"page{self.current_page + 1}")
            self.update_buttons(focus_next=True)
            page = self.pages[self.current_page]
            if page.skip:
                print(f"on_prev_clicked: page{self.current_page + 1} skipped")
                self.on_prev_clicked()

    def on_next_clicked(self, button=None):
        current = self.pages[self.current_page]
        if hasattr(current, "is_complete") and not current.is_complete():
            self._show_incomplete_warning()
            return

        last_index = len(self.pages) - 1
        if self.current_page < last_index:
            self.current_page += 1
            self.stack.set_visible_child_name(f"page{self.current_page + 1}")
            self.update_buttons(focus_next=True)
            page = self.pages[self.current_page]
            if page.skip:
                print(f"on_next_clicked: page{self.current_page + 1} skipped")
                self.on_next_clicked()
        else:
            self.complete()

    def _show_incomplete_warning(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="You must fill out all of the necessary information before "
            "moving to the next page!",
        )
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()

    def update_buttons(self, focus_next=False):
        last_index = len(self.pages) - 1
        self.prev_button.set_sensitive(self.current_page > 0)
        self.next_button.set_sensitive(self.current_page <= last_index)
        current = self.pages[self.current_page]
        if self.current_page == last_index:
            self.next_button.set_label("Complete")
            self.next_button.add_css_class("button-next-last-page")
            self.next_button.remove_css_class("suggested-action")
            state = self.observable_property.get_value()
            self.next_button.set_sensitive(all(state.values()))
        else:
            self.next_button.remove_css_class("button-next-last-page")
            self.next_button.set_label("Next")
            # Light the button up once the current page has everything it
            # needs to move on -- pages without is_complete (SysInfo,
            # CheckPackages) are left alone.
            if hasattr(current, "is_complete") and current.is_complete():
                self.next_button.add_css_class("suggested-action")
            else:
                self.next_button.remove_css_class("suggested-action")

        # While SysInfo is gathering, lock Next/Prev so rapid clicks
        # don't queue and fire after the page finishes loading.
        if self._sysinfo_loading:
            self.next_button.set_sensitive(False)
            self.prev_button.set_sensitive(False)

        # Focus the next button -- only when we just navigated to a page, not
        # on every status update (that would steal focus out from under
        # whatever entry field the tech is typing in).
        if focus_next:
            self.next_button.grab_focus()

    def _on_sysinfo_loading_changed(self, loading):
        self._sysinfo_loading = loading
        self.update_buttons()

    def complete(self):
        print("Complete Clicked")
        current = self.stack.get_visible_child()
        if hasattr(current, "complete"):
            current.complete()


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.kramden.provision-finaltest")
        Adw.init()

        # Set Adwaita dark theme preference using Adw.StyleManager
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        window = WizardWindow(self)
        self.add_window(window)
        window.present()


app = Application()
app.run([])

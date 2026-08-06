#!/usr/bin/env python3

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gtk, Adw

import os
from sortly_register import SortlyRegister
from specinfo import SpecInfo
from manualtest_v3 import (
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
from speccomplete_v3 import SpecCompleteV3
from observable import ObservableProperty, StateObserver
from utils import Utils


class WizardWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Kramden - Spec (v3)")

        self.set_icon_name("kramden")
        self.set_default_size(1000, 900)
        self._monitors_model = None
        self._monitor_signal_handler = None
        display = Gdk.Display.get_default()
        if display:
            self._monitors_model = display.get_monitors()
            if self._monitors_model is not None:
                self._monitor_signal_handler = self._monitors_model.connect(
                    "items-changed", self._on_monitors_changed
                )
                if self._monitors_model.get_n_items() > 0:
                    self._apply_monitor_size(self._monitors_model.get_item(0))
        self.connect("close-request", self._on_close_request)

        # Initialize the observable property for tracking state. One entry
        # per page below (Touchscreen and USB-C only exist on capable
        # devices).
        initial_state = {
            "SpecInfo": False,
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
        header_bar_title = Gtk.Label(label="Kramden - Spec")
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
        self.title_widget = Gtk.Label(label="Spec")

        # Create a header
        header = Adw.HeaderBar()
        header.set_decoration_layout("")  # Remove window controls
        header.set_title_widget(self.title_widget)

        # View Stack
        self.stack = Adw.ViewStack()

        sortly_register = SortlyRegister()
        specinfo = SpecInfo()
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
        complete = SpecCompleteV3()

        manual_test_pages = (
            [physical_defects, wifi, touchpad, keyboard, screen]
            + touchscreen_pages
            + [browser, webcam, usb_a]
            + usb_c_pages
        )
        self.pages = [sortly_register, specinfo] + manual_test_pages + [complete]

        sortly_register.next = self.on_next_clicked
        sortly_register.state = self.observable_property
        specinfo.sortly_register = sortly_register
        specinfo.state = self.observable_property
        specinfo.on_loading_changed = self._on_specinfo_loading_changed
        self._specinfo_loading = False
        self.specinfo_page = specinfo

        for page in manual_test_pages:
            page.state = self.observable_property
            page.on_status_changed = self.update_buttons

        complete.sortly_register = sortly_register
        complete.specinfo = specinfo
        complete.manual_test_pages = manual_test_pages
        complete.state = self.observable_property
        complete.on_navigate_to_page = self._navigate_to_page
        complete.on_status_changed = self.update_buttons

        self.manual_test_pages = manual_test_pages

        for index, page in enumerate(self.pages):
            self.stack.add_named(page, f"page{index + 1}")

        self.stack.set_vhomogeneous(False)

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
            min(1000, int(geo.width * 0.8)),
            min(900, int(geo.height * 0.8)),
        )

    def _on_monitors_changed(self, monitors, position, removed, added):
        if monitors.get_n_items() > 0:
            self._apply_monitor_size(monitors.get_item(0))

    def _on_close_request(self, window):
        self._cleanup_monitor_signal()
        return False

    def _cleanup_monitor_signal(self):
        if self._monitors_model is None:
            return
        if self._monitor_signal_handler is not None:
            self._monitors_model.disconnect(self._monitor_signal_handler)
        self._monitor_signal_handler = None
        self._monitors_model = None

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
        # Warn if leaving the Sortly page without submitting hardware info
        if self.current_page == 0 and not self.pages[0]._submitted:
            self._show_sortly_warning()
            return

        current = self.pages[self.current_page]
        if hasattr(current, "is_complete") and not current.is_complete():
            if current is self.specinfo_page:
                self._show_specinfo_blocked_warning()
            else:
                self._show_incomplete_warning()
            return

        self._advance_next()

    def _show_sortly_warning(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Hardware info not submitted",
            secondary_text="You have not submitted the updated hardware info to Sortly. Are you sure you want to continue?",
        )
        dialog.connect("response", self._on_sortly_warning_response)
        dialog.present()

    def _on_sortly_warning_response(self, dialog, response):
        dialog.close()
        if response == Gtk.ResponseType.OK:
            self._advance_next()

    def _show_specinfo_blocked_warning(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="There is either asset info on this device or a drive in "
            "this device. You can not spec this device. Please find a "
            "Super Geek or Staff member and hand the machine to them.",
        )
        dialog.add_button("Power Off", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self._on_specinfo_blocked_response)
        dialog.present()

    def _on_specinfo_blocked_response(self, dialog, response):
        dialog.close()
        if response == Gtk.ResponseType.ACCEPT:
            Utils.power_off()

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

    def _advance_next(self):
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

    def update_buttons(self, focus_next=False):
        last_index = len(self.pages) - 1
        self.prev_button.set_sensitive(self.current_page > 0)
        self.next_button.set_sensitive(self.current_page <= last_index)
        current = self.pages[self.current_page]
        if self.current_page == last_index:
            self.next_button.set_label("Complete")
            self.next_button.add_css_class("button-next-last-page")
            self.next_button.remove_css_class("suggested-action")
            all_complete = (
                all(page.is_complete() for page in self.manual_test_pages)
                and self.pages[last_index].is_complete()
            )
            self.next_button.set_sensitive(all_complete)
        else:
            self.next_button.remove_css_class("button-next-last-page")
            self.next_button.set_label("Next")
            # Light the button up once the current page has everything it
            # needs to move on (see TogglePage/PhysicalDefectsPage.is_complete)
            # -- pages without is_complete (Sortly, SpecInfo) are left alone.
            if hasattr(current, "is_complete") and current.is_complete():
                self.next_button.add_css_class("suggested-action")
            else:
                self.next_button.remove_css_class("suggested-action")

        # While SpecInfo is gathering data, lock Next so rapid clicks
        # don't queue and fire after the page finishes loading.
        if self._specinfo_loading:
            self.next_button.set_sensitive(False)
            self.prev_button.set_sensitive(False)

        # Focus the next button -- only when we just navigated to a page, not
        # on every status update (that would steal focus out from under
        # whatever entry field the tech is typing in, e.g. Broken Part's
        # "Some other broken part" text box).
        if focus_next:
            self.next_button.grab_focus()

    def _on_specinfo_loading_changed(self, loading):
        self._specinfo_loading = loading
        self.update_buttons()

    def _navigate_to_page(self, page):
        try:
            index = self.pages.index(page)
        except ValueError:
            return
        self.current_page = index
        self.stack.set_visible_child_name(f"page{index + 1}")
        self.update_buttons(focus_next=True)

    def complete(self):
        print("Complete Clicked")
        current = self.stack.get_visible_child()
        if hasattr(current, "complete"):
            current.complete()


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.kramden.spec.v3")
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

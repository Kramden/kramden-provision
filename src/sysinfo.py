import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk
from loading_capture import StdoutCapture
from utils import Utils


class SysInfo(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "System Information"
        self.skip = False
        self.batteries_populated = False
        self.disks_populated = False

        # Loading state: data is gathered once in a background thread on
        # first show. Until ready, the nested loading view (spinner +
        # stdout) covers the content. on_loading_changed(loading: bool)
        # lets the wizard disable Next/Prev while we work.
        self._data_ready = False
        self._gather_in_progress = False
        self._gathered = {}
        self._stdout_capture = None
        self.on_loading_changed = None

        utils = Utils()

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create scrollable window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        self.hostname_row = Adw.ActionRow()
        self.hostname_row.set_title("K-Number")

        self.landscape_row = Adw.ActionRow()
        self.landscape_row.set_title("Landscape Status")

        vendor_row = Adw.ActionRow()
        vendor_row.set_title("Manufacturer")
        vendor_row.set_subtitle(utils.get_vendor())
        vendor_row.set_icon_name("emblem-ok-symbolic")

        model_row = Adw.ActionRow()
        model_row.set_title("Model")
        model_row.set_subtitle(utils.get_model())
        model_row.set_icon_name("emblem-ok-symbolic")

        os_row = Adw.ActionRow()
        os_row.set_title("OS")
        os_row.set_subtitle(utils.get_os())
        if "Ubuntu" in os_row.get_subtitle():
            os_row.set_icon_name("emblem-ok-symbolic")
        else:
            os_row.set_icon_name("emblem-important-symbolic")

        cpu_row = Adw.ActionRow()
        cpu_row.set_title("CPU")
        cpu_row.set_subtitle(utils.get_cpu_info())
        cpu_row.set_icon_name("emblem-ok-symbolic")

        self.mem_row = Adw.ActionRow()
        self.mem_row.set_title("Memory")
        self.mem_row.set_subtitle(utils.get_mem() + " GB")

        self.disks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.battery_row = Adw.ExpanderRow(title="Batteries")
        self.battery_row.set_visible(False)
        self.battery_row.set_expanded(True)

        # Add rows to the list box
        list_box.append(self.hostname_row)
        list_box.append(self.landscape_row)
        list_box.append(vendor_row)
        list_box.append(model_row)
        list_box.append(cpu_row)
        list_box.append(os_row)
        list_box.append(self.mem_row)
        list_box.append(self.disks_box)
        list_box.append(self.battery_row)

        # Nested loading view: spinner + live stdout TextView. Visible
        # while gather() runs in a background thread; hidden once data
        # is ready and the rows below are populated.
        self._loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        loading_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._loading_spinner = Gtk.Spinner()
        self._loading_spinner.set_size_request(24, 24)
        loading_label = Gtk.Label(label="Gathering system information...")
        loading_label.add_css_class("title-3")
        loading_label.set_halign(Gtk.Align.START)
        loading_header.append(self._loading_spinner)
        loading_header.append(loading_label)
        self._loading_box.append(loading_header)

        self._loading_buffer = Gtk.TextBuffer()
        self._loading_textview = Gtk.TextView(buffer=self._loading_buffer)
        self._loading_textview.set_editable(False)
        self._loading_textview.set_cursor_visible(False)
        self._loading_textview.set_monospace(True)
        self._loading_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        loading_scroll = Gtk.ScrolledWindow()
        loading_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        loading_scroll.set_min_content_height(320)
        loading_scroll.set_vexpand(True)
        loading_scroll.set_child(self._loading_textview)
        self._loading_box.append(loading_scroll)
        self._loading_box.set_visible(False)

        self._list_box = list_box

        vbox.append(self._loading_box)
        vbox.append(list_box)
        scrolled_window.set_child(vbox)
        self.set_child(scrolled_window)

    def on_shown(self):
        if self._gather_in_progress:
            return
        if not self._data_ready:
            self._start_gather()
            return
        self._render()

    def _start_gather(self):
        self._gather_in_progress = True
        self._list_box.set_visible(False)
        self._loading_box.set_visible(True)
        self._loading_spinner.start()
        self._loading_buffer.set_text("")
        if self.on_loading_changed:
            self.on_loading_changed(True)

        self._stdout_capture = StdoutCapture(self._on_stdout_line)
        self._stdout_capture.start()

        threading.Thread(target=self._gather_thread, daemon=True).start()

    def _gather_thread(self):
        try:
            self.gather()
        except Exception as exc:
            print(f"Error gathering system info: {exc}")
        finally:
            GLib.idle_add(self._on_gather_complete)

    def gather(self):
        """Heavy data collection. Runs on a background thread. Stores
        results in self._gathered. Uses print() narration so the user
        sees progress in the loading TextView.
        """
        utils = Utils()
        print("Reading hostname...")
        hostname = utils.get_hostname()
        print(f"  hostname: {hostname}")
        print("Checking Landscape registration...")
        registered = utils.is_registered()
        print(f"  registered: {registered}")
        print("Reading memory size...")
        mem = utils.get_mem()
        print("Enumerating disks...")
        disks = utils.get_disks()
        print(f"  Found {len(disks)} disk(s)")
        print("Reading battery capacities...")
        batteries = utils.get_battery_capacities()
        print(f"  Found {len(batteries)} batter(y/ies)")
        print("System information gathering complete.")

        self._gathered = {
            "hostname": hostname,
            "registered": registered,
            "mem": mem,
            "disks": disks,
            "batteries": batteries,
        }

    def _on_stdout_line(self, line):
        GLib.idle_add(self._append_stdout, line)

    def _append_stdout(self, line):
        end = self._loading_buffer.get_end_iter()
        self._loading_buffer.insert(end, line)
        mark = self._loading_buffer.get_insert()
        self._loading_textview.scroll_to_mark(mark, 0.0, False, 0.0, 0.0)
        return False

    def _on_gather_complete(self):
        if self._stdout_capture is not None:
            self._stdout_capture.stop()
            self._stdout_capture = None
        self._gather_in_progress = False
        self._data_ready = True
        self._loading_spinner.stop()
        self._loading_box.set_visible(False)
        self._list_box.set_visible(True)
        try:
            self._render()
        except Exception as exc:
            print(f"SysInfo._render failed: {exc}")
        finally:
            if self.on_loading_changed:
                self.on_loading_changed(False)
        return False

    def _render(self):
        passed = True
        self.hostname_row.set_subtitle(self._gathered["hostname"])
        if self.hostname_row.get_subtitle().lower().startswith("k"):
            self.hostname_row.set_icon_name("emblem-ok-symbolic")
            if self.hostname_row.has_css_class("text-error"):
                self.hostname_row.remove_css_class("text-error")
        else:
            self.hostname_row.set_icon_name("emblem-important-symbolic")
            self.hostname_row.add_css_class("text-error")
            passed = False

        # Landscape registration status
        if self._gathered["registered"]:
            self.landscape_row.set_subtitle("Registered")
            self.landscape_row.set_icon_name("emblem-ok-symbolic")
            if self.landscape_row.has_css_class("text-error"):
                self.landscape_row.remove_css_class("text-error")
        else:
            self.landscape_row.set_subtitle("Not registered")
            self.landscape_row.set_icon_name("emblem-important-symbolic")
            self.landscape_row.add_css_class("text-error")
            passed = False

        # Set Memory row to emblem-ok-symbolic if memory is greater than or equal to 7 GB, else set row to emblem-important-symbolic
        mem = int(self._gathered["mem"])
        if mem >= 7:
            self.mem_row.set_icon_name("emblem-ok-symbolic")
            if self.mem_row.has_css_class("text-error"):
                self.mem_row.remove_css_class("text-error")
        else:
            self.mem_row.set_icon_name("emblem-important-symbolic")
            self.mem_row.add_css_class("text-error")

        # Populate disk information
        if not self.disks_populated:
            disks = self._gathered["disks"]
            if len(disks.keys()) > 1:
                disks_row = Adw.ExpanderRow(title="Disks")
                disks_row.set_visible(True)
                disks_row.set_expanded(True)
                for disk in disks.keys():
                    row = Adw.ActionRow()
                    row.set_title(f"{str(disk)})")
                    disk_info = disks[disk]
                    row.set_subtitle(f"{disk_info['type']}: {disk_info['size']} GB")
                    disks_row.add_row(row)
                    disks_row.set_expanded(True)
                    disks_row.set_visible(True)
                    disks_row.set_icon_name("emblem-important-symbolic")
                    disks_row.add_css_class("text-error")
                self.disks_box.append(disks_row)
            else:
                disk = list(disks.items())
                disk_row = Adw.ExpanderRow(title="Disk")
                disk_row.set_visible(True)
                disk_row.set_expanded(True)
                row = Adw.ActionRow()
                row.set_title(f"{str(disk[0][0])}")
                disk_info = disk[0][1]
                row.set_subtitle(f"{disk_info['type']}: {disk_info['size']} GB")
                if disk_info['size'] >= 100:
                    row.set_icon_name("emblem-ok-symbolic")
                    if row.has_css_class("text-error"):
                        row.remove_css_class("text-error")
                else:
                    row.set_icon_name("emblem-important-symbolic")
                    row.add_css_class("text-error")
                disk_row.add_row(row)
                self.disks_box.append(disk_row)
            self.disks_populated = True

        # Populate battery information
        if not self.batteries_populated:
            batteries = self._gathered["batteries"]
            if len(batteries) == 1:
                self.battery_row.set_title("Battery")
            for battery in batteries.keys():
                row = Adw.ActionRow()
                row.set_title(str(battery))
                row.set_subtitle(f"Capacity: {str(batteries[battery])}%")
                self.battery_row.add_row(row)
                self.battery_row.set_expanded(True)
                if int(batteries[battery]) >= 70:
                    row.set_icon_name("emblem-ok-symbolic")
                else:
                    row.set_icon_name("emblem-important-symbolic")
                self.battery_row.set_visible(True)
            self.batteries_populated = True

        state = self.state.get_value()
        state["SysInfo"] = passed
        print("sysinfo:_render " + str(self.state.get_value()))

#!/usr/bin/env python3

import concurrent.futures
import gi
import os
import re
import subprocess
import sys
import threading
import time

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gtk, Adw, GLib

TEST_MODE = "--test" in sys.argv


def detect_drives():
    """Detect non-removable SATA and NVMe drives using lsblk."""
    drives = []

    # SATA drives
    try:
        result = subprocess.run(
            ["lsblk", "-n", "-d", "--output", "PATH,TYPE,RM"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "disk" and parts[2] == "0":
                path = parts[0]
                if "nvme" not in path:
                    size = _get_drive_size(path)
                    drives.append({"path": path, "type": "SATA", "size": size})
    except (subprocess.CalledProcessError, OSError):
        pass

    # NVMe drives
    try:
        result = subprocess.run(
            ["lsblk", "-n", "--nvme", "-d", "--output", "PATH,TYPE,RM"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "disk" and parts[2] == "0":
                path = parts[0]
                size = _get_drive_size(path)
                drives.append({"path": path, "type": "NVMe", "size": size})
    except (subprocess.CalledProcessError, OSError):
        pass

    return drives


def _get_drive_size(path):
    """Get drive size in human-readable format."""
    try:
        result = subprocess.run(
            ["lsblk", "-n", "-d", "-b", "--output", "SIZE", path],
            capture_output=True,
            text=True,
        )
        size_bytes = int(result.stdout.strip())
        size_gb = round(size_bytes / (1024**3), 1)
        return f"{size_gb} GB"
    except (subprocess.CalledProcessError, OSError, ValueError):
        return "Unknown"


def erase_drive(drive, test_mode):
    """Erase a single drive. Returns (success, short_message, detail)."""
    path = drive["path"]
    drive_type = drive["type"]

    if test_mode:
        time.sleep(2)
        return True, f"[TEST] Would erase {drive_type} drive {path}", None

    try:
        if drive_type == "SATA":
            return _erase_sata(path)
        else:  # NVMe
            result = subprocess.run(
                ["sudo", "nvme", "format", "--force", path],
                capture_output=True,
                text=True,
            )

        if result.returncode == 0:
            return True, f"Successfully erased {path}", None
        else:
            detail = ""
            if result.stdout.strip():
                detail += result.stdout.strip()
            if result.stderr.strip():
                if detail:
                    detail += "\n"
                detail += result.stderr.strip()
            return False, f"Failed to erase {path}", detail or None
    except OSError as e:
        return False, f"Failed to erase {path}", str(e)


def _erase_sata(path):
    """Erase a SATA drive, falling back to ATA Security Erase if SANITIZE is not supported."""
    # Try SANITIZE block erase first (preferred, faster)
    result = subprocess.run(
        [
            "sudo",
            "hdparm",
            "--yes-i-know-what-i-am-doing",
            "--sanitize-block-erase",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, f"Successfully erased {path}", None

    # SANITIZE not supported, fall back to ATA Security Erase
    # Check if drive is frozen (security commands will fail on frozen drives)
    info_result = subprocess.run(
        ["sudo", "hdparm", "-I", path],
        capture_output=True,
        text=True,
    )
    if not re.search(r"not\s+frozen", info_result.stdout):
        return (
            False,
            f"Failed to erase {path}",
            "Drive is frozen. Try suspending and resuming the system first.",
        )

    # Set a temporary password (required before security erase)
    result = subprocess.run(
        ["sudo", "hdparm", "--security-set-pass", "p", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        return (
            False,
            f"Failed to erase {path}",
            f"Could not set security password:\n{detail}" if detail else None,
        )

    # Issue ATA Security Erase
    result = subprocess.run(
        ["sudo", "hdparm", "--security-erase", "p", path],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, f"Successfully erased {path}", None

    # Erase failed — try to clear the password so the drive isn't left locked
    subprocess.run(
        ["sudo", "hdparm", "--security-disable", "p", path],
        capture_output=True,
        text=True,
    )
    detail = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    return (
        False,
        f"Failed to erase {path}",
        f"ATA Security Erase failed:\n{detail}" if detail else None,
    )


class DriveRow(Adw.ActionRow):
    """A row representing a single drive with a checkbox."""

    def __init__(self, drive):
        super().__init__()
        self.drive = drive
        self._default_subtitle = f"{drive['type']}  —  {drive['size']}"
        self.set_title(drive["path"])
        self.set_subtitle(self._default_subtitle)
        self.succeeded = False
        self.error_detail = None

        self.check = Gtk.CheckButton()
        self.check.set_active(True)
        self.add_prefix(self.check)

        self.status_icon = Gtk.Image()
        self.status_icon.set_visible(False)
        self.add_suffix(self.status_icon)

        self.detail_button = Gtk.Button(icon_name="dialog-information-symbolic")
        self.detail_button.add_css_class("flat")
        self.detail_button.set_visible(False)
        self.detail_button.set_valign(Gtk.Align.CENTER)
        self.detail_button.set_tooltip_text("View error details")
        self.detail_button.connect("clicked", self._on_detail_clicked)
        self.add_suffix(self.detail_button)

        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        self.add_suffix(self.spinner)

    def _clear_status_classes(self):
        self.status_icon.remove_css_class("success-icon")
        self.status_icon.remove_css_class("error-icon")

    def reset(self):
        """Reset row to pre-erase state for retry."""
        self.spinner.stop()
        self.spinner.set_visible(False)
        self._clear_status_classes()
        self.status_icon.set_visible(False)
        self.detail_button.set_visible(False)
        self.set_subtitle(self._default_subtitle)
        self.succeeded = False
        self.error_detail = None

    def set_in_progress(self):
        self.spinner.set_visible(True)
        self.spinner.start()
        self._clear_status_classes()
        self.status_icon.set_visible(False)
        self.detail_button.set_visible(False)
        self.check.set_sensitive(False)

    def set_success(self, message):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self._clear_status_classes()
        self.status_icon.set_from_icon_name("emblem-ok-symbolic")
        self.status_icon.add_css_class("success-icon")
        self.status_icon.set_visible(True)
        self.set_subtitle(message)
        self.succeeded = True

    def set_failure(self, short_message, detail):
        self.spinner.stop()
        self.spinner.set_visible(False)
        self._clear_status_classes()
        self.status_icon.set_from_icon_name("dialog-error-symbolic")
        self.status_icon.add_css_class("error-icon")
        self.status_icon.set_visible(True)
        self.set_subtitle(short_message)
        self.error_detail = detail
        if detail:
            self.detail_button.set_visible(True)
        self.succeeded = False

    def _on_detail_clicked(self, button):
        window = self.get_root()
        dialog = Adw.MessageDialog(
            transient_for=window,
            heading=f"Error erasing {self.drive['path']}",
            body=self.error_detail or "No details available.",
        )
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.present()


class SecureEraseWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Kramden - Secure Erase")
        self.set_icon_name("kramden")
        self.set_default_size(800, 600)
        self.erasing = False

        # Header bar
        header_bar = Gtk.HeaderBar()
        title_text = "Kramden - Secure Erase"
        if TEST_MODE:
            title_text += "  [TEST MODE]"
        header_bar_title = Gtk.Label(label=title_text)
        header_bar.set_title_widget(header_bar_title)
        header_bar.set_show_title_buttons(True)
        self.set_titlebar(header_bar)

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

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Warning banner
        self.banner = Adw.Banner()
        if TEST_MODE:
            self.banner.set_title(
                "[TEST MODE] No data will actually be erased"
            )
            self.banner.add_css_class("test-mode-banner")
        else:
            self.banner.set_title(
                "WARNING: ALL DATA WILL BE PERMANENTLY DESTROYED"
            )
            self.banner.add_css_class("destructive-banner")
        self.banner.set_revealed(True)
        main_box.append(self.banner)

        # Scrollable content area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # Drive list
        drives_label = Gtk.Label(label="Detected Drives")
        drives_label.add_css_class("title-2")
        drives_label.set_xalign(0)
        content_box.append(drives_label)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        content_box.append(self.list_box)

        # Status label (shown after erase completes)
        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)
        self.status_label.set_visible(False)
        content_box.append(self.status_label)

        scrolled.set_child(content_box)
        main_box.append(scrolled)

        # Bottom button bar
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_margin_top(12)
        button_box.set_margin_bottom(12)
        button_box.set_margin_start(20)
        button_box.set_margin_end(20)
        button_box.set_halign(Gtk.Align.END)

        self.erase_button = Gtk.Button(label="Erase Selected Drives")
        self.erase_button.add_css_class("destructive-action")
        self.erase_button.connect("clicked", self._on_erase_clicked)
        button_box.append(self.erase_button)

        main_box.append(button_box)
        self.set_child(main_box)

        # Detect drives
        self.drive_rows = []
        drives = detect_drives()
        if drives:
            for drive in drives:
                row = DriveRow(drive)
                self.drive_rows.append(row)
                self.list_box.append(row)
        else:
            no_drives_row = Adw.ActionRow()
            no_drives_row.set_title("No drives detected")
            self.list_box.append(no_drives_row)
            self.erase_button.set_sensitive(False)

    def _on_erase_clicked(self, button):
        selected = [r for r in self.drive_rows if r.check.get_active()]
        if not selected:
            return

        # Show confirmation dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Confirm Secure Erase",
            body=(
                f"You are about to permanently erase {len(selected)} "
                f"drive{'s' if len(selected) != 1 else ''}.\n\n"
                "This action CANNOT be undone.\n\n"
                'Type "ERASE" below to confirm.'
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("erase", "Erase")
        dialog.set_response_appearance("erase", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        # Add text entry for confirmation
        entry = Gtk.Entry()
        entry.set_placeholder_text('Type "ERASE" to confirm')
        entry.set_halign(Gtk.Align.CENTER)
        dialog.set_extra_child(entry)

        # Disable the erase button until "ERASE" is typed
        dialog.set_response_enabled("erase", False)
        entry.connect(
            "changed",
            lambda e: dialog.set_response_enabled(
                "erase", e.get_text().strip() == "ERASE"
            ),
        )

        dialog.connect("response", self._on_confirm_response, selected)
        dialog.present()

    def _on_confirm_response(self, dialog, response, selected_rows):
        if response != "erase":
            return

        self.erasing = True
        self.erase_button.set_sensitive(False)
        # Reset selected rows and disable all checkboxes during erase
        for row in selected_rows:
            row.reset()
        for row in self.drive_rows:
            row.check.set_sensitive(False)
        # Clear stale status label
        self.status_label.set_visible(False)
        self.status_label.remove_css_class("success-text")
        self.status_label.remove_css_class("text-error")

        thread = threading.Thread(
            target=self._erase_thread,
            args=(selected_rows,),
            daemon=True,
        )
        thread.start()

    def _erase_drive_worker(self, row):
        """Erase a single drive and update its row. Returns success bool."""
        GLib.idle_add(row.set_in_progress)
        success, short_message, detail = erase_drive(row.drive, TEST_MODE)
        if success:
            GLib.idle_add(row.set_success, short_message)
        else:
            GLib.idle_add(row.set_failure, short_message, detail)
        return success

    def _erase_thread(self, selected_rows):
        results = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(selected_rows)
        ) as executor:
            futures = {
                executor.submit(self._erase_drive_worker, row): row
                for row in selected_rows
            }
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        GLib.idle_add(self._erase_complete, results)

    def _erase_complete(self, results):
        self.erasing = False
        total = len(results)
        succeeded = sum(1 for s in results if s)
        failed = total - succeeded

        # Clear stale classes before applying
        self.status_label.remove_css_class("success-text")
        self.status_label.remove_css_class("text-error")

        if failed == 0:
            self.status_label.set_text(
                f"All {total} drive{'s' if total != 1 else ''} erased successfully."
            )
            self.status_label.add_css_class("success-text")
        else:
            self.status_label.set_text(
                f"{succeeded} of {total} drives erased. {failed} failed."
            )
            self.status_label.add_css_class("text-error")

        self.status_label.set_visible(True)

        # Re-enable erase button and checkboxes on failed rows for retry
        self.erase_button.set_sensitive(True)
        for row in self.drive_rows:
            if row.succeeded:
                row.check.set_active(False)
                row.check.set_sensitive(False)
            else:
                row.check.set_active(True)
                row.check.set_sensitive(True)

        return False


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.kramden.provision-secureerase")
        Adw.init()
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        window = SecureEraseWindow(self)
        self.add_window(window)
        window.present()


app = Application()
app.run([])

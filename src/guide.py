import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
gi.require_version('WebKit', '6.0')
from gi.repository import Adw, Gtk, WebKit
from utils import Utils
import os

class KramdenGuide(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Kramden Guide"
        utils = Utils()
        os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"]="1"

        # Create scrollable window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Create a WebView widget
        self.webview = WebKit.WebView()
        settings = self.webview.get_settings()
        settings.set_enable_media(False)
        settings.set_enable_javascript(True)

        # Load the PDF file
        pdf = "Kramden_Computer_Info.pdf"
        pdf_dir = "/usr/share/kramden-provision/documents/"
        #pdf_path = os.path.join(pdf_dir, pdf)
        if (utils.file_exists_and_readable(os.path.join(pdf_dir, pdf))):
            pdf_path = os.path.join(pdf_dir, pdf)
        else:
            pdf_path = os.path.join(os.getcwd(), pdf)
        self.webview.load_uri("file://" + pdf_path)
 
        scrolled_window.set_child(self.webview)
        self.set_child(scrolled_window)

    def disable_controls(self):
        disable_script = """
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
        """
        self.webview.evaluate_javascript(disable_script, 3, None, None, None)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("KramdenGuide: on_shown")
        self.disable_controls()

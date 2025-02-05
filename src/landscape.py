import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

class Landscape(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Landscape Registration"
        
        label = Gtk.Label(label="Landscape Registration")
        self.set_child(label)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
       state = self.state.get_value()
       state['Landscape'] = True
       self.state.set_value(state)

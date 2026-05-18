import os
import sys
import threading


class StdoutCapture:
    """Redirect fd 1 (and sys.stdout) to a pipe; deliver lines to a callback.

    Captures both Python prints and subprocess stdout that inherits fd 1.
    The callback runs on the reader thread — push to GLib.idle_add for UI.
    """

    def __init__(self, on_line):
        self._on_line = on_line
        self._saved_fd1 = None
        self._saved_stdout = None
        self._read_fd = None
        self._reader_thread = None

    def start(self):
        r, w = os.pipe()
        self._read_fd = r
        self._saved_fd1 = os.dup(1)
        try:
            sys.stdout.flush()
        except Exception:
            pass
        os.dup2(w, 1)
        os.close(w)
        self._saved_stdout = sys.stdout
        sys.stdout = os.fdopen(1, "w", buffering=1, closefd=False)
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()

    def _reader(self):
        try:
            with os.fdopen(self._read_fd, "r", buffering=1) as f:
                for line in f:
                    self._on_line(line)
        except Exception:
            pass

    def stop(self):
        try:
            sys.stdout.flush()
        except Exception:
            pass
        sys.stdout = self._saved_stdout
        os.dup2(self._saved_fd1, 1)
        os.close(self._saved_fd1)
        # Reader thread sees EOF and exits on its own.

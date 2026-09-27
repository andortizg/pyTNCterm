import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import os
import queue
import threading
import time

from gui import theme
from gui.monitor_panel import MonitorPanel
from gui.terminal_tab import TerminalTab
from gui.status_bar import StatusBar
from gui.toolbar import Toolbar
from gui.dialogs.settings_dialog import SettingsDialog, get_init_commands
from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.help_dialog import HelpDialog
from gui.dialogs.command_reference import CommandReferenceDialog
from gui.dialogs.command_search import CommandSearchPopup
from serial_port.serial_handler import SerialHandler
from core.config import Config
from core import tnc_commands
from core.yapp_handler import YappHandler, YappEvent
from core.tnc_init import TncInitializer
from gui.dialogs.yapp_dialog import YappTransferDialog


class MainWindow:
    """
    Main application window. Two-tab layout: Connection (interactive terminal)
    and Monitor (raw AX.25 traffic with frame coloring).

    Args:
        root: tk.Tk - the root Tk window
    """

    POLL_INTERVAL_MS = 50
    STATS_INTERVAL_MS = 1000
    # Line terminators sent on Enter (config key serial.line_ending)
    EOL_BYTES = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "None": ""}
    # Guard time around the 3 Ctrl-C used to leave transparent mode (> CMDTIME)
    TRANS_GUARD_S = 1.5

    def __init__(self, root):
        self.root = root
        self.config = Config()
        self.serial = SerialHandler()
        self._yapp = None          # YappHandler (created per transfer)
        self._yapp_dialog = None   # YappTransferDialog
        # _ui_queue: queue.Queue of (callable, args) - work posted from other
        # threads, executed in the Tk thread by _poll_serial
        self._ui_queue = queue.Queue()
        # _initializer: TncInitializer or None - running handshake/init
        self._initializer = None
        # _pending_cr: bool - last RX chunk ended with CR (for CR/LF normalization)
        self._pending_cr = False
        # _yapp_trans: bool - TNC was switched to transparent mode for YAPP
        self._yapp_trans = False

        # Load saved theme
        saved_theme = self.config.get("appearance", "theme", default="Dark Blue")
        theme.set_theme(saved_theme)

        self._setup_window()
        theme.apply_theme(self.root)
        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self._start_polling()
        self._update_from_config()

    def _setup_window(self):
        """Configures the main window: title, size, position."""
        self.root.title("pyTNCterm")
        self.root.configure(bg=theme.get("bg_dark"))

        w = self.config.get("window", "width", default=900)
        h = self.config.get("window", "height", default=700)
        x = self.config.get("window", "x", default=-1)
        y = self.config.get("window", "y", default=-1)

        if x >= 0 and y >= 0:
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.root.geometry(f"{w}x{h}")
            self.root.update_idletasks()
            sx = (self.root.winfo_screenwidth() - w) // 2
            sy = (self.root.winfo_screenheight() - h) // 2
            self.root.geometry(f"+{sx}+{sy}")

        self.root.minsize(700, 500)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_menu(self):
        """Builds the menu bar with File, Connection, View (with Theme), Help."""
        menu_opts = dict(
            bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            activebackground=theme.get("accent_primary"), activeforeground="#000000",
            font=("Segoe UI", 9), borderwidth=0, relief="flat"
        )

        menubar = tk.Menu(self.root, **menu_opts)

        # File
        file_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        file_menu.add_command(label="Settings...", command=self._open_settings,
                              accelerator="Ctrl+,")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._on_close,
                              accelerator="Ctrl+Shift+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Connection
        conn_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        conn_menu.add_command(label="Connect", command=self._connect,
                              accelerator="Ctrl+Shift+K")
        conn_menu.add_command(label="Disconnect", command=self._disconnect,
                              accelerator="Ctrl+Shift+D")
        conn_menu.add_separator()
        conn_menu.add_command(label="Initialize TNC", command=self._start_tnc_init,
                              accelerator="Ctrl+Shift+I")
        conn_menu.add_command(label="Send BREAK",
                              command=lambda: self._execute_key({"key": "break"}))
        menubar.add_cascade(label="Connection", menu=conn_menu)

        # YAPP
        yapp_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        yapp_menu.add_command(label="Send File...", command=self._yapp_send,
                              accelerator="Ctrl+Shift+S")
        yapp_menu.add_command(label="Receive File...", command=self._yapp_receive,
                              accelerator="Ctrl+Shift+R")
        yapp_menu.add_separator()
        yapp_menu.add_command(label="Set Download Directory...",
                              command=self._yapp_set_download_dir)
        menubar.add_cascade(label="YAPP", menu=yapp_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        view_menu.add_command(label="Clear Connection", command=self._clear_terminal,
                              accelerator="Ctrl+Shift+L")
        view_menu.add_command(label="Clear TX History", command=self._clear_tx)
        view_menu.add_command(label="Clear Monitor", command=self._clear_monitor)
        view_menu.add_separator()

        # Theme submenu
        self._theme_var = tk.StringVar(value=theme.get_current_theme_name())
        theme_menu = tk.Menu(view_menu, tearoff=0, **menu_opts)
        for name in theme.get_theme_names():
            theme_menu.add_radiobutton(
                label=name, variable=self._theme_var, value=name,
                command=lambda n=name: self._switch_theme(n)
            )
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        menubar.add_cascade(label="View", menu=view_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        help_menu.add_command(label="Help Contents", command=self._open_help,
                              accelerator="F1")
        help_menu.add_command(label="TNC Command Reference",
                              command=self._open_command_reference, accelerator="F3")
        help_menu.add_separator()
        help_menu.add_command(label="About pyTNCterm", command=self._open_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_ui(self):
        """Assembles layout: toolbar + notebook (Connection, Monitor) + status bar."""
        self._container = tk.Frame(self.root, bg=theme.get("bg_dark"))
        self._container.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        self.toolbar = Toolbar(self._container, callbacks={
            "connect": self._connect,
            "disconnect": self._disconnect,
            "clear_monitor": self._clear_monitor,
            "clear_channel": self._clear_terminal,
        })
        self.toolbar.pack(fill=tk.X)

        ttk.Separator(self._container, orient=tk.HORIZONTAL,
                       style="TSeparator").pack(fill=tk.X)

        # Status bar (packed first at bottom so it stays fixed)
        self.status_bar = StatusBar(self._container)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Notebook with 2 tabs (fills remaining space)
        self._notebook = ttk.Notebook(self._container, style="TNotebook")
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=(2, 0))

        # Tab 1: Connection (interactive terminal)
        self.terminal = TerminalTab(self._notebook, self.config,
                                    on_send=self._on_send,
                                    on_execute=self._on_execute_command,
                                    on_raw=self._on_raw)
        self._notebook.add(self.terminal, text="  ⚡ Connection  ")

        # Tab 2: Monitor (raw traffic with frame coloring)
        self.monitor = MonitorPanel(self._notebook, self.config)
        self._notebook.add(self.monitor, text="  ◆ Monitor  ")

        # Focus terminal on start
        self.root.after(100, self.terminal.focus_terminal)

        # Refocus terminal when Connection tab selected
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        """
        Refocuses the terminal when the Connection tab is selected.

        Args:
            event: tk.Event
        """
        try:
            idx = self._notebook.index(self._notebook.select())
            if idx == 0:  # Connection tab
                self.root.after(50, self.terminal.focus_terminal)
        except Exception:
            pass

    def _bind_keys(self):
        """
        Binds keyboard shortcuts. Application shortcuts use Ctrl+Shift+letter because
        plain Ctrl+letter in the TX area is sent to the TNC as a control character.
        """
        shortcuts = {
            "Q": self._on_close, "K": self._connect, "D": self._disconnect,
            "L": self._clear_terminal, "I": self._start_tnc_init,
            "S": self._yapp_send, "R": self._yapp_receive,
        }
        for letter, fn in shortcuts.items():
            self.root.bind(f"<Control-Shift-{letter}>", lambda e, f=fn: f())
            self.root.bind(f"<Control-Shift-{letter.lower()}>", lambda e, f=fn: f())
        self.root.bind("<Control-comma>", lambda e: self._open_settings())
        self.root.bind("<F1>", lambda e: self._open_help())
        self.root.bind("<F2>", lambda e: self._open_command_search())
        self.root.bind("<F3>", lambda e: self._open_command_reference())

    # -- Theme switching --

    def _switch_theme(self, name):
        """
        Switches theme, updates config colors, and refreshes entire UI.

        Args:
            name: str - theme name
        """
        theme.set_theme(name)
        theme.apply_theme(self.root)
        self._theme_var.set(name)

        # Update config colors from new theme
        color_map = {
            ("appearance", "monitor", "bg_color"): "monitor_bg",
            ("appearance", "monitor", "text_color"): "monitor_fg",
            ("appearance", "monitor", "info_color"): "monitor_info",
            ("appearance", "monitor", "error_color"): "monitor_error",
            ("appearance", "channel", "bg_color"): "channel_bg",
            ("appearance", "channel", "rx_color"): "channel_rx",
            ("appearance", "channel", "tx_color"): "channel_tx",
            ("appearance", "channel", "system_color"): "channel_system",
            ("appearance", "input", "bg_color"): "input_bg",
            ("appearance", "input", "text_color"): "input_fg",
            ("appearance", "input", "prompt_color"): "input_prompt",
        }
        for config_keys, theme_key in color_map.items():
            self.config.set(*config_keys, theme.get(theme_key))

        self.config.set("appearance", "theme", name)
        self.config.save()
        self._refresh_all_colors()

    def _refresh_all_colors(self):
        """Refreshes colors of all UI components after a theme change."""
        self.root.configure(bg=theme.get("bg_dark"))
        self._container.configure(bg=theme.get("bg_dark"))
        self.terminal.update_appearance()
        self.monitor.update_appearance()
        self.toolbar.update_appearance()
        self.status_bar.update_appearance()
        self._build_menu()  # Rebuild menu for new colors
        callsign = self.config.get("station", "callsign", default="")
        self.status_bar.set_callsign(callsign)
        tnc_model = self.config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        self.status_bar.set_tnc(tnc_model)

    # -- Serial connection --

    def _connect(self):
        """Connects to the serial port using current config."""
        port = self.config.get("serial", "port", default="")
        if not port or port == "(no ports found)":
            messagebox.showwarning("Connection",
                                   "No serial port configured.\nGo to Settings > Serial Port.",
                                   parent=self.root)
            return

        baudrate = self.config.get("serial", "baudrate", default=9600)
        databits = self.config.get("serial", "databits", default=8)
        stopbits = self.config.get("serial", "stopbits", default=1)
        parity = self.config.get("serial", "parity", default="None")
        flow = self.config.get("serial", "flow_control", default="None")

        success, msg = self.serial.connect(
            port=port, baudrate=baudrate, databits=databits,
            stopbits=stopbits, parity=parity, flow_control=flow
        )

        if success:
            sb = int(stopbits) if float(stopbits).is_integer() else stopbits
            pi = f"{port} {baudrate},{databits}" \
                 f"{'N' if parity == 'None' else parity[0]}{sb}"
            self.status_bar.set_connected(pi)
            self.toolbar.set_connected(True)
            self.terminal.append(f"--- Connected to {pi} ---\n", tag="system")
            self.monitor.append(f"--- Connected to {pi} ---\n", tag="info")
            # Switch to Connection tab
            self._notebook.select(0)
            self._pending_cr = False
            if self.config.get("tnc", "auto_init", default=True):
                self._start_tnc_init()
        else:
            messagebox.showerror("Connection Error", msg, parent=self.root)

    # -- TNC handshake / init --

    def _ui(self, fn, *args):
        """
        Schedules fn(*args) in the Tk thread (safe to call from any thread).

        Args:
            fn: callable - function to run in the GUI thread
            *args: arguments for fn
        """
        self._ui_queue.put((fn, args))

    def _start_tnc_init(self):
        """Starts the TNC handshake + init commands in a background thread."""
        if not self.serial.is_connected:
            self.terminal.append("--- Not connected ---\n", tag="error")
            return
        if self._initializer and self._initializer.is_running():
            self.terminal.append("[init] Already running\n", tag="system")
            return
        if self._yapp and self._yapp.is_active():
            return
        model = self.config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        target = {
            "baudrate": int(self.config.get("serial", "baudrate", default=9600)),
            "databits": int(self.config.get("serial", "databits", default=8)),
            "parity": self.config.get("serial", "parity", default="None"),
            "stopbits": float(self.config.get("serial", "stopbits", default=1)),
        }
        self._initializer = TncInitializer(
            self.serial, model, target,
            init_commands=get_init_commands(self.config, model),
            callsign=self.config.get("station", "callsign", default=""),
            do_handshake=self.config.get("tnc", "handshake", default=True),
            on_status=lambda m, lvl: self._ui(self._init_status, m, lvl),
            on_done=lambda ok: self._ui(self._init_done, ok),
        )
        self.terminal.append(f"[init] {model}\n", tag="system")
        self._initializer.start()

    def _init_status(self, message, level):
        """
        Shows an initializer progress message (GUI thread).

        Args:
            message: str - text
            level: str - "info", "ok", "warn", "error"
        """
        tag = "error" if level in ("warn", "error") else "system"
        self.terminal.append(f"[init] {message}\n", tag=tag)

    def _init_done(self, success):
        """
        Called when the initializer ends (GUI thread).

        Args:
            success: bool - True if the TNC was found and configured
        """
        self._initializer = None
        if success:
            self.terminal.append("[init] TNC ready\n", tag="system")

    def _stop_tnc_init(self):
        """Stops a running initializer, if any."""
        if self._initializer:
            self._initializer.stop()
            self._initializer = None

    def _disconnect(self):
        """Disconnects from the serial port."""
        self._stop_tnc_init()
        if self._yapp and self._yapp.is_active():
            self._yapp.abort("Disconnected")
        if self.serial.is_connected:
            self.serial.disconnect()
            self.status_bar.set_disconnected()
            self.toolbar.set_connected(False)
            self.terminal.append("--- Disconnected ---\n", tag="system")
            self.monitor.append("--- Disconnected ---\n", tag="info")

    # -- Data handling --

    def _eol(self):
        """
        Returns: str - line terminator configured for Enter ("\r", "\n", "\r\n" or "")
        """
        return self.EOL_BYTES.get(
            self.config.get("serial", "line_ending", default="CR"), "\r")

    def _on_send(self, text, already_sent=False):
        """
        Called when user presses Enter in the terminal.
        Sends the line (line mode) or only the terminator (character mode).

        Args:
            text: str - the line typed by the user
            already_sent: bool - True if the characters were sent while typing
        """
        if not self.serial.is_connected:
            self.terminal.append("--- Not connected ---\n", tag="error")
            return
        if already_sent:
            self.serial.send(self._eol())
        else:
            self.serial.send(text + self._eol())
        self.terminal.append_tx(text)

    def _on_raw(self, data):
        """
        Sends raw bytes immediately (control keys, character mode).
        Control characters are shown in the RX area as [^X].

        Args:
            data: bytes - bytes to send
        """
        if not self.serial.is_connected:
            self.terminal.append("--- Not connected ---\n", tag="error")
            return
        self.serial.send_bytes(data)
        if len(data) == 1 and data[0] < 0x20 and data[0] not in (0x08, 0x0D, 0x0A):
            name = "ESC" if data[0] == 0x1B else "^" + chr(data[0] + 0x40)
            self.terminal.append(f"[{name}]\n", tag="system")

    def _start_polling(self):
        """Starts periodic serial and stats polling."""
        self._poll_serial()
        self._poll_stats()

    # Control characters removed from displayed text (all except TAB and LF)
    _DISPLAY_STRIP = {c: None for c in range(32) if c not in (9, 10)}
    _DISPLAY_STRIP[127] = None

    def _normalize_rx(self, text):
        """
        Converts CR, LF and CR+LF to "\n" (even if split across chunks) and
        removes other control characters for display.

        Args:
            text: str - received text (latin-1 decoded)

        Returns: str - text ready to display
        """
        if self._pending_cr and text.startswith("\n"):
            text = text[1:]
        self._pending_cr = text.endswith("\r")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.translate(self._DISPLAY_STRIP)

    def _poll_serial(self):
        """Runs posted UI work, reads the serial queue and displays data.
        Routes data to the YAPP handler when a transfer is active.
        Consecutive chunks are joined to minimize Text widget updates."""
        # Work posted from other threads
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                try:
                    fn(*args)
                except Exception as e:
                    self.terminal.append(f"[internal error] {e}\n", tag="error")
        except queue.Empty:
            pass

        pending = bytearray()
        try:
            while True:
                msg_type, data = self.serial.rx_queue.get_nowait()

                if msg_type == "__DISCONNECTED__":
                    self._flush_rx(pending)
                    pending = bytearray()
                    self._stop_tnc_init()
                    self.status_bar.set_disconnected()
                    self.toolbar.set_connected(False)
                    self.terminal.append("--- Connection lost ---\n", tag="error")
                    self.monitor.append("--- Connection lost ---\n", tag="error")
                    if self._yapp and self._yapp.is_active():
                        self._yapp.abort("Serial connection lost")
                    continue

                if msg_type == "data" and data:
                    if self._yapp and self._yapp.is_active():
                        self._flush_rx(pending)
                        pending = bytearray()
                        self._yapp.process_data(data)
                    else:
                        pending.extend(data)
        except queue.Empty:
            pass
        self._flush_rx(pending)
        self.root.after(self.POLL_INTERVAL_MS, self._poll_serial)

    def _flush_rx(self, data):
        """
        Displays accumulated RX bytes in the terminal and the monitor.

        Args:
            data: bytes/bytearray - received bytes (may be empty)
        """
        if not data:
            return
        text = self._normalize_rx(bytes(data).decode("latin-1", errors="replace"))
        if text:
            self.terminal.append(text, tag="rx")
            self.monitor.append(text)

    def _poll_stats(self):
        """Updates TX/RX counters in status bar."""
        if self.serial.is_connected:
            stats = self.serial.get_stats()
            self.status_bar.update_counters(stats["tx_bytes"], stats["rx_bytes"])
        self.root.after(self.STATS_INTERVAL_MS, self._poll_stats)

    # -- Clear actions --

    def _clear_terminal(self):
        """Clears the connection terminal RX zone."""
        self.terminal.clear()

    def _clear_tx(self):
        """Clears the TX zone history."""
        self.terminal.clear_tx()

    def _clear_monitor(self):
        """Clears the monitor panel."""
        self.monitor.clear()

    # -- YAPP --

    def _yapp_can_start(self):
        """
        Checks that a YAPP transfer can be started.

        Returns: bool - True if connected, idle and no init running
        """
        if not self.serial.is_connected:
            messagebox.showwarning("YAPP", "Not connected to serial port.",
                                   parent=self.root)
            return False
        if (self._yapp and self._yapp.is_active()) or self._yapp_trans:
            messagebox.showwarning("YAPP", "A transfer is already in progress.",
                                   parent=self.root)
            return False
        if self._initializer and self._initializer.is_running():
            messagebox.showwarning("YAPP", "TNC initialization in progress.",
                                   parent=self.root)
            return False
        return True

    def _yapp_create(self, mode, filename=""):
        """
        Creates the YAPP handler (callbacks marshalled to the GUI thread) and dialog.

        Args:
            mode: str - "send" or "receive"
            filename: str - file name shown in the dialog
        """
        self._yapp = YappHandler(
            send_raw=self.serial.send_bytes,
            on_progress=lambda t, n: self._ui(self._yapp_on_progress, t, n),
            on_event=lambda ev, m: self._ui(self._yapp_on_event, ev, m),
            on_finished=lambda ok, m: self._ui(self._yapp_on_finished, ok, m),
            block_delay_ms=self.config.get("yapp", "block_delay_ms", default=0),
        )
        self._yapp_dialog = YappTransferDialog(
            self.root, mode=mode, filename=filename, on_cancel=self._yapp_cancel)
        if self.config.get("serial", "flow_control", default="None") != "RTS/CTS":
            self._yapp_dialog.log_event(
                YappEvent.INFO, "Warning: no RTS/CTS flow control. If blocks are lost, "
                                "enable RTS/CTS or set a block delay.")

    def _yapp_begin(self, start_fn, start_first=False):
        """
        Puts the TNC in transparent mode (if enabled) and calls start_fn in the
        GUI thread, before (receive) or after (send) switching the TNC.

        Args:
            start_fn: callable() -> tuple(bool, str) - starts the YAPP handler
            start_first: bool - True to start the handler before entering
                         transparent mode (receiver must not miss the first SI)
        """
        def start():
            if not self._yapp:
                return
            ok, msg = start_fn()
            if not ok:
                self._yapp_dialog.log_event(YappEvent.ERROR, msg)
                self._yapp_dialog.transfer_finished(False, msg)
                self._yapp = None
                self._yapp_leave_transparent()

        if not self.config.get("yapp", "transparent", default=True):
            start()
            return

        trans_cmd = self.config.get("yapp", "trans_cmd", default="TRANS")
        if start_first:
            start()
            if not self._yapp:
                return
        self._yapp_trans = True
        self._yapp_dialog.log_event(YappEvent.INFO,
                                    f"Switching TNC to transparent mode ({trans_cmd})")

        def worker():
            self.serial.send_bytes(b"\x03")      # to command mode
            time.sleep(0.5)
            self.serial.send(trans_cmd + "\r")
            if not start_first:
                time.sleep(0.8)
                self._ui(start)

        threading.Thread(target=worker, daemon=True).start()

    def _yapp_leave_transparent(self):
        """
        Leaves transparent mode: guard time, 3 x Ctrl-C, guard time, then the
        configured return command (e.g. "K" for converse). Runs in a thread.
        """
        if not self._yapp_trans:
            return
        ret_cmd = self.config.get("yapp", "return_cmd", default="K")
        guard = self.TRANS_GUARD_S

        def worker():
            time.sleep(guard)
            for _ in range(3):
                self.serial.send_bytes(b"\x03")
                time.sleep(0.2)
            time.sleep(guard)
            if ret_cmd:
                self.serial.send(ret_cmd + "\r")
            self._ui(self._yapp_trans_done)

        threading.Thread(target=worker, daemon=True).start()

    def _yapp_trans_done(self):
        """Marks the TNC as back from transparent mode (GUI thread)."""
        self._yapp_trans = False
        self.terminal.append("[YAPP] TNC back from transparent mode\n", tag="system")

    def _yapp_send(self):
        """YAPP file send - opens file picker and starts transfer."""
        if not self._yapp_can_start():
            return
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            parent=self.root, title="Select file to send via YAPP",
            initialdir=self.config.get("paths", "yapp_upload", default="") or None)
        if not filepath:
            return
        filename = os.path.basename(filepath)
        self._yapp_create("send", filename)
        self._yapp_dialog.update_file_info(filename, os.path.getsize(filepath))
        self._yapp_begin(lambda: self._yapp.start_send(filepath))

    def _yapp_receive(self):
        """YAPP file receive - starts listening for incoming file."""
        if not self._yapp_can_start():
            return
        download_dir = self.config.get("paths", "yapp_download", default="")
        if not download_dir:
            from tkinter import filedialog
            download_dir = filedialog.askdirectory(
                parent=self.root, title="Select download directory for YAPP")
            if not download_dir:
                return
            self.config.set("paths", "yapp_download", download_dir)
            self.config.save()
        self._yapp_create("receive")
        self._yapp_begin(lambda: self._yapp.start_receive(download_dir), start_first=True)

    def _yapp_on_progress(self, transferred, total):
        """
        Progreso YAPP (hilo GUI).

        Args:
            transferred: int - bytes transferidos
            total: int - total bytes
        """
        if self._yapp_dialog:
            if self._yapp and self._yapp.filename:
                self._yapp_dialog.update_file_info(self._yapp.filename,
                                                   self._yapp.file_size)
            self._yapp_dialog.update_progress(transferred, total)

    def _yapp_on_event(self, event_type, message):
        """
        Evento de control YAPP (hilo GUI).

        Args:
            event_type: YappEvent - tipo de evento
            message: str - mensaje descriptivo
        """
        if self._yapp_dialog:
            self._yapp_dialog.log_event(event_type, message)

    def _yapp_on_finished(self, success, message):
        """
        Fin de transferencia YAPP (hilo GUI). Devuelve la TNC al modo comando.

        Args:
            success: bool - si fue exitosa
            message: str - mensaje final
        """
        if self._yapp_dialog:
            self._yapp_dialog.transfer_finished(success, message)
        if self._yapp:
            self._yapp.reset_to_idle()
            self._yapp = None
        if self.serial.is_connected:
            self._yapp_leave_transparent()
        else:
            self._yapp_trans = False

    def _yapp_cancel(self):
        """Cancela la transferencia YAPP activa."""
        if self._yapp and self._yapp.is_active():
            self._yapp.cancel()
        elif self._yapp:
            # Cancelled while entering transparent mode
            self._yapp = None
            self._yapp_leave_transparent()

    def _yapp_set_download_dir(self):
        """Opens directory picker for YAPP download folder."""
        from tkinter import filedialog
        current = self.config.get("paths", "yapp_download", default="")
        d = filedialog.askdirectory(parent=self.root, initialdir=current or None,
                                    title="Select YAPP Download Directory")
        if d:
            self.config.set("paths", "yapp_download", d)
            self.config.save()

    # -- Dialogs --

    def _open_settings(self):
        SettingsDialog(self.root, self.config, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        """Called after settings saved. Applies theme, TNC model, and refreshes UI."""
        saved_theme = self.config.get("appearance", "theme",
                                      default=theme.get_current_theme_name())
        if saved_theme != theme.get_current_theme_name():
            theme.set_theme(saved_theme)
            theme.apply_theme(self.root)
        self._refresh_all_colors()
        self._sync_tnc_model()
        self.terminal.set_send_mode(self.config.get("serial", "send_mode", default="line"))

    def _sync_tnc_model(self):
        """Updates TNC model, autocomplete setting on terminal tab and status bar."""
        model = self.config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        self.terminal.set_tnc_model(model)
        self.status_bar.set_tnc(model)
        tnc_commands.clear_cache()
        # Sync autocomplete toggle
        ac_enabled = self.config.get("tnc", "autocomplete", default=True)
        self.terminal.set_autocomplete_enabled(ac_enabled)

    def _update_from_config(self):
        """Initial UI refresh from config."""
        self.terminal.update_appearance()
        self.monitor.update_appearance()
        callsign = self.config.get("station", "callsign", default="")
        self.status_bar.set_callsign(callsign)
        self._sync_tnc_model()
        self.terminal.set_send_mode(self.config.get("serial", "send_mode", default="line"))

    def _open_about(self):
        AboutDialog(self.root)

    def _open_help(self):
        HelpDialog(self.root)

    def _open_command_reference(self):
        """Opens the TNC Command Reference dialog (F3)."""
        model = self.config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        CommandReferenceDialog(self.root, model,
                               on_insert=self._handle_command_insert)

    def _open_command_search(self):
        """Opens the quick command search popup (F2)."""
        model = self.config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        CommandSearchPopup(self.root, model,
                           on_insert=self._handle_command_insert)

    def _handle_command_insert(self, cmd):
        """
        Handles a command selected from reference dialog or search popup.
        Same logic as the context menu execution.

        Args:
            cmd: dict - command definition
        """
        self._on_execute_command(cmd)

    # -- Command execution --

    def _on_execute_command(self, cmd):
        """
        Executes a TNC command received from the terminal context menu,
        command reference dialog, or search popup.

        Args:
            cmd: dict - command definition with type, and optionally:
                 syntax (text), key (key), steps (sequence),
                 or special type "__search__" to open search popup
        """
        cmd_type = cmd.get("type", "text")

        if cmd_type == "__search__":
            self._open_command_search()
            return

        if cmd_type == "text":
            # Insert into TX for user to edit
            self.terminal.insert_command(cmd.get("syntax", cmd.get("cmd", "")))
            # Switch to Connection tab
            self._notebook.select(0)
            return

        if cmd_type == "key":
            self._execute_key(cmd)
            return

        if cmd_type == "sequence":
            self._execute_sequence(cmd)
            return

    def _execute_key(self, cmd):
        """
        Sends a special key directly to the TNC via serial port.
        Supported keys: ctrl+A..Z, escape, break.

        Args:
            cmd: dict - with "key" field (e.g., "ctrl+C", "escape", "break")
        """
        if not self.serial.is_connected:
            self.terminal.append("--- Not connected ---\n", tag="error")
            return

        key = cmd.get("key", "").lower().strip()
        desc = cmd.get("desc", cmd.get("cmd", key))

        if key.startswith("ctrl+"):
            # ctrl+A = 0x01, ctrl+B = 0x02, ..., ctrl+Z = 0x1A
            letter = key[5:].upper()
            if len(letter) == 1 and "A" <= letter <= "Z":
                byte_val = ord(letter) - ord("A") + 1
                self.serial.send_bytes(bytes([byte_val]))
                self.terminal.append(f"[⚡ Sent {key.upper()}]\n", tag="system")
        elif key == "escape":
            self.serial.send_bytes(bytes([0x1B]))
            self.terminal.append("[⚡ Sent ESC]\n", tag="system")
        elif key == "break":
            self.serial.send_break()
            self.terminal.append("[⚡ Sent BREAK]\n", tag="system")
        else:
            self.terminal.append(f"[Unknown key: {key}]\n", tag="error")

    def _execute_sequence(self, cmd):
        """
        Executes a multi-step sequence in a background thread.
        Steps can be: ctrl key, text, wait.

        Args:
            cmd: dict - with "steps" list of step dicts
        """
        if not self.serial.is_connected:
            self.terminal.append("--- Not connected ---\n", tag="error")
            return

        steps = cmd.get("steps", [])
        desc = cmd.get("desc", cmd.get("cmd", "sequence"))
        self.terminal.append(f"[🔗 Executing: {desc}]\n", tag="system")

        def run_steps():
            """Runs sequence steps in a thread with waits."""
            import time
            for step in steps:
                action = step.get("action", "")
                if action == "ctrl":
                    letter = step.get("key", "").upper()
                    if len(letter) == 1 and "A" <= letter <= "Z":
                        byte_val = ord(letter) - ord("A") + 1
                        self.serial.send_bytes(bytes([byte_val]))
                elif action == "text":
                    value = step.get("value", "")
                    self.serial.send(value)
                elif action == "wait":
                    ms = step.get("ms", 100)
                    time.sleep(ms / 1000.0)
                elif action == "escape":
                    self.serial.send_bytes(bytes([0x1B]))
                elif action == "break":
                    self.serial.send_break()

        thread = threading.Thread(target=run_steps, daemon=True)
        thread.start()

    def _on_close(self):
        """Saves config, disconnects, and exits."""
        try:
            geo = self.root.geometry()
            parts = geo.split("+")
            size = parts[0].split("x")
            self.config.set("window", "width", int(size[0]))
            self.config.set("window", "height", int(size[1]))
            self.config.set("window", "x", int(parts[1]))
            self.config.set("window", "y", int(parts[2]))
            self.config.save()
        except Exception:
            pass
        self._stop_tnc_init()
        if self._yapp and self._yapp.is_active():
            self._yapp.cancel()
        if self.serial.is_connected:
            self.serial.disconnect()
        self.root.destroy()

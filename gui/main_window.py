import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import os
import queue
import threading

from gui import theme
from gui.monitor_panel import MonitorPanel
from gui.terminal_tab import TerminalTab
from gui.status_bar import StatusBar
from gui.toolbar import Toolbar
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.help_dialog import HelpDialog
from gui.dialogs.command_reference import CommandReferenceDialog
from gui.dialogs.command_search import CommandSearchPopup
from serial_port.serial_handler import SerialHandler
from core.config import Config
from core import tnc_commands
from core.yapp_handler import YappHandler, YappEvent
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

    def __init__(self, root):
        self.root = root
        self.config = Config()
        self.serial = SerialHandler()
        self._yapp = None          # YappHandler (created per transfer)
        self._yapp_dialog = None   # YappTransferDialog

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
        file_menu.add_command(label="Quit", command=self._on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Connection
        conn_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        conn_menu.add_command(label="Connect", command=self._connect, accelerator="Ctrl+K")
        conn_menu.add_command(label="Disconnect", command=self._disconnect,
                              accelerator="Ctrl+D")
        menubar.add_cascade(label="Connection", menu=conn_menu)

        # YAPP
        yapp_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        yapp_menu.add_command(label="Send File...", command=self._yapp_send,
                              accelerator="Ctrl+S")
        yapp_menu.add_command(label="Receive File...", command=self._yapp_receive,
                              accelerator="Ctrl+R")
        yapp_menu.add_separator()
        yapp_menu.add_command(label="Set Download Directory...",
                              command=self._yapp_set_download_dir)
        menubar.add_cascade(label="YAPP", menu=yapp_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        view_menu.add_command(label="Clear Connection", command=self._clear_terminal,
                              accelerator="Ctrl+L")
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
                                    on_execute=self._on_execute_command)
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
        """Binds keyboard shortcuts."""
        self.root.bind("<Control-q>", lambda e: self._on_close())
        self.root.bind("<Control-Q>", lambda e: self._on_close())
        self.root.bind("<Control-k>", lambda e: self._connect())
        self.root.bind("<Control-K>", lambda e: self._connect())
        self.root.bind("<Control-d>", lambda e: self._disconnect())
        self.root.bind("<Control-D>", lambda e: self._disconnect())
        self.root.bind("<Control-l>", lambda e: self._clear_terminal())
        self.root.bind("<Control-L>", lambda e: self._clear_terminal())
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
            pi = f"{port} {baudrate},{databits}" \
                 f"{'N' if parity == 'None' else parity[0]}{int(stopbits)}"
            self.status_bar.set_connected(pi)
            self.toolbar.set_connected(True)
            self.terminal.append(f"--- Connected to {pi} ---\n", tag="system")
            self.monitor.append(f"--- Connected to {pi} ---\n", tag="info")
            # Switch to Connection tab
            self._notebook.select(0)
        else:
            messagebox.showerror("Connection Error", msg, parent=self.root)

    def _disconnect(self):
        """Disconnects from the serial port."""
        if self.serial.is_connected:
            self.serial.disconnect()
            self.status_bar.set_disconnected()
            self.toolbar.set_connected(False)
            self.terminal.append("--- Disconnected ---\n", tag="system")
            self.monitor.append("--- Disconnected ---\n", tag="info")

    # -- Data handling --

    def _on_send(self, text):
        """
        Called when user presses Enter in the terminal.
        Sends text to TNC and displays it.

        Args:
            text: str - the command text to send
        """
        if not self.serial.is_connected:
            self.terminal.append("--- Not connected ---\n", tag="error")
            return

        # Send with CR
        self.serial.send(text + "\r")
        # Display sent text
        self.terminal.append_tx(text)

    def _start_polling(self):
        """Starts periodic serial and stats polling."""
        self._poll_serial()
        self._poll_stats()

    def _poll_serial(self):
        """Reads from serial queue, displays in terminal and monitor.
        Routes data to YAPP handler when a transfer is active."""
        try:
            while True:
                msg_type, data = self.serial.rx_queue.get_nowait()

                if msg_type == "__DISCONNECTED__":
                    self.status_bar.set_disconnected()
                    self.toolbar.set_connected(False)
                    self.terminal.append("--- Connection lost ---\n", tag="error")
                    self.monitor.append("--- Connection lost ---\n", tag="error")
                    # Cancel active YAPP transfer on disconnect
                    if self._yapp and self._yapp.is_active():
                        self._yapp.cancel()
                    continue

                if msg_type == "data" and data:
                    # Route to YAPP handler if transfer active
                    if self._yapp and self._yapp.is_active():
                        self._yapp.process_data(data)
                        continue

                    text = data.decode("latin-1", errors="replace")
                    # Show in terminal (connection tab)
                    self.terminal.append(text, tag="rx")
                    # Show in monitor (with auto frame classification)
                    self.monitor.append(text)
        except queue.Empty:
            pass
        self.root.after(self.POLL_INTERVAL_MS, self._poll_serial)

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

    # -- YAPP (placeholder) --

    def _yapp_send(self):
        """YAPP file send - opens file picker and starts transfer."""
        if not self.serial.is_connected:
            messagebox.showwarning("YAPP", "Not connected to serial port.",
                                   parent=self.root)
            return
        if self._yapp and self._yapp.is_active():
            messagebox.showwarning("YAPP", "A transfer is already in progress.",
                                   parent=self.root)
            return

        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            parent=self.root, title="Select file to send via YAPP")
        if not filepath:
            return

        # Create YAPP handler
        self._yapp = YappHandler(
            send_raw=self.serial.send_bytes,
            on_progress=self._yapp_on_progress,
            on_event=self._yapp_on_event,
            on_finished=self._yapp_on_finished,
        )

        # Create dialog
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        self._yapp_dialog = YappTransferDialog(
            self.root, mode="send", filename=filename,
            on_cancel=self._yapp_cancel)
        self._yapp_dialog.update_file_info(filename, file_size)

        # Start transfer
        ok, msg = self._yapp.start_send(filepath)
        if not ok:
            self._yapp_dialog.log_event(YappEvent.ERROR, msg)
            self._yapp_dialog.transfer_finished(False, msg)
            self._yapp = None

    def _yapp_receive(self):
        """YAPP file receive - starts listening for incoming file."""
        if not self.serial.is_connected:
            messagebox.showwarning("YAPP", "Not connected to serial port.",
                                   parent=self.root)
            return
        if self._yapp and self._yapp.is_active():
            messagebox.showwarning("YAPP", "A transfer is already in progress.",
                                   parent=self.root)
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

        # Create YAPP handler
        self._yapp = YappHandler(
            send_raw=self.serial.send_bytes,
            on_progress=self._yapp_on_progress,
            on_event=self._yapp_on_event,
            on_finished=self._yapp_on_finished,
        )

        # Create dialog
        self._yapp_dialog = YappTransferDialog(
            self.root, mode="receive", filename="",
            on_cancel=self._yapp_cancel)

        # Start receive
        ok, msg = self._yapp.start_receive(download_dir)
        if not ok:
            self._yapp_dialog.log_event(YappEvent.ERROR, msg)
            self._yapp_dialog.transfer_finished(False, msg)
            self._yapp = None

    def _yapp_on_progress(self, transferred, total):
        """
        Callback de progreso YAPP. Se ejecuta en thread del serial handler,
        así que programamos actualización en el hilo GUI.

        Args:
            transferred: int - bytes transferidos
            total: int - total bytes
        """
        if self._yapp_dialog:
            self.root.after(0, self._yapp_dialog.update_progress, transferred, total)
            # Actualizar info del archivo si es recepción y acabamos de saber el nombre
            if self._yapp and self._yapp.filename:
                self.root.after(0, self._yapp_dialog.update_file_info,
                                self._yapp.filename, self._yapp.file_size)

    def _yapp_on_event(self, event_type, message):
        """
        Callback de evento de control YAPP.

        Args:
            event_type: YappEvent - tipo de evento
            message: str - mensaje descriptivo
        """
        if self._yapp_dialog:
            self.root.after(0, self._yapp_dialog.log_event, event_type, message)

    def _yapp_on_finished(self, success, message):
        """
        Callback de fin de transferencia YAPP.

        Args:
            success: bool - si fue exitosa
            message: str - mensaje final
        """
        if self._yapp_dialog:
            self.root.after(0, self._yapp_dialog.transfer_finished, success, message)
        if self._yapp:
            self._yapp.reset_to_idle()
            self._yapp = None

    def _yapp_cancel(self):
        """Cancela la transferencia YAPP activa."""
        if self._yapp and self._yapp.is_active():
            self._yapp.cancel()

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
        if self.serial.is_connected:
            self.serial.disconnect()
        self.root.destroy()

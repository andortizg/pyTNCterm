import tkinter as tk
import tkinter.ttk as ttk
from tkinter import colorchooser, filedialog, font as tkfont
from gui import theme
from serial_port.serial_handler import SerialHandler

# Init command templates. "{CALL}" is replaced by the station callsign.
_INIT_AEA = ("MYCALL {CALL}\nECHO OFF\nXFLOW OFF\nAUTOLF ON\n8BITCONV ON\n"
             "MONITOR 4\nMCOM ON\n")
_INIT_KANTRONICS = ("INTFACE TERMINAL\nMYCALL {CALL}\nECHO OFF\nXFLOW OFF\nAUTOLF ON\n"
                    "8BITCONV ON\nMONITOR ON\nMCOM ON\n")
_INIT_TNC2 = "MYCALL {CALL}\nECHO OFF\nXFLOW OFF\nAUTOLF ON\nMONITOR ON\nMCOM ON\n"

# TNC model definitions: model name -> {modes: list of str, init: str default init commands}
TNC_MODELS = {
    "Generic / TNC-2 Compatible": {"modes": ["Packet"], "init": _INIT_TNC2},
    "Kantronics KPC-3 / KPC-3+": {"modes": ["Packet"], "init": _INIT_KANTRONICS},
    "Kantronics KAM / KAM+": {
        "modes": ["Packet", "CW", "RTTY", "AMTOR"], "init": _INIT_KANTRONICS},
    "Kantronics KAM-XL": {
        "modes": ["Packet", "CW", "RTTY", "AMTOR", "PACTOR"], "init": _INIT_KANTRONICS},
    "AEA / Timewave PK-232": {
        "modes": ["Packet", "CW", "RTTY", "AMTOR", "SSTV", "FAX"], "init": _INIT_AEA},
    "AEA PK-88": {"modes": ["Packet"], "init": _INIT_AEA},
    "MFJ-1270 / MFJ-1274": {"modes": ["Packet"], "init": _INIT_TNC2},
    "MFJ-1278 / MFJ-1278B": {
        "modes": ["Packet", "CW", "RTTY", "AMTOR", "SSTV", "FAX"], "init": _INIT_TNC2},
    "SCS PTC-II / IIe / IIpro": {
        "modes": ["Packet", "PACTOR", "PACTOR-II", "RTTY", "CW", "AMTOR", "PSK31"],
        "init": "ECHO 1\nMON 3\n"},
    "SCS PTC-III": {
        "modes": ["Packet", "PACTOR", "PACTOR-II", "PACTOR-III", "RTTY", "CW", "AMTOR",
                  "PSK31"],
        "init": "ECHO 1\nMON 3\n"},
    "SCS Tracker / DSP TNC": {"modes": ["Packet", "APRS"], "init": ""},
    "TNC-Pi": {"modes": ["Packet", "APRS"], "init": ""},
    "Other": {"modes": ["Packet"], "init": ""},
}

# Defaults shipped by previous versions (replaced automatically by the new ones)
LEGACY_INITS = {
    "ECHO ON\nMON ON\nMCOM ON",
    "INT TERMINAL\nECHO ON\nMON ON\nMCOM ON\nFLOW OFF",
    "ECHO ON\nMON ON",
}

SEND_MODES = {"line": "On Enter (line mode)", "char": "Each key as typed (character mode)"}
LINE_ENDINGS = {"CR": "CR", "LF": "LF", "CRLF": "CR+LF", "None": "Nothing"}


def get_init_commands(config, model):
    """
    Returns the init commands for a model: the user's text, or the model default
    if the user never changed it (or it is a legacy default).

    Args:
        config: Config - application configuration
        model: str - TNC model name

    Returns: str - init commands, one per line
    """
    default = TNC_MODELS.get(model, TNC_MODELS["Other"])["init"]
    user = config.get("tnc", "init_commands", default=None)
    if user is None or user.strip() in LEGACY_INITS:
        return default
    return user


class SettingsDialog(tk.Toplevel):
    """
    Settings dialog with tabs: Station, Serial Port, Appearance (with theme selector), Paths.

    Args:
        parent: tk widget - parent window
        config: Config - application configuration instance
        on_save: callable or None - called after settings are saved
    """

    def __init__(self, parent, config, on_save=None):
        super().__init__(parent)
        self._config = config
        self._on_save = on_save
        self._vars = {}
        self._color_labels = {}

        self.title("Settings")
        self.geometry("620x690")
        self.resizable(False, False)
        self.configure(bg=theme.get("dialog_bg"))
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._center()

    def _center(self):
        """Centers the dialog on screen."""
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Builds the settings dialog with notebook tabs and buttons."""
        main = tk.Frame(self, bg=theme.get("dialog_bg"))
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        nb = ttk.Notebook(main, style="TNotebook")
        nb.pack(fill=tk.BOTH, expand=True)

        nb.add(self._build_station_tab(nb), text="  Station  ")
        nb.add(self._build_tnc_tab(nb), text="  TNC  ")
        nb.add(self._build_serial_tab(nb), text="  Serial Port  ")
        nb.add(self._build_appearance_tab(nb), text="  Appearance  ")
        nb.add(self._build_paths_tab(nb), text="  Paths  ")

        btn_frame = tk.Frame(main, bg=theme.get("dialog_bg"))
        btn_frame.pack(fill=tk.X, pady=(12, 4))
        ttk.Button(btn_frame, text="Cancel", style="TButton",
                   command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="Save", style="Accent.TButton",
                   command=self._save).pack(side=tk.RIGHT, padx=4)

    def _build_station_tab(self, parent):
        """Builds the Station settings tab. Returns: tk.Frame"""
        frame = tk.Frame(parent, bg=theme.get("dialog_bg"))
        tk.Label(frame, text="Station Information", font=("Segoe UI", 12, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=16, pady=(16, 12))
        grid = tk.Frame(frame, bg=theme.get("dialog_bg"))
        grid.pack(fill=tk.X, padx=24)
        self._add_entry(grid, 0, "Callsign:", "station.callsign",
                        self._config.get("station", "callsign", default=""))
        self._add_entry(grid, 1, "Name:", "station.name",
                        self._config.get("station", "name", default=""))
        self._add_entry(grid, 2, "Grid Locator:", "station.grid_locator",
                        self._config.get("station", "grid_locator", default=""))
        return frame

    def _build_tnc_tab(self, parent):
        """Builds the TNC settings tab: model selector, supported modes, init commands.
        Returns: tk.Frame"""
        frame = tk.Frame(parent, bg=theme.get("dialog_bg"))

        tk.Label(frame, text="TNC Configuration", font=("Segoe UI", 12, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=16, pady=(16, 12))

        grid = tk.Frame(frame, bg=theme.get("dialog_bg"))
        grid.pack(fill=tk.X, padx=24)

        # Model selector
        models = list(TNC_MODELS.keys())
        current_model = self._config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        self._add_combo(grid, 0, "TNC Model:", "tnc.model", models, current_model)

        # Supported modes (read-only, updated when model changes)
        row = 1
        tk.Label(grid, text="Supported Modes:", font=("Segoe UI", 10),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_primary"), anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))

        modes_text = ", ".join(TNC_MODELS.get(current_model, {}).get("modes", ["Packet"]))
        self._modes_var = tk.StringVar(value=modes_text)
        self._modes_label = tk.Label(
            grid, textvariable=self._modes_var, font=("Consolas", 10, "bold"),
            bg=theme.get("dialog_bg"), fg=theme.get("accent_secondary"), anchor="w"
        )
        self._modes_label.grid(row=row, column=1, sticky="w", pady=4)
        grid.columnconfigure(1, weight=1)

        # Autocomplete toggle
        row = 2
        tk.Label(grid, text="TX Autocomplete:", font=("Segoe UI", 10),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_primary"), anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))

        ac_frame = tk.Frame(grid, bg=theme.get("dialog_bg"))
        ac_frame.grid(row=row, column=1, sticky="w", pady=4)

        current_ac = self._config.get("tnc", "autocomplete", default=True)
        self._ac_var = tk.BooleanVar(value=current_ac)
        ac_check = tk.Checkbutton(
            ac_frame, text="Show command suggestions while typing in TX",
            variable=self._ac_var,
            bg=theme.get("dialog_bg"), fg=theme.get("text_primary"),
            selectcolor=theme.get("entry_bg"),
            activebackground=theme.get("dialog_bg"),
            activeforeground=theme.get("text_primary"),
            font=("Segoe UI", 9),
        )
        ac_check.pack(side=tk.LEFT)

        # Auto-init / handshake toggles
        self._auto_init_var = tk.BooleanVar(
            value=self._config.get("tnc", "auto_init", default=True))
        self._handshake_var = tk.BooleanVar(
            value=self._config.get("tnc", "handshake", default=True))
        self._add_check(grid, 3, "On Connect:", self._auto_init_var,
                        "Initialize TNC (send init commands)")
        self._add_check(grid, 4, "", self._handshake_var,
                        "Detect TNC first (probe / autobaud '*' / baud scan)")

        # Init commands (editable text area)
        tk.Label(frame, text="Initialization Commands", font=("Segoe UI", 10, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_cyan")
                 ).pack(anchor="w", padx=24, pady=(16, 4))

        hint_row = tk.Frame(frame, bg=theme.get("dialog_bg"))
        hint_row.pack(fill=tk.X, padx=24, pady=(0, 4))
        tk.Label(hint_row, text="One per line. {CALL} = callsign, @WAIT ms = pause, "
                                "# = comment",
                 font=("Segoe UI", 8), bg=theme.get("dialog_bg"),
                 fg=theme.get("text_dim")).pack(side=tk.LEFT)
        ttk.Button(hint_row, text="Restore default", style="TButton",
                   command=self._restore_default_init).pack(side=tk.RIGHT)

        init_frame = tk.Frame(frame, bg=theme.get("border_color"), bd=1)
        init_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))

        current_init = get_init_commands(self._config, current_model)
        self._init_text = tk.Text(
            init_frame, bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
            font=("Consolas", 10), wrap=tk.WORD, height=7,
            borderwidth=0, highlightthickness=0, padx=6, pady=4,
            insertbackground=theme.get("accent_secondary"),
            selectbackground=theme.get("bg_highlight"), selectforeground="#ffffff",
        )
        self._init_text.pack(fill=tk.BOTH, expand=True)
        self._init_text.insert("1.0", current_init)

        # Bind model combobox change to update modes and init commands
        model_var = self._vars.get("tnc.model")
        if model_var:
            model_var.trace_add("write", self._on_tnc_model_changed)

        return frame

    def _on_tnc_model_changed(self, *args):
        """Called when TNC model combobox changes. Updates modes display and init commands."""
        model = self._vars.get("tnc.model", tk.StringVar()).get()
        info = TNC_MODELS.get(model, TNC_MODELS["Other"])

        # Update modes label
        self._modes_var.set(", ".join(info["modes"]))

        # Update init commands (only if user hasn't modified them from the previous default)
        # Get previous model's default init
        current_init_text = self._init_text.get("1.0", "end-1c").strip()
        # Check if current text matches any model's default
        is_default = False
        for m_info in TNC_MODELS.values():
            if current_init_text == m_info["init"].strip() \
                    or current_init_text in LEGACY_INITS:
                is_default = True
                break
        if is_default or not current_init_text:
            self._init_text.delete("1.0", tk.END)
            self._init_text.insert("1.0", info["init"])

    def _restore_default_init(self):
        """Replaces the init commands text with the default for the selected model."""
        model = self._vars.get("tnc.model", tk.StringVar()).get()
        info = TNC_MODELS.get(model, TNC_MODELS["Other"])
        self._init_text.delete("1.0", tk.END)
        self._init_text.insert("1.0", info["init"])

    def _build_serial_tab(self, parent):
        """Builds the Serial Port settings tab. Returns: tk.Frame"""
        frame = tk.Frame(parent, bg=theme.get("dialog_bg"))
        tk.Label(frame, text="Serial Port Configuration", font=("Segoe UI", 12, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=16, pady=(16, 12))
        grid = tk.Frame(frame, bg=theme.get("dialog_bg"))
        grid.pack(fill=tk.X, padx=24)

        ports = SerialHandler.list_ports()
        current_port = self._config.get("serial", "port", default="")
        if current_port and current_port not in ports:
            ports.append(current_port)
        if not ports:
            ports = ["(no ports found)"]
        self._add_combo(grid, 0, "Port:", "serial.port", ports, current_port)
        bauds = ["300", "1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
        self._add_combo(grid, 1, "Baud Rate:", "serial.baudrate", bauds,
                        str(self._config.get("serial", "baudrate", default=9600)))
        self._add_combo(grid, 2, "Data Bits:", "serial.databits", ["7", "8"],
                        str(self._config.get("serial", "databits", default=8)))
        self._add_combo(grid, 3, "Stop Bits:", "serial.stopbits", ["1", "1.5", "2"],
                        str(self._config.get("serial", "stopbits", default=1)))
        self._add_combo(grid, 4, "Parity:", "serial.parity",
                        ["None", "Even", "Odd", "Mark", "Space"],
                        self._config.get("serial", "parity", default="None"))
        self._add_combo(grid, 5, "Flow Control:", "serial.flow_control",
                        ["None", "RTS/CTS", "XON/XOFF"],
                        self._config.get("serial", "flow_control", default="None"))

        btn_frame = tk.Frame(frame, bg=theme.get("dialog_bg"))
        btn_frame.pack(fill=tk.X, padx=24, pady=(8, 0))
        ttk.Button(btn_frame, text="↻ Refresh Ports", style="TButton",
                   command=self._refresh_ports).pack(side=tk.LEFT)

        # Keyboard / transmission
        tk.Label(frame, text="Keyboard Transmission", font=("Segoe UI", 10, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_cyan")
                 ).pack(anchor="w", padx=24, pady=(14, 4))
        grid2 = tk.Frame(frame, bg=theme.get("dialog_bg"))
        grid2.pack(fill=tk.X, padx=24)
        cur_mode = self._config.get("serial", "send_mode", default="line")
        self._add_combo(grid2, 0, "Send Characters:", "serial.send_mode",
                        list(SEND_MODES.values()),
                        SEND_MODES.get(cur_mode, SEND_MODES["line"]))
        cur_eol = self._config.get("serial", "line_ending", default="CR")
        self._add_combo(grid2, 1, "On Enter Send:", "serial.line_ending",
                        list(LINE_ENDINGS.values()),
                        LINE_ENDINGS.get(cur_eol, "CR"))

        # YAPP
        tk.Label(frame, text="YAPP Transfers", font=("Segoe UI", 10, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_cyan")
                 ).pack(anchor="w", padx=24, pady=(14, 4))
        grid3 = tk.Frame(frame, bg=theme.get("dialog_bg"))
        grid3.pack(fill=tk.X, padx=24)
        self._yapp_trans_var = tk.BooleanVar(
            value=self._config.get("yapp", "transparent", default=True))
        self._add_check(grid3, 0, "TNC Mode:", self._yapp_trans_var,
                        "Switch TNC to TRANSparent mode during transfer")
        self._add_entry(grid3, 1, "Block Delay (ms):", "yapp.block_delay_ms",
                        str(self._config.get("yapp", "block_delay_ms", default=0)))
        return frame

    def _build_appearance_tab(self, parent):
        """Builds the Appearance tab with theme selector + color pickers. Returns: tk.Frame"""
        outer = tk.Frame(parent, bg=theme.get("dialog_bg"))

        canvas = tk.Canvas(outer, bg=theme.get("dialog_bg"), highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        frame = tk.Frame(canvas, bg=theme.get("dialog_bg"))
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        tk.Label(frame, text="Theme & Colors", font=("Segoe UI", 12, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=16, pady=(16, 8))

        grid = tk.Frame(frame, bg=theme.get("dialog_bg"))
        grid.pack(fill=tk.X, padx=24)

        # ---- Theme selector ----
        row = 0
        self._add_combo(grid, row, "Theme:", "appearance.theme",
                        theme.get_theme_names(), theme.get_current_theme_name())
        row += 1

        # ---- Font ----
        available_fonts = sorted(set(tkfont.families()))
        mono_fonts = [f for f in available_fonts if any(
            k in f.lower() for k in ["mono", "consol", "courier", "fixed", "terminal", "code"]
        )]
        if not mono_fonts:
            mono_fonts = available_fonts[:20]
        self._add_combo(grid, row, "Font Family:", "appearance.font_family",
                        mono_fonts,
                        self._config.get("appearance", "font_family", default="Consolas"))
        row += 1
        sizes = [str(s) for s in range(8, 21)]
        self._add_combo(grid, row, "Font Size:", "appearance.font_size", sizes,
                        str(self._config.get("appearance", "font_size", default=11)))

        # ---- Color sections ----
        sections = [
            ("Monitor Panel", "monitor", [
                ("Background", "bg_color"), ("Text", "text_color"),
                ("Info Text", "info_color"), ("Error Text", "error_color")
            ]),
            ("Channel Tabs", "channel", [
                ("Background", "bg_color"), ("RX Text", "rx_color"),
                ("TX Text", "tx_color"), ("System Text", "system_color")
            ]),
            ("Input Line", "input", [
                ("Background", "bg_color"), ("Text", "text_color"),
                ("Prompt", "prompt_color")
            ]),
        ]
        for section_label, section_key, colors in sections:
            row += 1
            tk.Label(grid, text=section_label, font=("Segoe UI", 10, "bold"),
                     bg=theme.get("dialog_bg"), fg=theme.get("accent_cyan")
                     ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(14, 4))
            for color_label, color_key in colors:
                row += 1
                current = self._config.get("appearance", section_key, color_key, default="#ffffff")
                self._add_color_picker(grid, row, f"  {color_label}:",
                                       f"appearance.{section_key}.{color_key}", current)
        return outer

    def _build_paths_tab(self, parent):
        """Builds the Paths settings tab. Returns: tk.Frame"""
        frame = tk.Frame(parent, bg=theme.get("dialog_bg"))
        tk.Label(frame, text="File Paths", font=("Segoe UI", 12, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=16, pady=(16, 12))
        for label_text, key in [
            ("YAPP Download Directory:", "yapp_download"),
            ("YAPP Upload Directory:", "yapp_upload"),
            ("Log Directory:", "log_directory"),
        ]:
            row_frame = tk.Frame(frame, bg=theme.get("dialog_bg"))
            row_frame.pack(fill=tk.X, padx=24, pady=4)
            tk.Label(row_frame, text=label_text, font=("Segoe UI", 10),
                     bg=theme.get("dialog_bg"), fg=theme.get("text_primary"),
                     width=24, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=self._config.get("paths", key, default=""))
            self._vars[f"paths.{key}"] = var
            tk.Entry(row_frame, textvariable=var, width=30,
                     bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
                     font=("Segoe UI", 10), borderwidth=1,
                     insertbackground=theme.get("accent_secondary")
                     ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
            ttk.Button(row_frame, text="Browse...", style="TButton",
                       command=lambda v=var: self._browse_dir(v)).pack(side=tk.RIGHT)
        return frame

    # --- Helpers ---

    def _add_entry(self, grid, row, label, var_key, value):
        """Adds a label + entry row."""
        tk.Label(grid, text=label, font=("Segoe UI", 10),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_primary"), anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        var = tk.StringVar(value=value)
        self._vars[var_key] = var
        tk.Entry(grid, textvariable=var, width=28,
                 bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
                 font=("Consolas", 11), borderwidth=1,
                 insertbackground=theme.get("accent_secondary")
                 ).grid(row=row, column=1, sticky="we", pady=4)
        grid.columnconfigure(1, weight=1)

    def _add_check(self, grid, row, label, var, text):
        """
        Adds a label + checkbutton row.

        Args:
            grid: tk.Frame - grid container
            row: int - grid row
            label: str - left label text
            var: tk.BooleanVar - bound variable
            text: str - checkbutton text
        """
        tk.Label(grid, text=label, font=("Segoe UI", 10),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_primary"), anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 8))
        tk.Checkbutton(
            grid, text=text, variable=var,
            bg=theme.get("dialog_bg"), fg=theme.get("text_primary"),
            selectcolor=theme.get("entry_bg"),
            activebackground=theme.get("dialog_bg"),
            activeforeground=theme.get("text_primary"),
            font=("Segoe UI", 9),
        ).grid(row=row, column=1, sticky="w", pady=2)

    def _add_combo(self, grid, row, label, var_key, values, current):
        """Adds a label + combobox row."""
        tk.Label(grid, text=label, font=("Segoe UI", 10),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_primary"), anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        var = tk.StringVar(value=current)
        self._vars[var_key] = var
        combo = ttk.Combobox(grid, textvariable=var, values=values,
                             state="readonly", style="TCombobox", width=25)
        combo.grid(row=row, column=1, sticky="we", pady=4)
        grid.columnconfigure(1, weight=1)

    def _add_color_picker(self, grid, row, label, var_key, current_color):
        """Adds a label + color swatch + pick button row."""
        tk.Label(grid, text=label, font=("Segoe UI", 10),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_primary"), anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        var = tk.StringVar(value=current_color)
        self._vars[var_key] = var
        sf = tk.Frame(grid, bg=theme.get("dialog_bg"))
        sf.grid(row=row, column=1, sticky="w", pady=3)
        swatch = tk.Label(sf, text="  ", bg=current_color, width=4, height=1,
                          relief="solid", bd=1)
        swatch.pack(side=tk.LEFT, padx=(0, 6))
        self._color_labels[var_key] = swatch
        hex_lbl = tk.Label(sf, text=current_color, font=("Consolas", 9),
                           bg=theme.get("dialog_bg"), fg=theme.get("text_secondary"))
        hex_lbl.pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(sf, text="Pick...", font=("Segoe UI", 8),
                  bg=theme.get("button_bg"), fg=theme.get("button_fg"),
                  activebackground=theme.get("button_active"),
                  bd=0, padx=8, pady=1, cursor="hand2",
                  command=lambda v=var, s=swatch, h=hex_lbl: self._pick_color(v, s, h)
                  ).pack(side=tk.LEFT)

    def _pick_color(self, var, swatch, hex_label):
        """Opens color picker and updates swatch."""
        color = colorchooser.askcolor(initialcolor=var.get(), parent=self)
        if color and color[1]:
            var.set(color[1])
            swatch.config(bg=color[1])
            hex_label.config(text=color[1])

    def _browse_dir(self, var):
        """Opens directory selection dialog."""
        d = filedialog.askdirectory(parent=self, initialdir=var.get() or None)
        if d:
            var.set(d)

    def _refresh_ports(self):
        """Refreshes serial port list."""
        ports = SerialHandler.list_ports()
        if not ports:
            ports = ["(no ports found)"]
        # Update all comboboxes in widget tree
        self._update_combo_in_tree(self, "serial.port", ports)

    def _update_combo_in_tree(self, widget, var_key, values):
        """Recursively finds the combobox for var_key and updates its values."""
        if isinstance(widget, ttk.Combobox):
            var = self._vars.get(var_key)
            if var and str(widget.cget("textvariable")) == str(var):
                widget["values"] = values
        for child in widget.winfo_children():
            self._update_combo_in_tree(child, var_key, values)

    def _save(self):
        """Saves all settings to config and closes."""
        # Station
        for key in ["callsign", "name", "grid_locator"]:
            var = self._vars.get(f"station.{key}")
            if var:
                self._config.set("station", key, var.get())

        # TNC
        self._config.set("tnc", "model",
                         self._vars.get("tnc.model", tk.StringVar()).get())
        self._config.set("tnc", "init_commands",
                         self._init_text.get("1.0", "end-1c"))
        self._config.set("tnc", "autocomplete", self._ac_var.get())
        self._config.set("tnc", "auto_init", self._auto_init_var.get())
        self._config.set("tnc", "handshake", self._handshake_var.get())

        # Serial
        self._config.set("serial", "port", self._vars.get("serial.port", tk.StringVar()).get())
        baud = self._vars.get("serial.baudrate", tk.StringVar()).get()
        self._config.set("serial", "baudrate", int(baud) if baud.isdigit() else 9600)
        dbits = self._vars.get("serial.databits", tk.StringVar()).get()
        self._config.set("serial", "databits", int(dbits) if dbits.isdigit() else 8)
        sbits = self._vars.get("serial.stopbits", tk.StringVar()).get()
        try:
            self._config.set("serial", "stopbits", float(sbits))
        except ValueError:
            self._config.set("serial", "stopbits", 1)
        self._config.set("serial", "parity",
                         self._vars.get("serial.parity", tk.StringVar()).get())
        self._config.set("serial", "flow_control",
                         self._vars.get("serial.flow_control", tk.StringVar()).get())

        mode_label = self._vars.get("serial.send_mode", tk.StringVar()).get()
        self._config.set("serial", "send_mode",
                         next((k for k, v in SEND_MODES.items() if v == mode_label), "line"))
        eol_label = self._vars.get("serial.line_ending", tk.StringVar()).get()
        self._config.set("serial", "line_ending",
                         next((k for k, v in LINE_ENDINGS.items() if v == eol_label), "CR"))

        # YAPP
        self._config.set("yapp", "transparent", self._yapp_trans_var.get())
        delay = self._vars.get("yapp.block_delay_ms", tk.StringVar()).get().strip()
        self._config.set("yapp", "block_delay_ms", int(delay) if delay.isdigit() else 0)

        # Theme
        selected_theme = self._vars.get("appearance.theme", tk.StringVar()).get()
        if selected_theme:
            self._config.set("appearance", "theme", selected_theme)
            theme.set_theme(selected_theme)

        # Font
        self._config.set("appearance", "font_family",
                         self._vars.get("appearance.font_family", tk.StringVar()).get())
        fsize = self._vars.get("appearance.font_size", tk.StringVar()).get()
        self._config.set("appearance", "font_size", int(fsize) if fsize.isdigit() else 11)

        # Colors
        color_keys = [
            ("appearance", "monitor", "bg_color"), ("appearance", "monitor", "text_color"),
            ("appearance", "monitor", "info_color"), ("appearance", "monitor", "error_color"),
            ("appearance", "channel", "bg_color"), ("appearance", "channel", "rx_color"),
            ("appearance", "channel", "tx_color"), ("appearance", "channel", "system_color"),
            ("appearance", "input", "bg_color"), ("appearance", "input", "text_color"),
            ("appearance", "input", "prompt_color"),
        ]
        for keys in color_keys:
            var = self._vars.get(".".join(keys))
            if var:
                self._config.set(*keys, var.get())

        # Paths
        for key in ["yapp_download", "yapp_upload", "log_directory"]:
            var = self._vars.get(f"paths.{key}")
            if var:
                self._config.set("paths", key, var.get())

        self._config.save()
        if self._on_save:
            self._on_save()
        self.destroy()

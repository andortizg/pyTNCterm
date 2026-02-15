import re
import tkinter as tk
import tkinter.ttk as ttk
from gui import theme


# Regex patterns to detect AX.25 frame types in TNC monitor output.
# Matches lines like: [001: DG2GSV > DB0UAL SABM+]
# or: fm DG2GSV to DB0UAL ctl SABM+
FRAME_PATTERNS = {
    # -- Connection management --
    "sabm": re.compile(r'\bSABM[E+\-]?\b', re.IGNORECASE),
    "disc": re.compile(r'\bDISC[+\-]?\b', re.IGNORECASE),
    "ua":   re.compile(r'\bUA[+\-]?\b', re.IGNORECASE),
    "dm":   re.compile(r'\bDM[+\-]?\b', re.IGNORECASE),
    "frmr": re.compile(r'\bFRMR\b', re.IGNORECASE),
    # -- Information frames --
    "iframe": re.compile(r'\b[IR]\s*S?\d', re.IGNORECASE),
    # -- Supervisory frames --
    "rr":   re.compile(r'\bRR\d', re.IGNORECASE),
    "rnr":  re.compile(r'\bRNR\d', re.IGNORECASE),
    "rej":  re.compile(r'\bREJ\d', re.IGNORECASE),
    "srej": re.compile(r'\bSREJ\d', re.IGNORECASE),
    # -- Unnumbered information --
    "ui":   re.compile(r'\bUI[+\-]?\b', re.IGNORECASE),
}

# Color mapping for each frame type category
FRAME_COLORS = {
    "connect":      "#00e676",  # green - SABM, UA
    "disconnect":   "#ef5350",  # red - DISC, DM, FRMR
    "iframe":       "#e0e0e0",  # white - I-frames
    "supervisory":  "#4fc3f7",  # blue - RR, RNR, REJ, SREJ
    "ui":           "#ffab40",  # orange - UI frames
    "default":      "#90a4ae",  # grey - unrecognized
}


def classify_frame(line):
    """
    Classifies a monitor line by AX.25 frame type.

    Args:
        line: str - a single line of monitor output

    Returns: str - tag name: "connect", "disconnect", "iframe",
                   "supervisory", "ui", or "default"
    """
    if FRAME_PATTERNS["sabm"].search(line) or FRAME_PATTERNS["ua"].search(line):
        return "connect"
    if (FRAME_PATTERNS["disc"].search(line) or FRAME_PATTERNS["dm"].search(line)
            or FRAME_PATTERNS["frmr"].search(line)):
        return "disconnect"
    if FRAME_PATTERNS["rnr"].search(line) or FRAME_PATTERNS["rej"].search(line) \
            or FRAME_PATTERNS["srej"].search(line):
        return "supervisory"
    if FRAME_PATTERNS["rr"].search(line):
        return "supervisory"
    if FRAME_PATTERNS["ui"].search(line):
        return "ui"
    if FRAME_PATTERNS["iframe"].search(line):
        return "iframe"
    return "default"


class MonitorPanel(ttk.Frame):
    """
    Scrollable monitor panel with AX.25 frame type coloring and callsign filtering.
    Shows raw traffic from the TNC.

    Args:
        parent: tk widget - parent container
        config: Config - application configuration instance
    """

    def __init__(self, parent, config):
        super().__init__(parent, style="TFrame")
        self._config = config
        self._max_lines = 500
        # _filter_call: str - if set, only show lines containing this callsign
        self._filter_call = ""
        # _line_buffer: str - partial line buffer for incoming data
        self._line_buffer = ""
        self._build_ui()

    def _build_ui(self):
        """Builds the monitor panel: header with filter + scrollable text widget."""
        # Header bar with title and filter
        header = tk.Frame(self, bg=theme.get("toolbar_bg"), height=28)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        self._header = header

        self._title_label = tk.Label(
            header, text="  ◆  MONITOR", font=("Segoe UI", 9, "bold"),
            bg=theme.get("toolbar_bg"), fg=theme.get("accent_cyan"), anchor="w"
        )
        self._title_label.pack(side=tk.LEFT, padx=4)

        # Filter entry
        self._filter_label = tk.Label(
            header, text="Filter:", font=("Segoe UI", 8),
            bg=theme.get("toolbar_bg"), fg=theme.get("text_secondary")
        )
        self._filter_label.pack(side=tk.RIGHT, padx=(0, 6))

        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", self._on_filter_change)
        self._filter_entry = tk.Entry(
            header, textvariable=self._filter_var, width=12,
            bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
            font=("Consolas", 9), borderwidth=1, highlightthickness=0,
            insertbackground=theme.get("accent_secondary"),
        )
        self._filter_entry.pack(side=tk.RIGHT, padx=(0, 4), pady=3)

        self._filter_info = tk.Label(
            header, text="Callsign:", font=("Segoe UI", 8),
            bg=theme.get("toolbar_bg"), fg=theme.get("text_dim")
        )
        self._filter_info.pack(side=tk.RIGHT, padx=(0, 2))

        # Text area
        text_frame = tk.Frame(self, bg=theme.get("border_color"), bd=1, relief="flat")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=(1, 1), pady=(0, 1))

        self._scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                         style="Vertical.TScrollbar")
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        bg = self._config.get("appearance", "monitor", "bg_color",
                              default=theme.get("monitor_bg"))
        fg = self._config.get("appearance", "monitor", "text_color",
                              default=theme.get("monitor_fg"))
        font_family = self._config.get("appearance", "font_family", default="Consolas")
        font_size = self._config.get("appearance", "font_size", default=11)

        self._text = tk.Text(
            text_frame, bg=bg, fg=fg, font=(font_family, font_size),
            wrap=tk.WORD, state=tk.DISABLED,
            yscrollcommand=self._scrollbar.set,
            borderwidth=0, highlightthickness=0, padx=8, pady=4,
            insertbackground=theme.get("accent_secondary"),
            selectbackground=theme.get("bg_highlight"), selectforeground="#ffffff",
        )
        self._text.pack(fill=tk.BOTH, expand=True)
        self._scrollbar.config(command=self._text.yview)

        # Configure tags for frame types
        self._configure_tags()

    def _configure_tags(self):
        """Sets up text tags for each frame type and for info/error."""
        self._text.tag_configure("connect", foreground=FRAME_COLORS["connect"])
        self._text.tag_configure("disconnect", foreground=FRAME_COLORS["disconnect"])
        self._text.tag_configure("iframe", foreground=FRAME_COLORS["iframe"])
        self._text.tag_configure("supervisory", foreground=FRAME_COLORS["supervisory"])
        self._text.tag_configure("ui", foreground=FRAME_COLORS["ui"])
        self._text.tag_configure("default", foreground=FRAME_COLORS["default"])
        # Legacy tags for system messages
        info_color = self._config.get("appearance", "monitor", "info_color",
                                      default=theme.get("monitor_info"))
        error_color = self._config.get("appearance", "monitor", "error_color",
                                       default=theme.get("monitor_error"))
        self._text.tag_configure("info", foreground=info_color)
        self._text.tag_configure("error", foreground=error_color)

    def _on_filter_change(self, *args):
        """
        Called when the filter entry changes. Updates the active filter callsign.
        """
        self._filter_call = self._filter_var.get().strip().upper()

    def append(self, text, tag=None):
        """
        Appends text to the monitor panel. If no explicit tag is given,
        text is split into lines and each line is auto-classified by frame type.
        Lines not matching the callsign filter are hidden.

        Args:
            text: str - text to append
            tag: str or None - explicit tag ("info", "error") overrides auto-classification
        """
        if tag:
            # Explicit tag (system messages) - always show
            self._insert_text(text, tag)
            return

        # Buffer partial lines and process complete lines
        self._line_buffer += text
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            full_line = line + "\n"

            # Apply callsign filter
            if self._filter_call and self._filter_call not in full_line.upper():
                continue

            # Auto-classify and insert
            frame_tag = classify_frame(full_line)
            self._insert_text(full_line, frame_tag)

    def _insert_text(self, text, tag):
        """
        Inserts text into the text widget with the given tag, trimming excess lines.

        Args:
            text: str - text to insert
            tag: str - tag name for coloring
        """
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, text, tag)

        line_count = int(self._text.index("end-1c").split(".")[0])
        if line_count > self._max_lines:
            self._text.delete("1.0", f"{line_count - self._max_lines}.0")

        self._text.see(tk.END)
        self._text.config(state=tk.DISABLED)

    def clear(self):
        """Clears all text from the monitor panel."""
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)
        self._line_buffer = ""

    def update_appearance(self):
        """Reloads colors and font from current config and theme."""
        bg = self._config.get("appearance", "monitor", "bg_color",
                              default=theme.get("monitor_bg"))
        fg = self._config.get("appearance", "monitor", "text_color",
                              default=theme.get("monitor_fg"))
        font_family = self._config.get("appearance", "font_family", default="Consolas")
        font_size = self._config.get("appearance", "font_size", default=11)
        self._text.config(bg=bg, fg=fg, font=(font_family, font_size))
        self._configure_tags()

        # Update header
        self._header.config(bg=theme.get("toolbar_bg"))
        self._title_label.config(bg=theme.get("toolbar_bg"), fg=theme.get("accent_cyan"))
        self._filter_label.config(bg=theme.get("toolbar_bg"), fg=theme.get("text_secondary"))
        self._filter_info.config(bg=theme.get("toolbar_bg"), fg=theme.get("text_dim"))
        self._filter_entry.config(bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
                                  insertbackground=theme.get("accent_secondary"))

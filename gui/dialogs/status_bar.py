import tkinter as tk
import tkinter.ttk as ttk
from gui import theme


class StatusBar(ttk.Frame):
    """
    Bottom status bar: connection state, serial port info, mode, TX/RX counters.

    Args:
        parent: tk widget - parent container
    """

    def __init__(self, parent):
        super().__init__(parent, style="Status.TFrame")
        self._build_ui()

    def _build_ui(self):
        """Builds the status bar with indicator, port info, mode, and counters."""
        self._bar = tk.Frame(self, bg=theme.get("status_bg"), height=28)
        self._bar.pack(fill=tk.X)
        self._bar.pack_propagate(False)

        self._indicator = tk.Label(
            self._bar, text="  ●", font=("Segoe UI", 11),
            bg=theme.get("status_bg"), fg=theme.get("status_disconnected")
        )
        self._indicator.pack(side=tk.LEFT, padx=(6, 2))

        self._status_label = tk.Label(
            self._bar, text="Disconnected", font=("Segoe UI", 9),
            bg=theme.get("status_bg"), fg=theme.get("status_fg")
        )
        self._status_label.pack(side=tk.LEFT, padx=(0, 12))

        self._add_sep()

        self._port_label = tk.Label(
            self._bar, text="No port", font=("Consolas", 9),
            bg=theme.get("status_bg"), fg=theme.get("text_dim")
        )
        self._port_label.pack(side=tk.LEFT, padx=8)

        self._add_sep()

        self._tnc_label = tk.Label(
            self._bar, text="TNC: ---", font=("Segoe UI", 9),
            bg=theme.get("status_bg"), fg=theme.get("accent_primary")
        )
        self._tnc_label.pack(side=tk.LEFT, padx=8)

        self._add_sep()

        self._mode_label = tk.Label(
            self._bar, text="Mode: ---", font=("Segoe UI", 9),
            bg=theme.get("status_bg"), fg=theme.get("accent_warning")
        )
        self._mode_label.pack(side=tk.LEFT, padx=8)

        self._add_sep()

        self._tx_label = tk.Label(
            self._bar, text="TX: 0", font=("Consolas", 9),
            bg=theme.get("status_bg"), fg=theme.get("accent_secondary")
        )
        self._tx_label.pack(side=tk.LEFT, padx=(8, 4))

        self._rx_label = tk.Label(
            self._bar, text="RX: 0", font=("Consolas", 9),
            bg=theme.get("status_bg"), fg=theme.get("accent_cyan")
        )
        self._rx_label.pack(side=tk.LEFT, padx=(4, 8))

        self._call_label = tk.Label(
            self._bar, text="", font=("Consolas", 9, "bold"),
            bg=theme.get("status_bg"), fg=theme.get("accent_orange")
        )
        self._call_label.pack(side=tk.RIGHT, padx=10)

    def _add_sep(self):
        """Adds a vertical separator line."""
        sep = tk.Frame(self._bar, width=1, height=16, bg=theme.get("border_color"))
        sep.pack(side=tk.LEFT, padx=2, pady=6)

    def set_connected(self, port_info=""):
        """
        Updates to connected state.

        Args:
            port_info: str - port and settings string (e.g., "COM3 9600,8N1")
        """
        self._indicator.config(fg=theme.get("status_connected"))
        self._status_label.config(text="Connected", fg=theme.get("status_connected"))
        self._port_label.config(text=port_info, fg=theme.get("text_secondary"))

    def set_disconnected(self):
        """Updates to disconnected state."""
        self._indicator.config(fg=theme.get("status_disconnected"))
        self._status_label.config(text="Disconnected", fg=theme.get("status_fg"))
        self._port_label.config(text="No port", fg=theme.get("text_dim"))

    def update_counters(self, tx_bytes, rx_bytes):
        """
        Updates TX/RX byte counters.

        Args:
            tx_bytes: int - total bytes transmitted
            rx_bytes: int - total bytes received
        """
        self._tx_label.config(text=f"TX: {self._format_bytes(tx_bytes)}")
        self._rx_label.config(text=f"RX: {self._format_bytes(rx_bytes)}")

    def set_tnc(self, tnc_name):
        """
        Updates the displayed TNC model.

        Args:
            tnc_name: str - TNC model name (e.g., "KAM+", "PK-232")
        """
        # Shorten long names for status bar display
        short = tnc_name.replace("Generic / TNC-2 Compatible", "TNC-2") \
                        .replace("Kantronics ", "").replace("AEA / Timewave ", "") \
                        .replace("AEA ", "").replace("SCS ", "").split(" / ")[0]
        self._tnc_label.config(text=f"TNC: {short}" if short else "TNC: ---")

    def set_mode(self, mode_name):
        """
        Updates the displayed operating mode.

        Args:
            mode_name: str - mode name (e.g., "PACKET", "CW")
        """
        self._mode_label.config(text=f"Mode: {mode_name}")

    def set_callsign(self, callsign):
        """
        Displays the station callsign.

        Args:
            callsign: str - station callsign
        """
        self._call_label.config(text=callsign.upper() if callsign else "")

    def update_appearance(self):
        """Reloads all colors from current theme."""
        bg = theme.get("status_bg")
        self._bar.config(bg=bg)
        for w in self._bar.winfo_children():
            try:
                w.config(bg=bg)
            except Exception:
                pass
        self._indicator.config(bg=bg)
        self._status_label.config(bg=bg, fg=theme.get("status_fg"))
        self._port_label.config(bg=bg)
        self._tnc_label.config(bg=bg, fg=theme.get("accent_primary"))
        self._mode_label.config(bg=bg, fg=theme.get("accent_warning"))
        self._tx_label.config(bg=bg, fg=theme.get("accent_secondary"))
        self._rx_label.config(bg=bg, fg=theme.get("accent_cyan"))
        self._call_label.config(bg=bg, fg=theme.get("accent_orange"))

    @staticmethod
    def _format_bytes(n):
        """
        Formats a byte count into human-readable form.

        Args:
            n: int - byte count

        Returns: str - formatted string (e.g., "1.2K", "3.4M")
        """
        if n < 1024:
            return str(n)
        elif n < 1024 * 1024:
            return f"{n / 1024:.1f}K"
        else:
            return f"{n / (1024 * 1024):.1f}M"

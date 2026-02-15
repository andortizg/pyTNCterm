import tkinter as tk
from gui import theme

VERSION = "1.0.0"
AUTHOR = "Andrés Ortiz"
CALLSIGN = "EA7HQL"
LICENSE = "MIT License"
YEAR = "2025"


class AboutDialog(tk.Toplevel):
    """
    About dialog showing application name, version, author, and license.

    Args:
        parent: tk widget - parent window
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("About pyTNCterm")
        self.geometry("420x400")
        self.resizable(False, False)
        self.configure(bg=theme.get("dialog_bg"))
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._center()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        main = tk.Frame(self, bg=theme.get("dialog_bg"))
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        logo_frame = tk.Frame(main, bg=theme.get("bg_light"), bd=0)
        logo_frame.pack(fill=tk.X, pady=(0, 16))
        tk.Label(logo_frame, text="📡", font=("Segoe UI", 36),
                 bg=theme.get("bg_light"), fg=theme.get("accent_primary")).pack(pady=(16, 4))
        tk.Label(logo_frame, text="pyTNCterm", font=("Segoe UI", 20, "bold"),
                 bg=theme.get("bg_light"), fg=theme.get("accent_primary")).pack()
        tk.Label(logo_frame, text=f"Version {VERSION}", font=("Segoe UI", 10),
                 bg=theme.get("bg_light"), fg=theme.get("text_secondary")).pack(pady=(0, 12))

        info = tk.Frame(main, bg=theme.get("dialog_bg"))
        info.pack(fill=tk.X, pady=4)
        for label, value, color in [
            ("Author:", f"{AUTHOR}, {CALLSIGN}", theme.get("text_primary")),
            ("License:", LICENSE, theme.get("text_primary")),
            ("", f"Copyright © {YEAR} {AUTHOR}", theme.get("text_secondary")),
        ]:
            row = tk.Frame(info, bg=theme.get("dialog_bg"))
            row.pack(fill=tk.X, pady=3)
            if label:
                tk.Label(row, text=label, font=("Segoe UI", 10, "bold"),
                         bg=theme.get("dialog_bg"), fg=theme.get("accent_cyan"),
                         width=10, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(row, text=value, font=("Segoe UI", 10),
                     bg=theme.get("dialog_bg"), fg=color, anchor="w").pack(side=tk.LEFT)

        tk.Label(
            main,
            text="A portable multi-mode TNC terminal program\n"
                 "for amateur radio packet, CW, RTTY, AMTOR,\n"
                 "PACTOR and other digital modes.\n\n"
                 "Supports YAPP file transfers and works with\n"
                 "Kantronics, AEA, MFJ, SCS and other TNCs.",
            font=("Segoe UI", 9), bg=theme.get("dialog_bg"),
            fg=theme.get("text_secondary"), justify=tk.CENTER
        ).pack(pady=(16, 0))

        tk.Button(
            main, text="Close", font=("Segoe UI", 10),
            bg=theme.get("button_bg"), fg=theme.get("button_fg"),
            activebackground=theme.get("button_active"),
            bd=0, padx=20, pady=6, cursor="hand2", command=self.destroy
        ).pack(pady=(16, 0))

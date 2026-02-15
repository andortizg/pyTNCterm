import tkinter as tk
import tkinter.ttk as ttk
from gui import theme


class Toolbar(ttk.Frame):
    """
    Toolbar with quick-access buttons.

    Args:
        parent: tk widget - parent container
        callbacks: dict - action name -> callable
    """

    def __init__(self, parent, callbacks=None):
        super().__init__(parent, style="Toolbar.TFrame")
        self._callbacks = callbacks or {}
        self._buttons = {}
        self._build_ui()

    def _build_ui(self):
        """Builds the toolbar with styled buttons."""
        self._bar = tk.Frame(self, bg=theme.get("toolbar_bg"), height=38)
        self._bar.pack(fill=tk.X)
        self._bar.pack_propagate(False)

        tk.Frame(self._bar, width=6, bg=theme.get("toolbar_bg")).pack(side=tk.LEFT)

        self._add_button("connect", "⚡ Connect", "connect")
        self._add_button("disconnect", "✕ Disconnect", "disconnect")
        self._add_separator()
        self._add_button("clear_monitor", "🗑 Clear Monitor", "clear_monitor")
        self._add_button("clear_channel", "🗑 Clear Channel", "clear_channel")

        self.set_connected(False)

    def _add_button(self, name, text, callback_key):
        """
        Creates a toolbar button.

        Args:
            name: str - internal button name
            text: str - button label
            callback_key: str - key in self._callbacks
        """
        btn = tk.Button(
            self._bar, text=text, font=("Segoe UI", 9),
            bg=theme.get("toolbar_btn_bg"), fg=theme.get("toolbar_btn_fg"),
            activebackground=theme.get("toolbar_btn_active"), activeforeground="#ffffff",
            bd=0, padx=12, pady=4, cursor="hand2",
            highlightthickness=0, relief="flat",
            command=self._callbacks.get(callback_key, lambda: None)
        )
        btn.pack(side=tk.LEFT, padx=2, pady=4)
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg=theme.get("toolbar_btn_active")))
        btn.bind("<Leave>", lambda e, b=btn: b.config(
            bg=theme.get("toolbar_btn_bg") if b["state"] != "disabled" else theme.get("bg_dark")))
        self._buttons[name] = btn

    def _add_separator(self):
        """Adds a vertical separator."""
        sep = tk.Frame(self._bar, width=1, height=22, bg=theme.get("border_color"))
        sep.pack(side=tk.LEFT, padx=6, pady=8)

    def set_connected(self, connected):
        """
        Updates button states based on connection status.

        Args:
            connected: bool
        """
        if connected:
            self._buttons["connect"].config(state="disabled",
                                            bg=theme.get("bg_dark"), fg=theme.get("text_dim"))
            self._buttons["disconnect"].config(state="normal",
                                               bg=theme.get("toolbar_btn_bg"),
                                               fg=theme.get("toolbar_btn_fg"))
        else:
            self._buttons["connect"].config(state="normal",
                                            bg=theme.get("toolbar_btn_bg"),
                                            fg=theme.get("toolbar_btn_fg"))
            self._buttons["disconnect"].config(state="disabled",
                                               bg=theme.get("bg_dark"), fg=theme.get("text_dim"))

    def update_appearance(self):
        """Reloads all colors from current theme."""
        self._bar.config(bg=theme.get("toolbar_bg"))
        for name, btn in self._buttons.items():
            if btn["state"] != "disabled":
                btn.config(bg=theme.get("toolbar_btn_bg"), fg=theme.get("toolbar_btn_fg"),
                           activebackground=theme.get("toolbar_btn_active"))
            else:
                btn.config(bg=theme.get("bg_dark"), fg=theme.get("text_dim"))
        # Update spacers and separators
        for w in self._bar.winfo_children():
            if isinstance(w, tk.Frame):
                w.config(bg=theme.get("toolbar_bg") if w.winfo_width() < 10
                         else theme.get("border_color"))

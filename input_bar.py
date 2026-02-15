import tkinter as tk
import tkinter.ttk as ttk
from gui import theme


class InputBar(ttk.Frame):
    """
    Command input line with prompt, text entry, and history (up/down arrows).

    Args:
        parent: tk widget - parent container
        config: Config - application configuration instance
        on_send: callable(str) - callback when user presses Enter
    """

    def __init__(self, parent, config, on_send=None):
        super().__init__(parent, style="TFrame")
        self._config = config
        self._on_send = on_send
        self._history = []
        self._history_idx = -1
        self._current_input = ""
        self._build_ui()

    def _get_colors(self):
        """Returns: dict with input bar color values from config, falling back to theme."""
        return {
            "bg": self._config.get("appearance", "input", "bg_color",
                                   default=theme.get("input_bg")),
            "fg": self._config.get("appearance", "input", "text_color",
                                   default=theme.get("input_fg")),
            "prompt": self._config.get("appearance", "input", "prompt_color",
                                       default=theme.get("input_prompt")),
            "font": self._config.get("appearance", "font_family", default="Consolas"),
            "size": self._config.get("appearance", "font_size", default=11),
        }

    def _build_ui(self):
        """Builds the input bar: prompt label + entry widget."""
        c = self._get_colors()

        input_frame = tk.Frame(self, bg=theme.get("border_accent"), bd=1, relief="flat")
        input_frame.pack(fill=tk.X, padx=2, pady=(2, 2))

        self._inner = tk.Frame(input_frame, bg=c["bg"])
        self._inner.pack(fill=tk.X, padx=1, pady=1)

        self._prompt_label = tk.Label(
            self._inner, text=" => ", bg=c["bg"], fg=c["prompt"],
            font=(c["font"], c["size"], "bold")
        )
        self._prompt_label.pack(side=tk.LEFT)

        self._entry = tk.Entry(
            self._inner, bg=c["bg"], fg=c["fg"],
            font=(c["font"], c["size"]),
            insertbackground=c["fg"], borderwidth=0, highlightthickness=0,
            selectbackground=theme.get("bg_highlight"), selectforeground="#ffffff",
        )
        self._entry.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 4), ipady=4)

        self._entry.bind("<Return>", self._handle_enter)
        self._entry.bind("<Up>", self._handle_up)
        self._entry.bind("<Down>", self._handle_down)

    def _handle_enter(self, event):
        """Sends text via callback and adds to history."""
        text = self._entry.get()
        if text.strip():
            self._history.append(text)
        self._history_idx = -1
        self._current_input = ""
        self._entry.delete(0, tk.END)
        if self._on_send and text:
            self._on_send(text)

    def _handle_up(self, event):
        """Navigates backward in command history."""
        if not self._history:
            return "break"
        if self._history_idx == -1:
            self._current_input = self._entry.get()
            self._history_idx = len(self._history) - 1
        elif self._history_idx > 0:
            self._history_idx -= 1
        self._entry.delete(0, tk.END)
        self._entry.insert(0, self._history[self._history_idx])
        return "break"

    def _handle_down(self, event):
        """Navigates forward in command history."""
        if self._history_idx == -1:
            return "break"
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._history[self._history_idx])
        else:
            self._history_idx = -1
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._current_input)
        return "break"

    def focus_input(self):
        """Sets keyboard focus to the input entry."""
        self._entry.focus_set()

    def update_appearance(self):
        """Reloads colors and font from current config and theme."""
        c = self._get_colors()
        self._entry.config(bg=c["bg"], fg=c["fg"], font=(c["font"], c["size"]),
                           insertbackground=c["fg"])
        self._prompt_label.config(bg=c["bg"], fg=c["prompt"],
                                  font=(c["font"], c["size"], "bold"))
        self._inner.config(bg=c["bg"])

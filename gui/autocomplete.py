import tkinter as tk
from gui import theme
from core import tnc_commands


class AutocompleteTooltip:
    """
    Floating autocomplete popup that appears below the TX cursor when the user
    types text matching known TNC commands. Shows command name, syntax, and
    short help. Tab inserts the selected command, Escape closes.

    Args:
        tx_text: tk.Text - the TX text widget to attach to
        model_name: str - current TNC model name
        on_insert: callable(str) or None - called with syntax string to insert
    """

    MAX_RESULTS = 8

    def __init__(self, tx_text, model_name, on_insert=None):
        self._tx = tx_text
        self._model = model_name
        self._on_insert = on_insert
        self._popup = None
        self._listbox = None
        self._help_label = None
        self._results = []  # list of (category, cmd_dict)
        self._enabled = True
        self._after_id = None

        # Bind events
        self._tx.bind("<KeyRelease>", self._on_key_release, add="+")
        self._tx.bind("<Escape>", self._on_escape, add="+")
        self._tx.bind("<Tab>", self._on_tab, add="+")
        self._tx.bind("<FocusOut>", lambda e: self.hide(), add="+")

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        """
        Enable or disable autocomplete.

        Args:
            value: bool
        """
        self._enabled = value
        if not value:
            self.hide()

    def set_model(self, model_name):
        """
        Updates the TNC model for autocomplete lookups.

        Args:
            model_name: str
        """
        self._model = model_name

    def _on_key_release(self, event):
        """
        Called on every key release in TX. Triggers autocomplete lookup
        with a small delay to avoid excessive lookups.

        Args:
            event: tk.Event
        """
        if not self._enabled:
            return

        # Ignore modifier keys and navigation
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                            "Alt_L", "Alt_R", "Caps_Lock", "Up", "Down",
                            "Left", "Right", "Home", "End", "Tab", "Escape",
                            "Return", "BackSpace"):
            if event.keysym == "BackSpace":
                # Re-trigger on backspace
                pass
            else:
                return

        # Debounce: cancel previous scheduled lookup
        if self._after_id:
            self._tx.after_cancel(self._after_id)
        self._after_id = self._tx.after(150, self._do_lookup)

    def _do_lookup(self):
        """Performs the actual command lookup based on current TX input."""
        self._after_id = None

        # Get current input line text (from input_mark to cursor)
        try:
            text = self._tx.get("input_start", "insert").strip()
        except Exception:
            text = self._tx.get("1.0", "insert").strip()

        if not text or len(text) < 2:
            self.hide()
            return

        # Get first word (the command)
        first_word = text.split()[0] if text.split() else text

        # Search commands matching the first word
        results = tnc_commands.search_commands(self._model, first_word)

        # Filter to text-type commands only (keys/sequences less useful for autocomplete)
        results = [(cat, cmd) for cat, cmd in results if cmd.get("type") == "text"]

        if not results:
            self.hide()
            return

        # Don't show if exact match and only one result
        if len(results) == 1 and results[0][1].get("cmd", "").upper() == first_word.upper():
            self.hide()
            return

        self._results = results[:self.MAX_RESULTS]
        self._show_popup()

    def _show_popup(self):
        """Creates or updates the floating popup with matching commands."""
        if not self._results:
            self.hide()
            return

        # Calculate position below cursor
        try:
            bbox = self._tx.bbox("insert")
            if not bbox:
                self.hide()
                return
            x, y, w, h = bbox
            abs_x = self._tx.winfo_rootx() + x
            abs_y = self._tx.winfo_rooty() + y + h + 4
        except Exception:
            self.hide()
            return

        if self._popup is None:
            self._create_popup()

        # Update listbox
        self._listbox.delete(0, tk.END)
        for cat, cmd in self._results:
            syntax = cmd.get("syntax", cmd.get("cmd", ""))
            desc = cmd.get("desc", "")
            self._listbox.insert(tk.END, f" {cmd['cmd']:18s} {syntax}")

        self._listbox.selection_set(0)
        self._update_help()

        # Position and show
        popup_w = 420
        popup_h = min(len(self._results) * 20 + 65, 230)
        self._popup.geometry(f"{popup_w}x{popup_h}+{abs_x}+{abs_y}")
        self._popup.deiconify()

    def _create_popup(self):
        """Creates the floating Toplevel popup with listbox and help label."""
        self._popup = tk.Toplevel(self._tx)
        self._popup.wm_overrideredirect(True)
        self._popup.configure(bg=theme.get("border_accent"))

        inner = tk.Frame(self._popup, bg=theme.get("bg_medium"), bd=1)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._listbox = tk.Listbox(
            inner, bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            font=("Consolas", 9),
            selectbackground=theme.get("accent_primary"), selectforeground="#000000",
            borderwidth=0, highlightthickness=0, activestyle="none",
            height=self.MAX_RESULTS,
        )
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=(2, 0))
        self._listbox.bind("<<ListboxSelect>>", lambda e: self._update_help())
        self._listbox.bind("<Double-1>", self._on_double_click)

        sep = tk.Frame(inner, bg=theme.get("border_color"), height=1)
        sep.pack(fill=tk.X, padx=4, pady=2)

        self._help_label = tk.Label(
            inner, text="", font=("Segoe UI", 8),
            bg=theme.get("bg_medium"), fg=theme.get("text_dim"),
            anchor="w", wraplength=400, justify="left",
        )
        self._help_label.pack(fill=tk.X, padx=4, pady=(0, 3))

    def _update_help(self):
        """Updates the help label with the selected command's description."""
        if not self._help_label:
            return
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._results):
            cat, cmd = self._results[sel[0]]
            desc = cmd.get("desc", "")
            default = cmd.get("default", "")
            rng = cmd.get("range", "")
            text = desc
            if default or rng:
                extras = []
                if default:
                    extras.append(f"Default: {default}")
                if rng:
                    extras.append(f"Range: {rng}")
                text += f"  ({', '.join(extras)})"
            text += "  [Tab to insert]"
            self._help_label.config(text=text)

    def _on_tab(self, event):
        """
        Inserts the selected command syntax into TX on Tab press.

        Args:
            event: tk.Event

        Returns: str "break" if popup visible, None otherwise
        """
        if self._popup and self._popup.winfo_viewable() and self._results:
            sel = self._listbox.curselection()
            idx = sel[0] if sel else 0
            if idx < len(self._results):
                cat, cmd = self._results[idx]
                syntax = cmd.get("syntax", cmd.get("cmd", ""))
                if self._on_insert:
                    self._on_insert(syntax)
                self.hide()
                return "break"
        return None

    def _on_escape(self, event):
        """Hides the popup on Escape."""
        if self._popup and self._popup.winfo_viewable():
            self.hide()
            return "break"
        return None

    def _on_double_click(self, event):
        """Inserts on double-click."""
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._results):
            cat, cmd = self._results[sel[0]]
            syntax = cmd.get("syntax", cmd.get("cmd", ""))
            if self._on_insert:
                self._on_insert(syntax)
            self.hide()

    def hide(self):
        """Hides the popup."""
        if self._popup:
            self._popup.withdraw()

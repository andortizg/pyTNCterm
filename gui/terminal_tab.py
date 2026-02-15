import tkinter as tk
import tkinter.ttk as ttk
from gui import theme
from gui.autocomplete import AutocompleteTooltip
from core import tnc_commands


class TerminalTab(ttk.Frame):
    """
    Split terminal panel using PanedWindow: upper pane (RX) shows received data
    and sent commands (read-only), lower pane (TX) is where the user types.
    Sent text remains visible in TX with a '>> ' prefix so the user can scroll
    back through previous commands. The divider is draggable.

    Args:
        parent: tk widget - parent container
        config: Config - application configuration instance
        on_send: callable(str) or None - called with text when Enter is pressed
    """

    def __init__(self, parent, config, on_send=None, on_execute=None):
        super().__init__(parent, style="TFrame")
        self._config = config
        self._on_send = on_send
        # on_execute: callable(dict) or None - called for key/sequence commands
        self._on_execute = on_execute
        # _tnc_model: str - current TNC model name for context menu
        self._tnc_model = config.get("tnc", "model", default="Generic / TNC-2 Compatible")
        # _history: list of str - command history
        self._history = []
        # _history_idx: int - current position in history (-1 = new input)
        self._history_idx = -1
        # _current_input: str - saved input when browsing history
        self._current_input = ""
        # _input_mark: str - tk text mark at the start of the current editable line
        self._input_mark = "input_start"
        self._max_lines_rx = 2000
        self._max_lines_tx = 500
        self._build_ui()
        # Autocomplete tooltip (created after UI so _tx_text exists)
        self._autocomplete = AutocompleteTooltip(
            self._tx_text, self._tnc_model,
            on_insert=self.insert_command
        )
        # Apply saved preference
        ac_enabled = config.get("tnc", "autocomplete", default=True)
        self._autocomplete.enabled = ac_enabled

    def _get_colors(self):
        """
        Returns: dict with color values from config, falling back to theme.
        Keys: bg, rx, tx, sys, font, size, tx_bg, tx_fg, prompt
        """
        return {
            "bg": self._config.get("appearance", "channel", "bg_color",
                                   default=theme.get("channel_bg")),
            "rx": self._config.get("appearance", "channel", "rx_color",
                                   default=theme.get("channel_rx")),
            "tx": self._config.get("appearance", "channel", "tx_color",
                                   default=theme.get("channel_tx")),
            "sys": self._config.get("appearance", "channel", "system_color",
                                    default=theme.get("channel_system")),
            "font": self._config.get("appearance", "font_family", default="Consolas"),
            "size": self._config.get("appearance", "font_size", default=11),
            "tx_bg": self._config.get("appearance", "input", "bg_color",
                                      default=theme.get("input_bg")),
            "tx_fg": self._config.get("appearance", "input", "text_color",
                                      default=theme.get("input_fg")),
            "prompt": self._config.get("appearance", "input", "prompt_color",
                                       default=theme.get("input_prompt")),
        }

    def _build_ui(self):
        """Builds the split terminal using PanedWindow with RX (top) and TX (bottom)."""
        c = self._get_colors()

        # PanedWindow for proper split resizing
        self._paned = tk.PanedWindow(
            self, orient=tk.VERTICAL,
            bg=theme.get("border_accent"),
            sashwidth=5, sashrelief="flat",
            opaqueresize=True,
        )
        self._paned.pack(fill=tk.BOTH, expand=True)

        # ── RX pane (upper, read-only) ──
        rx_container = tk.Frame(self._paned, bg=theme.get("bg_dark"))

        rx_header = tk.Frame(rx_container, bg=theme.get("toolbar_bg"), height=22)
        rx_header.pack(fill=tk.X)
        rx_header.pack_propagate(False)
        self._rx_header = rx_header

        self._rx_label = tk.Label(
            rx_header, text="  ▼  RX", font=("Segoe UI", 8, "bold"),
            bg=theme.get("toolbar_bg"), fg=theme.get("accent_cyan"), anchor="w"
        )
        self._rx_label.pack(side=tk.LEFT, padx=4)

        rx_frame = tk.Frame(rx_container, bg=theme.get("border_color"), bd=0)
        rx_frame.pack(fill=tk.BOTH, expand=True, padx=1)

        self._rx_scrollbar = ttk.Scrollbar(rx_frame, orient=tk.VERTICAL,
                                            style="Vertical.TScrollbar")
        self._rx_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._rx_text = tk.Text(
            rx_frame, bg=c["bg"], fg=c["rx"], font=(c["font"], c["size"]),
            wrap=tk.WORD, state=tk.DISABLED,
            yscrollcommand=self._rx_scrollbar.set,
            borderwidth=0, highlightthickness=0, padx=8, pady=4,
            insertbackground=theme.get("accent_secondary"),
            selectbackground=theme.get("bg_highlight"), selectforeground="#ffffff",
        )
        self._rx_text.pack(fill=tk.BOTH, expand=True)
        self._rx_scrollbar.config(command=self._rx_text.yview)

        # RX text tags
        self._rx_text.tag_configure("tx", foreground=c["tx"])
        self._rx_text.tag_configure("rx", foreground=c["rx"])
        self._rx_text.tag_configure("system", foreground=c["sys"])
        self._rx_text.tag_configure("error", foreground=theme.get("accent_error"))

        self._rx_container = rx_container

        # ── TX pane (lower, editable with history) ──
        tx_container = tk.Frame(self._paned, bg=theme.get("bg_dark"))

        tx_header = tk.Frame(tx_container, bg=theme.get("toolbar_bg"), height=22)
        tx_header.pack(fill=tk.X)
        tx_header.pack_propagate(False)
        self._tx_header = tx_header

        self._tx_label = tk.Label(
            tx_header, text="  ▲  TX  (Enter to send)", font=("Segoe UI", 8, "bold"),
            bg=theme.get("toolbar_bg"), fg=theme.get("accent_secondary"), anchor="w"
        )
        self._tx_label.pack(side=tk.LEFT, padx=4)

        tx_frame = tk.Frame(tx_container, bg=theme.get("border_accent"), bd=0)
        tx_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

        self._tx_scrollbar = ttk.Scrollbar(tx_frame, orient=tk.VERTICAL,
                                            style="Vertical.TScrollbar")
        self._tx_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tx_text = tk.Text(
            tx_frame, bg=c["tx_bg"], fg=c["tx_fg"],
            font=(c["font"], c["size"]),
            wrap=tk.WORD,
            yscrollcommand=self._tx_scrollbar.set,
            borderwidth=0, highlightthickness=0, padx=8, pady=4,
            insertbackground=theme.get("accent_secondary"),
            selectbackground=theme.get("bg_highlight"), selectforeground="#ffffff",
            undo=False,
        )
        self._tx_text.pack(fill=tk.BOTH, expand=True)
        self._tx_scrollbar.config(command=self._tx_text.yview)

        self._tx_container = tx_container

        # TX text tags
        self._tx_text.tag_configure("sent", foreground=theme.get("text_dim"))
        self._tx_text.tag_configure("sent_prompt", foreground=theme.get("accent_warning"))

        # Mark for start of current editable input
        self._tx_text.mark_set(self._input_mark, "1.0")
        self._tx_text.mark_gravity(self._input_mark, "left")

        # Add panes: RX gets most space, TX starts smaller
        self._paned.add(rx_container, stretch="always")
        self._paned.add(tx_container, stretch="never")

        # Set initial sash position after layout is computed
        self.after(50, self._set_initial_sash)

        # Key bindings on TX
        self._tx_text.bind("<Return>", self._handle_enter)
        self._tx_text.bind("<Up>", self._handle_up)
        self._tx_text.bind("<Down>", self._handle_down)
        self._tx_text.bind("<BackSpace>", self._handle_backspace)
        self._tx_text.bind("<Key>", self._handle_key)
        self._tx_text.bind("<ButtonRelease-1>", self._handle_click)
        # Right-click context menu (Button-3 on Linux/Windows, Button-2 on Mac)
        self._tx_text.bind("<Button-3>", self._show_context_menu)

    def _set_initial_sash(self):
        """
        Sets the initial sash position so TX takes ~25% of the total height.
        Called after the widget is mapped and has a real size.
        """
        self.update_idletasks()
        total = self._paned.winfo_height()
        if total > 100:
            self._paned.sash_place(0, 0, int(total * 0.75))

    def _handle_enter(self, event):
        """
        Sends current input line to TNC. The sent text stays visible in TX
        with a '>>' prefix, and the cursor moves to a new line for next input.

        Args:
            event: tk.Event

        Returns: str "break" to prevent default newline
        """
        # Get text from input_mark to end
        input_text = self._tx_text.get(self._input_mark, "end-1c")

        if input_text.strip():
            self._history.append(input_text)
        self._history_idx = -1
        self._current_input = ""

        # Delete the raw input and replace with formatted sent line
        self._tx_text.delete(self._input_mark, "end-1c")
        self._tx_text.insert(self._input_mark, ">> ", "sent_prompt")
        self._tx_text.insert(tk.END, input_text + "\n", "sent")

        # Trim excess lines
        line_count = int(self._tx_text.index("end-1c").split(".")[0])
        if line_count > self._max_lines_tx:
            excess = line_count - self._max_lines_tx
            self._tx_text.delete("1.0", f"{excess}.0")

        # Update input mark to current end position (new input line)
        self._tx_text.mark_set(self._input_mark, "end-1c")
        self._tx_text.see(tk.END)

        # Send to TNC
        if self._on_send and input_text:
            self._on_send(input_text)

        return "break"

    def _handle_backspace(self, event):
        """
        Prevents backspace from deleting past the input mark (into sent history).

        Args:
            event: tk.Event

        Returns: str "break" if at input_mark, None otherwise
        """
        if self._tx_text.compare("insert", "<=", self._input_mark):
            return "break"
        return None

    def _handle_key(self, event):
        """
        Ensures typing only happens at or after input_mark (the editable area).
        If cursor is in the sent history area, it is moved to the end.

        Args:
            event: tk.Event

        Returns: str "break" if non-printable key in history area
        """
        # Allow navigation and modifier keys everywhere
        if event.keysym in ("Left", "Right", "Home", "End", "Delete",
                            "Shift_L", "Shift_R", "Control_L", "Control_R",
                            "Alt_L", "Alt_R", "Caps_Lock", "Tab",
                            "Prior", "Next"):
            return None
        if event.state & 0x4:  # Control key held (Ctrl+C, Ctrl+V, etc.)
            return None

        # If cursor is in the history area, move to end
        if self._tx_text.compare("insert", "<", self._input_mark):
            self._tx_text.mark_set("insert", "end")
        return None

    def _handle_click(self, event):
        """
        After mouse click, ensures cursor doesn't land in the read-only history.
        Cursor is moved to end if it lands before input_mark.

        Args:
            event: tk.Event
        """
        # Allow clicking in history for selection/copy, but move insert cursor
        if self._tx_text.compare("insert", "<", self._input_mark):
            self._tx_text.mark_set("insert", "end")

    def _handle_up(self, event):
        """
        Navigates backward in command history, replacing current input line.

        Args:
            event: tk.Event

        Returns: str "break"
        """
        if not self._history:
            return "break"
        if self._history_idx == -1:
            self._current_input = self._tx_text.get(self._input_mark, "end-1c")
            self._history_idx = len(self._history) - 1
        elif self._history_idx > 0:
            self._history_idx -= 1
        else:
            return "break"

        self._replace_input(self._history[self._history_idx])
        return "break"

    def _handle_down(self, event):
        """
        Navigates forward in command history, replacing current input line.

        Args:
            event: tk.Event

        Returns: str "break"
        """
        if self._history_idx == -1:
            return "break"
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._replace_input(self._history[self._history_idx])
        else:
            self._history_idx = -1
            self._replace_input(self._current_input)
        return "break"

    def _replace_input(self, text):
        """
        Replaces only the current input line (after input_mark) with new text.

        Args:
            text: str - replacement text
        """
        self._tx_text.delete(self._input_mark, "end-1c")
        self._tx_text.insert(self._input_mark, text)
        self._tx_text.mark_set("insert", "end")
        self._tx_text.see(tk.END)

    def append(self, text, tag=None):
        """
        Appends text to the RX zone (upper panel).

        Args:
            text: str - text to append
            tag: str or None - optional tag ("rx", "tx", "system", "error")
        """
        self._rx_text.config(state=tk.NORMAL)
        if tag:
            self._rx_text.insert(tk.END, text, tag)
        else:
            self._rx_text.insert(tk.END, text)

        # Trim excess lines
        line_count = int(self._rx_text.index("end-1c").split(".")[0])
        if line_count > self._max_lines_rx:
            self._rx_text.delete("1.0", f"{line_count - self._max_lines_rx}.0")

        self._rx_text.see(tk.END)
        self._rx_text.config(state=tk.DISABLED)

    def append_tx(self, text):
        """
        Appends transmitted text to the RX zone (displayed with TX color, prefixed =>).

        Args:
            text: str - the command that was sent
        """
        self.append(f"=> {text}\n", tag="tx")

    def clear(self):
        """Clears the RX zone."""
        self._rx_text.config(state=tk.NORMAL)
        self._rx_text.delete("1.0", tk.END)
        self._rx_text.config(state=tk.DISABLED)

    def clear_tx(self):
        """Clears the TX zone history and resets input mark."""
        self._tx_text.delete("1.0", tk.END)
        self._tx_text.mark_set(self._input_mark, "1.0")

    def focus_terminal(self):
        """Sets keyboard focus to the TX zone."""
        self._tx_text.focus_set()
        self._tx_text.mark_set("insert", "end")

    def update_appearance(self):
        """Reloads colors and font from current config and theme."""
        c = self._get_colors()

        # RX zone
        self._rx_text.config(bg=c["bg"], fg=c["rx"], font=(c["font"], c["size"]),
                             insertbackground=theme.get("accent_secondary"),
                             selectbackground=theme.get("bg_highlight"))
        self._rx_text.tag_configure("tx", foreground=c["tx"])
        self._rx_text.tag_configure("rx", foreground=c["rx"])
        self._rx_text.tag_configure("system", foreground=c["sys"])
        self._rx_text.tag_configure("error", foreground=theme.get("accent_error"))

        # TX zone
        self._tx_text.config(bg=c["tx_bg"], fg=c["tx_fg"], font=(c["font"], c["size"]),
                             insertbackground=theme.get("accent_secondary"),
                             selectbackground=theme.get("bg_highlight"))
        self._tx_text.tag_configure("sent", foreground=theme.get("text_dim"))
        self._tx_text.tag_configure("sent_prompt", foreground=theme.get("accent_warning"))

        # Containers and headers
        self._paned.config(bg=theme.get("border_accent"))
        self._rx_container.config(bg=theme.get("bg_dark"))
        self._tx_container.config(bg=theme.get("bg_dark"))
        self._rx_header.config(bg=theme.get("toolbar_bg"))
        self._rx_label.config(bg=theme.get("toolbar_bg"), fg=theme.get("accent_cyan"))
        self._tx_header.config(bg=theme.get("toolbar_bg"))
        self._tx_label.config(bg=theme.get("toolbar_bg"), fg=theme.get("accent_secondary"))

    # -- TNC command context menu --

    def set_tnc_model(self, model_name):
        """
        Updates the TNC model used for the right-click context menu and autocomplete.

        Args:
            model_name: str - TNC model name (e.g., "Kantronics KAM / KAM+")
        """
        self._tnc_model = model_name
        self._autocomplete.set_model(model_name)

    def set_autocomplete_enabled(self, enabled):
        """
        Enables or disables the autocomplete tooltip in TX.

        Args:
            enabled: bool
        """
        self._autocomplete.enabled = enabled

    def _show_context_menu(self, event):
        """
        Builds and shows the right-click context menu with TNC commands
        organized by category. Menu content depends on the selected TNC model.

        Args:
            event: tk.Event - mouse event with x_root, y_root coordinates
        """
        menu_opts = dict(
            bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            activebackground=theme.get("accent_primary"), activeforeground="#000000",
            font=("Segoe UI", 9), borderwidth=0, relief="flat"
        )

        menu = tk.Menu(self._tx_text, tearoff=0, **menu_opts)

        # Standard edit commands
        menu.add_command(label="Cut", command=self._ctx_cut, accelerator="Ctrl+X")
        menu.add_command(label="Copy", command=self._ctx_copy, accelerator="Ctrl+C")
        menu.add_command(label="Paste", command=self._ctx_paste, accelerator="Ctrl+V")
        menu.add_separator()

        # TNC commands by category
        categories = tnc_commands.get_categories(self._tnc_model)
        for cat in categories:
            commands = tnc_commands.get_commands(self._tnc_model, cat)
            if not commands:
                continue

            sub = tk.Menu(menu, tearoff=0, **menu_opts)
            for cmd in commands:
                cmd_type = cmd.get("type", "text")
                type_icon = {"text": "⌨", "key": "⚡", "sequence": "🔗"}.get(cmd_type, "⌨")
                label = f"{type_icon}  {cmd['cmd']}"
                # Add syntax/key hint
                hint = cmd.get("syntax", cmd.get("key", ""))
                if hint:
                    label += f"   [{hint}]"

                # Capture cmd in closure
                sub.add_command(
                    label=label,
                    command=lambda c=cmd: self._execute_command(c)
                )
            menu.add_cascade(label=f"  {cat}", menu=sub)

        menu.add_separator()
        menu.add_command(label="🔍 Search command...  F2",
                         command=self._request_search)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _ctx_cut(self):
        """Cut selected text in TX."""
        try:
            self._tx_text.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def _ctx_copy(self):
        """Copy selected text in TX."""
        try:
            self._tx_text.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def _ctx_paste(self):
        """Paste from clipboard into TX."""
        try:
            self._tx_text.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    def _request_search(self):
        """Triggers F2 search popup via the on_execute callback."""
        if self._on_execute:
            self._on_execute({"type": "__search__"})

    def _execute_command(self, cmd):
        """
        Executes a TNC command based on its type:
        - text: inserts syntax into TX input line for editing
        - key: sends directly via on_execute callback
        - sequence: sends via on_execute callback

        Args:
            cmd: dict - command definition with keys: type, cmd, syntax/key/steps
        """
        cmd_type = cmd.get("type", "text")

        if cmd_type == "text":
            self.insert_command(cmd.get("syntax", cmd.get("cmd", "")))
        elif cmd_type in ("key", "sequence"):
            if self._on_execute:
                self._on_execute(cmd)

    def insert_command(self, text):
        """
        Inserts a text command into the TX input line (replacing current input).
        The user can then edit parameters before pressing Enter.

        Args:
            text: str - command syntax to insert (e.g., "PACLEN {n}")
        """
        self._tx_text.delete(self._input_mark, "end-1c")
        self._tx_text.insert(self._input_mark, text)
        self._tx_text.mark_set("insert", "end")
        self._tx_text.see(tk.END)
        self._tx_text.focus_set()

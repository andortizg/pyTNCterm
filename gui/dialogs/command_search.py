import tkinter as tk
import tkinter.ttk as ttk
from gui import theme
from core import tnc_commands


class CommandSearchPopup(tk.Toplevel):
    """
    Quick command search popup (F2). Type to filter, arrow keys to navigate,
    Enter to insert selected command into TX.

    Args:
        parent: tk widget - parent window
        model_name: str - TNC model name
        on_insert: callable(dict) or None - called with command dict on selection
    """

    def __init__(self, parent, model_name, on_insert=None):
        super().__init__(parent)
        self._model = model_name
        self._on_insert = on_insert
        self._results = []  # list of (category, cmd_dict)

        self.title("Quick Command Search")
        self.geometry("520x480")
        self.configure(bg=theme.get("dialog_bg"))
        self.transient(parent)
        self.grab_set()
        self.overrideredirect(False)
        self._build_ui()
        self._center()
        self._search_entry.focus_set()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Builds the search popup: entry + results listbox."""
        main = tk.Frame(self, bg=theme.get("dialog_bg"))
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Search entry
        entry_frame = tk.Frame(main, bg=theme.get("dialog_bg"))
        entry_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(entry_frame, text="🔍", font=("Segoe UI", 12),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(side=tk.LEFT, padx=(0, 6))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        self._search_entry = tk.Entry(
            entry_frame, textvariable=self._search_var,
            bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
            font=("Consolas", 12), borderwidth=1,
            insertbackground=theme.get("accent_secondary"),
        )
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._search_entry.bind("<Return>", self._on_enter)
        self._search_entry.bind("<Escape>", lambda e: self.destroy())
        self._search_entry.bind("<Up>", self._on_arrow_up)
        self._search_entry.bind("<Down>", self._on_arrow_down)

        # Results listbox
        list_frame = tk.Frame(main, bg=theme.get("border_color"), bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self._listbox = tk.Listbox(
            list_frame, bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            font=("Consolas", 10),
            selectbackground=theme.get("accent_primary"), selectforeground="#000000",
            borderwidth=0, highlightthickness=0, activestyle="none",
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                   command=self._listbox.yview)
        self._listbox.config(yscrollcommand=scrollbar.set)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.bind("<Double-1>", self._on_enter)

        # Help text area (scrollable)
        self._help_text = tk.Text(
            main, bg=theme.get("bg_medium"), fg=theme.get("text_secondary"),
            font=("Segoe UI", 9), wrap=tk.WORD, height=5, state=tk.DISABLED,
            borderwidth=0, highlightthickness=0, padx=6, pady=4,
        )
        self._help_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # Hint
        tk.Label(main, text="Enter = insert  |  Esc = cancel  |  ↑↓ = navigate",
                 font=("Segoe UI", 8), bg=theme.get("dialog_bg"),
                 fg=theme.get("text_dim")).pack(anchor="w", pady=(4, 0))

        # Initial full list
        self._on_search()

    def _on_search(self, *args):
        """Filters results based on search text."""
        query = self._search_var.get().strip()
        if query:
            self._results = tnc_commands.search_commands(self._model, query)
        else:
            # Show all commands
            self._results = []
            for cat in tnc_commands.get_categories(self._model):
                for cmd in tnc_commands.get_commands(self._model, cat):
                    self._results.append((cat, cmd))

        self._listbox.delete(0, tk.END)
        for cat, cmd in self._results:
            type_icon = {"text": "⌨", "key": "⚡", "sequence": "🔗"}.get(
                cmd.get("type", "text"), "⌨")
            syntax = cmd.get("syntax", cmd.get("key", ""))
            self._listbox.insert(tk.END, f" {type_icon} {cmd['cmd']:20s}  {syntax}")

        if self._results:
            self._listbox.selection_set(0)
            self._update_detail()

    def _on_arrow_up(self, event):
        """Moves selection up in the listbox."""
        sel = self._listbox.curselection()
        if sel and sel[0] > 0:
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(sel[0] - 1)
            self._listbox.see(sel[0] - 1)
            self._update_detail()
        return "break"

    def _on_arrow_down(self, event):
        """Moves selection down in the listbox."""
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._results) - 1:
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(sel[0] + 1)
            self._listbox.see(sel[0] + 1)
            self._update_detail()
        return "break"

    def _update_detail(self):
        """Updates the help area with the selected command's description and help."""
        sel = self._listbox.curselection()
        self._help_text.config(state=tk.NORMAL)
        self._help_text.delete("1.0", tk.END)
        if sel and sel[0] < len(self._results):
            cat, cmd = self._results[sel[0]]
            text = f"[{cat}] {cmd.get('desc', '')}"
            help_txt = cmd.get("help", "")
            if help_txt:
                text += f"\n\n{help_txt}"
            default = cmd.get("default")
            rng = cmd.get("range")
            if default or rng:
                text += "\n"
                if default:
                    text += f"\nDefault: {default}"
                if rng:
                    text += f"  Range: {rng}"
            self._help_text.insert("1.0", text)
        self._help_text.config(state=tk.DISABLED)

    def _on_enter(self, event):
        """Inserts the selected command and closes the popup."""
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._results):
            cat, cmd = self._results[sel[0]]
            if self._on_insert:
                self._on_insert(cmd)
            self.destroy()

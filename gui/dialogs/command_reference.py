import tkinter as tk
import tkinter.ttk as ttk
from gui import theme
from core import tnc_commands


class CommandReferenceDialog(tk.Toplevel):
    """
    TNC Command Reference window. Shows a tree of categories/commands on the left
    and detailed info on the right. Double-click inserts command into TX.

    Args:
        parent: tk widget - parent window
        model_name: str - TNC model name (from config)
        on_insert: callable(dict) or None - called with command dict on double-click
    """

    def __init__(self, parent, model_name, on_insert=None):
        super().__init__(parent)
        self._model = model_name
        self._on_insert = on_insert
        self._commands_flat = []  # (category, cmd_dict) for tree items

        self.title(f"TNC Command Reference — {model_name}")
        self.geometry("780x520")
        self.configure(bg=theme.get("dialog_bg"))
        self.transient(parent)
        self._build_ui()
        self._populate_tree()
        self._center()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Builds the layout: search bar + paned tree/detail view."""
        main = tk.Frame(self, bg=theme.get("dialog_bg"))
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Title
        tk.Label(main, text=f"📖  {self._model}", font=("Segoe UI", 13, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=8, pady=(0, 4))

        # Search bar
        search_frame = tk.Frame(main, bg=theme.get("dialog_bg"))
        search_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(search_frame, text="Search:", font=("Segoe UI", 9),
                 bg=theme.get("dialog_bg"), fg=theme.get("text_secondary")
                 ).pack(side=tk.LEFT, padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        self._search_entry = tk.Entry(
            search_frame, textvariable=self._search_var, width=30,
            bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
            font=("Consolas", 10), borderwidth=1,
            insertbackground=theme.get("accent_secondary"),
        )
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Paned: tree + detail
        pane = tk.PanedWindow(main, orient=tk.HORIZONTAL, bg=theme.get("border_color"),
                              sashwidth=4, sashrelief="flat")
        pane.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # Tree
        tree_frame = tk.Frame(pane, bg=theme.get("dialog_bg"))
        self._tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse",
                                   style="Treeview")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                     command=self._tree.yview)
        self._tree.config(yscrollcommand=tree_scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", self._on_double_click)

        # Style the treeview
        style = ttk.Style()
        style.configure("Treeview",
                        background=theme.get("bg_medium"),
                        foreground=theme.get("text_primary"),
                        fieldbackground=theme.get("bg_medium"),
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                        background=theme.get("toolbar_bg"),
                        foreground=theme.get("text_primary"))
        style.map("Treeview",
                  background=[("selected", theme.get("accent_primary"))],
                  foreground=[("selected", "#000000")])

        pane.add(tree_frame, width=260)

        # Detail panel
        detail_frame = tk.Frame(pane, bg=theme.get("dialog_bg"))
        self._detail = tk.Text(
            detail_frame, bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            font=("Consolas", 11), wrap=tk.WORD, state=tk.DISABLED,
            borderwidth=0, highlightthickness=0, padx=12, pady=8,
            selectbackground=theme.get("bg_highlight"),
        )
        self._detail.pack(fill=tk.BOTH, expand=True)
        # Tags for detail formatting
        self._detail.tag_configure("title", foreground=theme.get("accent_primary"),
                                    font=("Segoe UI", 13, "bold"))
        self._detail.tag_configure("label", foreground=theme.get("accent_cyan"),
                                    font=("Segoe UI", 10, "bold"))
        self._detail.tag_configure("value", foreground=theme.get("text_primary"),
                                    font=("Consolas", 11))
        self._detail.tag_configure("syntax", foreground=theme.get("accent_secondary"),
                                    font=("Consolas", 12, "bold"))
        self._detail.tag_configure("dim", foreground=theme.get("text_dim"),
                                    font=("Segoe UI", 9))
        self._detail.tag_configure("step", foreground=theme.get("accent_warning"),
                                    font=("Consolas", 10))
        pane.add(detail_frame)

        # Hint at bottom
        tk.Label(main, text="Double-click a command to insert it into TX",
                 font=("Segoe UI", 8), bg=theme.get("dialog_bg"),
                 fg=theme.get("text_dim")).pack(anchor="w", padx=8, pady=(4, 0))

    def _populate_tree(self, filter_text=""):
        """
        Populates the treeview with categories and commands.

        Args:
            filter_text: str - if set, only show matching commands
        """
        self._tree.delete(*self._tree.get_children())
        self._commands_flat = []

        categories = tnc_commands.get_categories(self._model)
        idx = 0

        for cat in categories:
            commands = tnc_commands.get_commands(self._model, cat)
            if filter_text:
                fl = filter_text.lower()
                commands = [c for c in commands
                            if fl in c.get("cmd", "").lower()
                            or fl in c.get("desc", "").lower()
                            or fl in c.get("syntax", "").lower()]
            if not commands:
                continue

            cat_id = self._tree.insert("", "end", text=f"📁 {cat}", open=True)
            for cmd in commands:
                type_icon = {"text": "⌨", "key": "⚡", "sequence": "🔗"}.get(
                    cmd.get("type", "text"), "⌨")
                item_id = self._tree.insert(cat_id, "end",
                                             text=f"  {type_icon} {cmd['cmd']}")
                self._commands_flat.append((item_id, cat, cmd))
                idx += 1

    def _on_search(self, *args):
        """Filters the tree based on search text."""
        self._populate_tree(self._search_var.get().strip())

    def _on_select(self, event):
        """Shows command detail when a tree item is selected."""
        sel = self._tree.selection()
        if not sel:
            return
        item_id = sel[0]

        # Find matching command
        cmd_data = None
        cat_name = ""
        for fid, cat, cmd in self._commands_flat:
            if fid == item_id:
                cmd_data = cmd
                cat_name = cat
                break

        if not cmd_data:
            # Category node selected
            self._detail.config(state=tk.NORMAL)
            self._detail.delete("1.0", tk.END)
            self._detail.config(state=tk.DISABLED)
            return

        self._show_detail(cat_name, cmd_data)

    def _show_detail(self, cat_name, cmd):
        """
        Displays command details in the detail panel, including help text.

        Args:
            cat_name: str - category name
            cmd: dict - command definition with optional help, default, range
        """
        self._detail.config(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)

        self._detail.insert(tk.END, cmd["cmd"] + "\n", "title")
        self._detail.insert(tk.END, f"Category: {cat_name}\n\n", "dim")

        self._detail.insert(tk.END, "Description\n", "label")
        self._detail.insert(tk.END, cmd.get("desc", "") + "\n\n", "value")

        cmd_type = cmd.get("type", "text")
        self._detail.insert(tk.END, "Type\n", "label")
        type_desc = {
            "text": "Text command — inserted into TX for editing",
            "key": "Special key — sent directly to TNC",
            "sequence": "Sequence — multiple steps sent automatically",
        }.get(cmd_type, cmd_type)
        self._detail.insert(tk.END, type_desc + "\n\n", "value")

        if cmd_type == "text":
            self._detail.insert(tk.END, "Syntax\n", "label")
            self._detail.insert(tk.END, cmd.get("syntax", "") + "\n", "syntax")
            # Show default and range if available
            if cmd.get("default") or cmd.get("range"):
                self._detail.insert(tk.END, "\n", "value")
                if cmd.get("default"):
                    self._detail.insert(tk.END, f"Default: {cmd['default']}  ", "dim")
                if cmd.get("range"):
                    self._detail.insert(tk.END, f"Range: {cmd['range']}", "dim")
                self._detail.insert(tk.END, "\n", "value")
        elif cmd_type == "key":
            self._detail.insert(tk.END, "Key\n", "label")
            self._detail.insert(tk.END, cmd.get("key", "") + "\n", "syntax")
        elif cmd_type == "sequence":
            self._detail.insert(tk.END, "Steps\n", "label")
            for i, step in enumerate(cmd.get("steps", []), 1):
                action = step.get("action", "")
                desc = step.get("desc", "")
                if action == "ctrl":
                    detail = f"  {i}. Send Ctrl+{step.get('key', '?')}"
                elif action == "wait":
                    detail = f"  {i}. Wait {step.get('ms', 0)}ms"
                elif action == "text":
                    detail = f"  {i}. Send: {step.get('value', '')!r}"
                else:
                    detail = f"  {i}. {action}"
                if desc:
                    detail += f"  ({desc})"
                self._detail.insert(tk.END, detail + "\n", "step")

        # Show help text
        help_text = cmd.get("help", "")
        if help_text:
            self._detail.insert(tk.END, "\nHelp\n", "label")
            self._detail.insert(tk.END, help_text + "\n", "value")

        self._detail.config(state=tk.DISABLED)

    def _on_double_click(self, event):
        """Inserts selected command into TX on double-click."""
        sel = self._tree.selection()
        if not sel:
            return
        item_id = sel[0]
        for fid, cat, cmd in self._commands_flat:
            if fid == item_id:
                if self._on_insert:
                    self._on_insert(cmd)
                return

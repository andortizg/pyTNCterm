#!/usr/bin/env python3
# Nuitka build options (applied automatically by "python -m nuitka main.py"):
# nuitka-project: --onefile
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project: --include-data-dir={MAIN_DIRECTORY}/resources=resources
# nuitka-project: --output-filename=pyTNCterm
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --windows-console-mode=attach
"""
pyTNCterm - A portable multi-mode TNC terminal program.

Author: Andrés Ortiz, EA7HQL
License: MIT
"""

import sys
import tkinter as tk


def main():
    """Application entry point. Creates the root window and starts the main loop."""
    root = tk.Tk()

    # Set window icon (if available)
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    # Import here to avoid circular imports
    from gui.main_window import MainWindow

    app = MainWindow(root)
    root.mainloop()


def _show_fatal_error():
    """Shows the startup traceback in a message box (the .exe has no console)."""
    import traceback
    text = traceback.format_exc()
    try:
        from tkinter import messagebox
        err_root = tk.Tk()
        err_root.withdraw()
        messagebox.showerror("pyTNCterm - startup error", text[-3000:], parent=err_root)
        err_root.destroy()
    except Exception:
        pass
    print(text, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _show_fatal_error()
        sys.exit(1)

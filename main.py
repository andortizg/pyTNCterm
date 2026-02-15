#!/usr/bin/env python3
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


if __name__ == "__main__":
    main()

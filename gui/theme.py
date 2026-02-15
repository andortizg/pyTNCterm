"""
Theme system with multiple predefined themes and dynamic switching.
Each theme is a dict with all color definitions used across the application.
Call get(key) to retrieve a color from the active theme.
"""

THEMES = {
    "Dark Blue": {
        "bg_dark": "#0f1923", "bg_medium": "#1b2838", "bg_light": "#2a3a4a",
        "bg_highlight": "#3d5266",
        "accent_primary": "#4fc3f7", "accent_secondary": "#00e676",
        "accent_warning": "#ffd54f", "accent_error": "#ef5350",
        "accent_cyan": "#00bcd4", "accent_orange": "#ffab40",
        "text_primary": "#e0e0e0", "text_secondary": "#90a4ae", "text_dim": "#607d8b",
        "toolbar_bg": "#162231", "toolbar_btn_bg": "#243447",
        "toolbar_btn_fg": "#b0bec5", "toolbar_btn_active": "#345068",
        "tab_bg": "#1b2838", "tab_selected_bg": "#0d1b2a",
        "tab_fg": "#78909c", "tab_selected_fg": "#4fc3f7",
        "status_bg": "#0d1520", "status_fg": "#78909c",
        "status_connected": "#00e676", "status_disconnected": "#ef5350",
        "border_color": "#2a3a4a", "border_accent": "#345068",
        "scrollbar_bg": "#1b2838", "scrollbar_fg": "#3d5266",
        "dialog_bg": "#1b2838", "dialog_fg": "#e0e0e0",
        "entry_bg": "#0f1923", "entry_fg": "#e0e0e0",
        "button_bg": "#2a3f55", "button_fg": "#e0e0e0", "button_active": "#3d5a78",
        "monitor_bg": "#0a1929", "monitor_fg": "#4fc3f7",
        "monitor_info": "#ffd54f", "monitor_error": "#ef5350",
        "channel_bg": "#0d1b2a", "channel_rx": "#e0e0e0",
        "channel_tx": "#00e676", "channel_system": "#ffd54f",
        "input_bg": "#1a1a2e", "input_fg": "#00e676", "input_prompt": "#4fc3f7",
    },
    "Amber Retro": {
        "bg_dark": "#1a1200", "bg_medium": "#2a1f00", "bg_light": "#3d2e00",
        "bg_highlight": "#554200",
        "accent_primary": "#ffb300", "accent_secondary": "#ff8f00",
        "accent_warning": "#ffe082", "accent_error": "#ff6e40",
        "accent_cyan": "#ffca28", "accent_orange": "#ff9100",
        "text_primary": "#ffcc80", "text_secondary": "#ff9800", "text_dim": "#8d6e00",
        "toolbar_bg": "#211800", "toolbar_btn_bg": "#332600",
        "toolbar_btn_fg": "#ffb74d", "toolbar_btn_active": "#4d3a00",
        "tab_bg": "#2a1f00", "tab_selected_bg": "#1a1200",
        "tab_fg": "#8d6e00", "tab_selected_fg": "#ffb300",
        "status_bg": "#140d00", "status_fg": "#8d6e00",
        "status_connected": "#ff8f00", "status_disconnected": "#ff6e40",
        "border_color": "#3d2e00", "border_accent": "#554200",
        "scrollbar_bg": "#2a1f00", "scrollbar_fg": "#554200",
        "dialog_bg": "#2a1f00", "dialog_fg": "#ffcc80",
        "entry_bg": "#1a1200", "entry_fg": "#ffb74d",
        "button_bg": "#3d2e00", "button_fg": "#ffcc80", "button_active": "#554200",
        "monitor_bg": "#140d00", "monitor_fg": "#ffb300",
        "monitor_info": "#ffe082", "monitor_error": "#ff6e40",
        "channel_bg": "#1a1200", "channel_rx": "#ffcc80",
        "channel_tx": "#ff8f00", "channel_system": "#ffe082",
        "input_bg": "#1a1200", "input_fg": "#ffb300", "input_prompt": "#ff9100",
    },
    "Green Terminal": {
        "bg_dark": "#0a0f0a", "bg_medium": "#121f12", "bg_light": "#1e301e",
        "bg_highlight": "#2d4a2d",
        "accent_primary": "#00ff41", "accent_secondary": "#39ff14",
        "accent_warning": "#b2ff59", "accent_error": "#ff1744",
        "accent_cyan": "#69f0ae", "accent_orange": "#76ff03",
        "text_primary": "#b9f6ca", "text_secondary": "#69f0ae", "text_dim": "#2e7d32",
        "toolbar_bg": "#0d170d", "toolbar_btn_bg": "#1a2e1a",
        "toolbar_btn_fg": "#81c784", "toolbar_btn_active": "#2d4a2d",
        "tab_bg": "#121f12", "tab_selected_bg": "#0a0f0a",
        "tab_fg": "#2e7d32", "tab_selected_fg": "#00ff41",
        "status_bg": "#070b07", "status_fg": "#2e7d32",
        "status_connected": "#00ff41", "status_disconnected": "#ff1744",
        "border_color": "#1e301e", "border_accent": "#2d4a2d",
        "scrollbar_bg": "#121f12", "scrollbar_fg": "#2d4a2d",
        "dialog_bg": "#121f12", "dialog_fg": "#b9f6ca",
        "entry_bg": "#0a0f0a", "entry_fg": "#00ff41",
        "button_bg": "#1e301e", "button_fg": "#b9f6ca", "button_active": "#2d4a2d",
        "monitor_bg": "#070b07", "monitor_fg": "#00ff41",
        "monitor_info": "#b2ff59", "monitor_error": "#ff1744",
        "channel_bg": "#0a0f0a", "channel_rx": "#b9f6ca",
        "channel_tx": "#39ff14", "channel_system": "#b2ff59",
        "input_bg": "#0a0f0a", "input_fg": "#00ff41", "input_prompt": "#69f0ae",
    },
    "Solarized Dark": {
        "bg_dark": "#002b36", "bg_medium": "#073642", "bg_light": "#094c5a",
        "bg_highlight": "#1a6475",
        "accent_primary": "#268bd2", "accent_secondary": "#2aa198",
        "accent_warning": "#b58900", "accent_error": "#dc322f",
        "accent_cyan": "#2aa198", "accent_orange": "#cb4b16",
        "text_primary": "#93a1a1", "text_secondary": "#839496", "text_dim": "#586e75",
        "toolbar_bg": "#003340", "toolbar_btn_bg": "#0a4050",
        "toolbar_btn_fg": "#839496", "toolbar_btn_active": "#1a5565",
        "tab_bg": "#073642", "tab_selected_bg": "#002b36",
        "tab_fg": "#586e75", "tab_selected_fg": "#268bd2",
        "status_bg": "#001f27", "status_fg": "#586e75",
        "status_connected": "#2aa198", "status_disconnected": "#dc322f",
        "border_color": "#094c5a", "border_accent": "#1a6475",
        "scrollbar_bg": "#073642", "scrollbar_fg": "#094c5a",
        "dialog_bg": "#073642", "dialog_fg": "#93a1a1",
        "entry_bg": "#002b36", "entry_fg": "#93a1a1",
        "button_bg": "#094c5a", "button_fg": "#93a1a1", "button_active": "#1a6475",
        "monitor_bg": "#001f27", "monitor_fg": "#268bd2",
        "monitor_info": "#b58900", "monitor_error": "#dc322f",
        "channel_bg": "#002b36", "channel_rx": "#93a1a1",
        "channel_tx": "#2aa198", "channel_system": "#b58900",
        "input_bg": "#002b36", "input_fg": "#2aa198", "input_prompt": "#268bd2",
    },
    "Midnight Purple": {
        "bg_dark": "#110b1a", "bg_medium": "#1c1230", "bg_light": "#2a1c48",
        "bg_highlight": "#3d2966",
        "accent_primary": "#bb86fc", "accent_secondary": "#03dac6",
        "accent_warning": "#ffb74d", "accent_error": "#cf6679",
        "accent_cyan": "#03dac6", "accent_orange": "#ff7043",
        "text_primary": "#e0d6f0", "text_secondary": "#a08bbe", "text_dim": "#6a5483",
        "toolbar_bg": "#150e22", "toolbar_btn_bg": "#231838",
        "toolbar_btn_fg": "#a08bbe", "toolbar_btn_active": "#3d2966",
        "tab_bg": "#1c1230", "tab_selected_bg": "#110b1a",
        "tab_fg": "#6a5483", "tab_selected_fg": "#bb86fc",
        "status_bg": "#0c0712", "status_fg": "#6a5483",
        "status_connected": "#03dac6", "status_disconnected": "#cf6679",
        "border_color": "#2a1c48", "border_accent": "#3d2966",
        "scrollbar_bg": "#1c1230", "scrollbar_fg": "#3d2966",
        "dialog_bg": "#1c1230", "dialog_fg": "#e0d6f0",
        "entry_bg": "#110b1a", "entry_fg": "#e0d6f0",
        "button_bg": "#2a1c48", "button_fg": "#e0d6f0", "button_active": "#3d2966",
        "monitor_bg": "#0c0712", "monitor_fg": "#bb86fc",
        "monitor_info": "#ffb74d", "monitor_error": "#cf6679",
        "channel_bg": "#110b1a", "channel_rx": "#e0d6f0",
        "channel_tx": "#03dac6", "channel_system": "#ffb74d",
        "input_bg": "#110b1a", "input_fg": "#03dac6", "input_prompt": "#bb86fc",
    },
    "Light": {
        "bg_dark": "#f5f5f5", "bg_medium": "#e0e0e0", "bg_light": "#cccccc",
        "bg_highlight": "#b0bec5",
        "accent_primary": "#1565c0", "accent_secondary": "#00897b",
        "accent_warning": "#f57f17", "accent_error": "#c62828",
        "accent_cyan": "#00838f", "accent_orange": "#e65100",
        "text_primary": "#212121", "text_secondary": "#424242", "text_dim": "#757575",
        "toolbar_bg": "#e8e8e8", "toolbar_btn_bg": "#d0d0d0",
        "toolbar_btn_fg": "#424242", "toolbar_btn_active": "#b0bec5",
        "tab_bg": "#e0e0e0", "tab_selected_bg": "#ffffff",
        "tab_fg": "#757575", "tab_selected_fg": "#1565c0",
        "status_bg": "#dcdcdc", "status_fg": "#616161",
        "status_connected": "#2e7d32", "status_disconnected": "#c62828",
        "border_color": "#bdbdbd", "border_accent": "#90a4ae",
        "scrollbar_bg": "#e0e0e0", "scrollbar_fg": "#b0bec5",
        "dialog_bg": "#eeeeee", "dialog_fg": "#212121",
        "entry_bg": "#ffffff", "entry_fg": "#212121",
        "button_bg": "#d0d0d0", "button_fg": "#212121", "button_active": "#b0bec5",
        "monitor_bg": "#ffffff", "monitor_fg": "#1565c0",
        "monitor_info": "#e65100", "monitor_error": "#c62828",
        "channel_bg": "#ffffff", "channel_rx": "#212121",
        "channel_tx": "#00897b", "channel_system": "#f57f17",
        "input_bg": "#ffffff", "input_fg": "#212121", "input_prompt": "#1565c0",
    },
}

_current = THEMES["Dark Blue"].copy()
_current_name = "Dark Blue"


def get_theme_names():
    """Returns: list of str - all available theme names"""
    return list(THEMES.keys())


def get_current_theme_name():
    """Returns: str - name of the currently active theme"""
    return _current_name


def get(key, fallback="#ff00ff"):
    """
    Gets a color value from the current theme.

    Args:
        key: str - theme color key (e.g., "bg_dark", "accent_primary")
        fallback: str - color to return if key not found

    Returns: str - hex color value
    """
    return _current.get(key, fallback)


def set_theme(name):
    """
    Switches the active theme.

    Args:
        name: str - theme name (must exist in THEMES)

    Returns: bool - True if theme was changed
    """
    global _current, _current_name
    if name in THEMES:
        _current = THEMES[name].copy()
        _current_name = name
        return True
    return False


def apply_theme(root):
    """
    Applies the current theme to all ttk widget styles.

    Args:
        root: tk.Tk - the root window
    """
    import tkinter.ttk as ttk

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    t = _current

    style.configure("TFrame", background=t["bg_dark"])
    style.configure("Toolbar.TFrame", background=t["toolbar_bg"])
    style.configure("Status.TFrame", background=t["status_bg"])
    style.configure("Dialog.TFrame", background=t["dialog_bg"])

    style.configure("TLabel", background=t["bg_dark"], foreground=t["text_primary"],
                     font=("Segoe UI", 10))
    style.configure("Status.TLabel", background=t["status_bg"], foreground=t["status_fg"],
                     font=("Segoe UI", 9))
    style.configure("Title.TLabel", background=t["dialog_bg"], foreground=t["accent_primary"],
                     font=("Segoe UI", 14, "bold"))
    style.configure("Heading.TLabel", background=t["dialog_bg"], foreground=t["accent_cyan"],
                     font=("Segoe UI", 10, "bold"))
    style.configure("Dialog.TLabel", background=t["dialog_bg"], foreground=t["text_primary"],
                     font=("Segoe UI", 10))

    style.configure("TButton", background=t["button_bg"], foreground=t["button_fg"],
                     font=("Segoe UI", 9), padding=(10, 4), borderwidth=0)
    style.map("TButton",
              background=[("active", t["button_active"]), ("pressed", t["accent_primary"])],
              foreground=[("active", "#ffffff")])

    style.configure("Toolbar.TButton", background=t["toolbar_btn_bg"],
                     foreground=t["toolbar_btn_fg"],
                     font=("Segoe UI", 9), padding=(12, 5), borderwidth=0)
    style.map("Toolbar.TButton",
              background=[("active", t["toolbar_btn_active"]),
                          ("pressed", t["accent_primary"])],
              foreground=[("active", "#ffffff")])

    style.configure("Accent.TButton", background=t["accent_primary"], foreground="#000000",
                     font=("Segoe UI", 9, "bold"), padding=(12, 5))
    style.map("Accent.TButton", background=[("active", t["bg_highlight"])])

    style.configure("TEntry", fieldbackground=t["entry_bg"], foreground=t["entry_fg"],
                     insertcolor=t["accent_secondary"], borderwidth=1, padding=(5, 3))

    style.configure("TCombobox", fieldbackground=t["entry_bg"], foreground=t["entry_fg"],
                     background=t["button_bg"], arrowcolor=t["text_secondary"],
                     borderwidth=1, padding=(3, 3))
    style.map("TCombobox",
              fieldbackground=[("readonly", t["entry_bg"])],
              foreground=[("readonly", t["entry_fg"])])

    style.configure("TNotebook", background=t["bg_dark"], borderwidth=0)
    style.configure("TNotebook.Tab", background=t["tab_bg"], foreground=t["tab_fg"],
                     font=("Segoe UI", 9), padding=(14, 6), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", t["tab_selected_bg"])],
              foreground=[("selected", t["tab_selected_fg"])])

    style.configure("TLabelframe", background=t["dialog_bg"], foreground=t["accent_primary"],
                     borderwidth=1, relief="groove")
    style.configure("TLabelframe.Label", background=t["dialog_bg"],
                     foreground=t["accent_primary"], font=("Segoe UI", 10, "bold"))

    style.configure("TSeparator", background=t["border_color"])

    style.configure("Vertical.TScrollbar", background=t["scrollbar_bg"],
                     troughcolor=t["bg_dark"], arrowcolor=t["text_secondary"], borderwidth=0)
    style.map("Vertical.TScrollbar", background=[("active", t["scrollbar_fg"])])

    style.configure("TCheckbutton", background=t["dialog_bg"], foreground=t["text_primary"],
                     font=("Segoe UI", 10))
    style.map("TCheckbutton", background=[("active", t["dialog_bg"])])

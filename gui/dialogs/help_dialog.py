import tkinter as tk
import tkinter.ttk as ttk
from gui import theme

HELP_TOPICS = [
    ("Getting Started", """
Welcome to pyTNCterm!

pyTNCterm is a portable terminal program for amateur radio digital modes. \
It communicates with your TNC (Terminal Node Controller) via a serial RS-232 connection.

Quick Start:
1. Go to Settings > Serial Port and select your COM port and baud rate.
2. Enter your callsign in Settings > Station.
3. Click the Connect button on the toolbar.
4. Type commands in the input line at the bottom and press Enter.

The program works in terminal mode: everything you type is sent directly to the TNC, \
and all TNC output is displayed in the channel window.
"""),
    ("Serial Port Setup", """
Configure your serial port in Settings (Ctrl+,):

- Port: Select the COM port (Windows) or /dev/ttyUSBx (Linux) for your TNC.
- Baud Rate: Must match your TNC setting. Common values: 1200, 9600.
- Data Bits: Usually 8.
- Stop Bits: Usually 1.
- Parity: Usually None.
- Flow Control: Use RTS/CTS (hardware) if your cable supports it, otherwise None.

Click "Refresh Ports" if you connected the TNC after opening Settings.
"""),
    ("Monitor Panel", """
The Monitor panel at the top shows all raw traffic from the TNC, including \
AX.25 frame headers, unproto/beacon traffic, and data from all channels.

The monitor is always active regardless of which channel tab is selected. \
Clear it with the "Clear Monitor" toolbar button.
"""),
    ("Channel Tabs", """
The channel area uses tabs to separate different connections.

- Channel 0: The default channel, always present.
- Additional tabs are created for new connections (future feature).

Text colors:
- White/light: Received data (RX)
- Green: Your transmitted data (TX)
- Yellow: System messages
- Red: Error messages
"""),
    ("Themes", """
pyTNCterm includes several built-in visual themes:

- Dark Blue: Modern dark theme (default)
- Amber Retro: Classic amber-on-black terminal look
- Green Terminal: Retro green phosphor terminal
- Solarized Dark: Ethan Schoonover's Solarized palette
- Midnight Purple: Dark purple accent theme
- Light: Light background for daytime use

Change themes in Settings > Appearance > Theme, or from the View > Theme menu \
for quick switching. Theme changes apply immediately.
"""),
    ("Command Input", """
The input line at the bottom is where you type commands.

- Press Enter to send a command to the TNC.
- Use Up/Down arrow keys to browse command history.
- Commands are sent directly to the TNC as typed.

Common TNC commands (vary by model):
- C <callsign> - Connect to a station
- D - Disconnect
- MON ON/OFF - Enable/disable monitor
- MH - Show heard stations
- PACKET/CW/RTTY - Switch operating mode
"""),
    ("Keyboard Shortcuts", """
Ctrl+Q          Quit the application
Ctrl+K          Connect to serial port
Ctrl+D          Disconnect from serial port
Ctrl+,          Open Settings
Ctrl+L          Clear active channel
F1              Open this Help window
"""),
    ("Multi-Mode Operation", """
pyTNCterm supports multi-mode TNCs such as Kantronics KAM, PK-232, \
MFJ-1278, and SCS PTC-II.

Supported modes (depending on your TNC): Packet Radio (AX.25), CW, RTTY, \
AMTOR, PACTOR, PSK31.

To switch modes, send the appropriate command to your TNC. \
Quick mode switching via menus will be available in a future version.
"""),
    ("YAPP File Transfer", """
YAPP (Yet Another Packet Program) is a file transfer protocol for packet radio.

YAPP support will be available in a future version with send/receive, \
progress display, configurable directories, and cancel capability.
"""),
    ("Troubleshooting", """
Cannot connect to TNC:
- Check the serial cable is connected and TNC is powered on.
- Verify correct COM port and baud rate in Settings.
- Try different flow control settings.
- Ensure no other program is using the port.

Garbled text:
- Baud rate probably does not match your TNC. Try different values.
- Check data bits and parity settings.
"""),
]


class HelpDialog(tk.Toplevel):
    """
    Help window with topic list and content display.

    Args:
        parent: tk widget - parent window
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("pyTNCterm Help")
        self.geometry("750x520")
        self.configure(bg=theme.get("dialog_bg"))
        self.transient(parent)
        self._build_ui()
        self._center()
        self._topic_list.selection_set(0)
        self._show_topic(None)

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        main = tk.Frame(self, bg=theme.get("dialog_bg"))
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tk.Label(main, text="📖  Help Topics", font=("Segoe UI", 14, "bold"),
                 bg=theme.get("dialog_bg"), fg=theme.get("accent_primary")
                 ).pack(anchor="w", padx=8, pady=(4, 8))

        pane = tk.PanedWindow(main, orient=tk.HORIZONTAL, bg=theme.get("border_color"),
                              sashwidth=3, sashrelief="flat")
        pane.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(pane, bg=theme.get("dialog_bg"))
        self._topic_list = tk.Listbox(
            left, bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            font=("Segoe UI", 10),
            selectbackground=theme.get("accent_primary"), selectforeground="#000000",
            borderwidth=0, highlightthickness=0, activestyle="none",
        )
        self._topic_list.pack(fill=tk.BOTH, expand=True, padx=(0, 2))
        for title, _ in HELP_TOPICS:
            self._topic_list.insert(tk.END, f"  {title}")
        self._topic_list.bind("<<ListboxSelect>>", self._show_topic)
        pane.add(left, width=200)

        right = tk.Frame(pane, bg=theme.get("dialog_bg"))
        self._content_title = tk.Label(
            right, text="", font=("Segoe UI", 13, "bold"),
            bg=theme.get("dialog_bg"), fg=theme.get("accent_cyan"), anchor="w"
        )
        self._content_title.pack(fill=tk.X, padx=12, pady=(8, 4))
        self._content = tk.Text(
            right, bg=theme.get("bg_medium"), fg=theme.get("text_primary"),
            font=("Segoe UI", 10), wrap=tk.WORD, state=tk.DISABLED,
            borderwidth=0, highlightthickness=0, padx=12, pady=8,
            selectbackground=theme.get("bg_highlight"),
        )
        self._content.pack(fill=tk.BOTH, expand=True)
        pane.add(right)

        tk.Button(
            main, text="Close", font=("Segoe UI", 10),
            bg=theme.get("button_bg"), fg=theme.get("button_fg"),
            activebackground=theme.get("button_active"),
            bd=0, padx=20, pady=6, cursor="hand2", command=self.destroy
        ).pack(pady=(8, 4))

    def _show_topic(self, event):
        """Displays the selected topic content."""
        sel = self._topic_list.curselection()
        if not sel:
            return
        title, body = HELP_TOPICS[sel[0]]
        self._content_title.config(text=title)
        self._content.config(state=tk.NORMAL)
        self._content.delete("1.0", tk.END)
        self._content.insert("1.0", body.strip())
        self._content.config(state=tk.DISABLED)

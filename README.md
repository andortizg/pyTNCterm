# 📡 pyTNCterm

**A portable multi-mode TNC terminal for amateur radio digital communications.**

pyTNCterm is a modern, cross-platform terminal program for controlling hardware TNCs (Terminal Node Controllers) used in packet radio and other amateur radio digital modes. It provides a clean, themeable GUI with split RX/TX terminal, AX.25 monitor with frame-type coloring, YAPP file transfers, model-specific TNC command reference, and autocomplete, all in a single lightweight Python/Tkinter application.

---

## Features

### Terminal & Communication

- **Split RX/TX terminal** — Separate scrollable areas for received data and transmitted commands, with distinct color coding for easy readability.
- **TX history** — Navigate previously sent commands with Up/Down arrow keys, similar to a shell history.
- **Monitor panel** — Dedicated tab showing raw AX.25 traffic with automatic frame-type classification and coloring (I-frames, UI, SABM, UA, DISC, RR, RNR, REJ, FRMR, etc.).
- **Callsign filter** — Filter the monitor panel to show only traffic involving a specific callsign.
- **Full serial port control** — Configurable baud rate (300–115200), data bits (7/8), stop bits (1/1.5/2), parity (None/Even/Odd/Mark/Space), and flow control (None/RTS-CTS/XON-XOFF).

### TNC Model Support

pyTNCterm ships with **manufacturer-verified command sets** for 13 TNC models, sourced from official hardware manuals. Each model includes specific commands, syntax, help text, defaults, ranges, and hardware connector pinout information:

| Manufacturer | Models | Modes |
|---|---|---|
| **Kantronics** | KPC-3 / KPC-3+, KAM / KAM+, KAM-XL | Packet, CW, RTTY, AMTOR, PACTOR, GTOR |
| **AEA / Timewave** | PK-232 / PK-232MBX, PK-88 | Packet, CW, RTTY, ASCII, AMTOR, PACTOR, NAVTEX |
| **MFJ** | MFJ-1278 / MFJ-1278B, MFJ-1270 / MFJ-1274 | Packet, CW, RTTY, AMTOR, SSTV, FAX |
| **Other** | Generic TNC-2 Compatible, TNC-Pi, Other | Packet, APRS |

Model-specific features include proper command differences (Kantronics dual-port slash notation, SCS non-TNC-2 command structure with `MYcall` instead of `MYCALL`, AEA `MONITOR 0-6` levels vs Kantronics `MONITOR ON/OFF`, MFJ `MODE` command for mode switching, etc.).

### Command Reference & Autocomplete

- **F3 — Full command reference** — Categorized tree view of all commands for the selected TNC model, with syntax, help text, defaults, ranges, and hardware connector pinouts. Double-click any command to insert it into the TX input.
- **F2 — Quick command search** — Fuzzy-search popup to quickly find and insert any TNC command.
- **Autocomplete tooltip** — As-you-type command suggestions in the TX input bar, showing matching commands with brief descriptions. Navigate with arrow keys, insert with Tab. Can be toggled on/off in Settings.

### YAPP File Transfers

Full implementation of the **YAPP protocol** (Yet Another Packet Protocol, WA7MBL Rev 1.1, 1986) for binary file transfers over packet radio:

- Send and receive files through the YAPP menu.
- Complete state machine implementation following the WA7MBL specification (SI→RR→HD→RF→DT→EF→AF→ET→AT).
- All protocol packet types: SI, RR, RF, AF, AT, CA, HD, DT, EF, ET, NR, CN, TX.
- Cancel support (CN/CA) from either side.
- Crash timer with automatic SI retries.
- Dedicated transfer dialog with:
  - Real-time progress bar with percentage.
  - Bytes transferred / total and transfer speed.
  - Color-coded protocol message log (▲TX / ▼RX arrows, timestamps, control frame names).
  - Cancel button during transfer.

### Themes

Six built-in color themes, switchable at runtime from the View menu:

| Theme | Description |
|---|---|
| **Dark Blue** | Default dark theme with blue accents |
| **Amber Retro** | Classic amber-on-black CRT look |
| **Green Terminal** | Green phosphor terminal aesthetic |
| **Solarized Dark** | Ethan Schoonover's Solarized palette |
| **Midnight Purple** | Dark theme with purple accents |
| **Light** | Light background theme for daytime use |

All UI elements — terminal, monitor, dialogs, toolbar, status bar, progress bars — respect the active theme.

### Other

- **Station info** — Configure your callsign, name, and grid locator in Settings.
- **Auto-init strings** — Model-specific initialization commands sent on connect.
- **Persistent configuration** — Window size/position, serial port settings, theme, TNC model, and all preferences saved to JSON config file.
- **Status bar** — Shows connection state, port name, TX/RX byte counters.
- **Toolbar** — Quick-access buttons for Connect, Disconnect, Clear Monitor, Clear Channel.
- **Keyboard shortcuts** for all common actions.

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+K` | Connect to serial port |
| `Ctrl+D` | Disconnect |
| `Ctrl+L` | Clear terminal |
| `Ctrl+,` | Open Settings |
| `Ctrl+S` | YAPP Send File |
| `Ctrl+R` | YAPP Receive File |
| `Ctrl+Q` | Quit |
| `F1` | Help |
| `F2` | Quick command search |
| `F3` | Full TNC command reference |
| `Up/Down` | Navigate TX history |
| `Tab` | Accept autocomplete suggestion |
| `Escape` | Dismiss autocomplete |

---

## Installation

### Requirements

- **Python 3.8+**
- **Tkinter** (included with most Python distributions)
- **pyserial** (`pip install pyserial`)

### Quick Start

```bash
git clone https://github.com/ea7hql/pyTNCterm.git
cd pyTNCterm
pip install pyserial
python main.py
```

### Linux

On Debian/Ubuntu, if Tkinter is not installed:

```bash
sudo apt install python3-tk
pip install pyserial
python3 main.py
```

### Windows

Python from [python.org](https://python.org) includes Tkinter by default:

```
pip install pyserial
python main.py
```

### macOS

```bash
pip3 install pyserial
python3 main.py
```

---

## Project Structure

```
pyTNCterm/
├── main.py                          # Application entry point
├── core/
│   ├── config.py                    # JSON configuration manager
│   ├── tnc_commands.py              # TNC command loader from JSON files
│   └── yapp_handler.py              # YAPP protocol state machine
├── gui/
│   ├── main_window.py               # Main window, menus, polling loop
│   ├── terminal_tab.py              # Split RX/TX terminal with history
│   ├── monitor_panel.py             # AX.25 monitor with frame coloring
│   ├── input_bar.py                 # TX input bar
│   ├── autocomplete.py              # Command autocomplete tooltip
│   ├── toolbar.py                   # Quick-access toolbar
│   ├── status_bar.py                # Status bar with counters
│   ├── theme.py                     # Theme definitions and switching
│   └── dialogs/
│       ├── settings_dialog.py       # Settings (Station, Serial, Appearance, Paths)
│       ├── command_reference.py     # F3 command reference dialog
│       ├── command_search.py        # F2 quick search popup
│       ├── yapp_dialog.py           # YAPP transfer progress dialog
│       ├── help_dialog.py           # F1 help dialog
│       └── about_dialog.py          # About dialog
├── serial_port/
│   └── serial_handler.py           # Serial I/O with background reader thread
├── resources/
│   ├── default_config.json          # Default configuration template
│   └── tnc_commands/                # Per-model TNC command definitions
│       ├── kantronics_kpc3.json     # Kantronics KPC-3 / KPC-3+ (40 commands)
│       ├── kantronics_kam.json      # Kantronics KAM / KAM+ (60 commands)
│       ├── kantronics_kamxl.json    # Kantronics KAM-XL (59 commands)
│       ├── aea_pk232.json           # AEA/Timewave PK-232 (42 commands)
│       ├── aea_pk88.json            # AEA PK-88 (19 commands)
│       ├── mfj_1278.json            # MFJ-1278 / MFJ-1278B (44 commands)
│       ├── mfj_1270.json            # MFJ-1270 / MFJ-1274 (19 commands)
│       ├── scs_ptc2.json            # SCS PTC-II / IIe / IIpro (44 commands)
│       ├── scs_ptc3.json            # SCS PTC-III (45 commands)
│       ├── scs_tracker.json         # SCS Tracker / DSP TNC (18 commands)
│       ├── generic_tnc2.json        # Generic TNC-2 (27 commands)
│       ├── tnc_pi.json              # TNC-Pi (27 commands)
│       └── other.json               # Fallback (27 commands)
└── LICENSE                          # MIT License
```

---

## Configuration

Settings are stored in `~/.pytncterm/config.json` and editable through the Settings dialog (`Ctrl+,`):

**Station** — Callsign, operator name, grid locator.

**Serial Port** — Port, baud rate, data bits, stop bits, parity, flow control. Auto-detection of available ports.

**TNC Model** — Select your hardware TNC. This determines the available commands for autocomplete, reference, and the initialization string sent on connect.

**Appearance** — Theme selection, font family and size.

**Paths** — YAPP download directory, log directory.

---

## YAPP Protocol Details

The YAPP implementation follows the original specification by Jeff Jacobsen WA7MBL (Revision 1.1, June 1986). The protocol uses a simple state machine with two-byte packet headers:

```
Sender:   S ──SI──→ SH ──HD──→ SD ──DT...──→ SE ──EF──→ ST ──ET──→ Done
               ↑RR       ↑RF                      ↑AF       ↑AT
Receiver: R ──────→ RH ──────→ RD ─────────→ (file complete) ──→ Done
```

Supported packet types:

| Code | Name | Bytes | Description |
|---|---|---|---|
| SI | Send Init | `ENQ 01` | Sender announces transfer |
| RR | Receive Ready | `ACK 01` | Receiver ready for header |
| HD | Send Header | `SOH len data` | Filename + size |
| RF | Receive File | `ACK 02` | Receiver ready for data |
| DT | Send Data | `STX len data` | File data (up to 250 bytes) |
| EF | End of File | `ETX 01` | File transmission complete |
| AF | Ack EOF | `ACK 03` | Receiver confirms file received |
| ET | End of Transfer | `EOT 01` | No more files |
| AT | Ack EOT | `ACK 04` | Receiver confirms end |
| NR | Not Ready | `NAK len reason` | Receiver cannot accept |
| CN | Cancel | `CAN len reason` | Abort transfer |
| CA | Cancel Ack | `ACK 05` | Acknowledge cancel |

Compatible with BPQ32, QTermTCP, EasyTerm, FBB BBS, and other YAPP-capable packet software.

---

## Adding TNC Models

TNC command definitions are plain JSON files in `resources/tnc_commands/`. To add a new TNC model:

1. Create a new JSON file following the existing format:

```json
{
  "model": "Your TNC Model Name",
  "categories": {
    "Connection": [
      {
        "cmd": "CONNECT",
        "type": "text",
        "desc": "Connect to a station",
        "syntax": "C {callsign}",
        "help": "Detailed help text..."
      }
    ]
  },
  "connectors": {
    "Computer Port": {
      "type": "DB-25 RS-232",
      "pinout": {
        "Pin 2": "TX Data",
        "Pin 3": "RX Data",
        "Pin 7": "Signal Ground"
      }
    }
  }
}
```

2. Add the model to `TNC_MODELS` in `gui/dialogs/settings_dialog.py`.

---

## Contributing

Contributions are welcome. Areas where help is particularly appreciated:

- Additional TNC model command sets (verified from manufacturer manuals).
- Testing with real hardware TNCs.
- YAPP interoperability testing with other software (BPQ32, EasyTerm, FBB, etc.).
- Localization / translations.
- Bug reports and feature requests.

---

## License

MIT License — Copyright © 2025 Andrés Ortiz, EA7HQL

See [LICENSE](LICENSE) for the full text.

---

## Acknowledgments

- **Jeff Jacobsen, WA7MBL** — YAPP protocol specification.
- **FC1EBN / F6FBB** — YappC checksum and resume extensions.
- The amateur radio packet community for keeping the mode alive.



# pyTNCterm

A portable multi-mode TNC terminal program for amateur radio, written in Python/tkinter.

## Features

- Direct serial connection to TNC in terminal mode
- Split RX/TX terminal with resizable panes
- Monitor panel with AX.25 frame type coloring (SABM, DISC, UA, I, RR, UI...)
- Callsign filter on monitor
- TNC model presets (KPC-3, KAM, PK-232, MFJ-1278, SCS PTC-II/III, etc.)
- Configurable initialization commands per TNC
- 6 built-in themes (Dark Blue, Amber Retro, Green Terminal, Solarized Dark, Midnight Purple, Light)
- Customizable fonts and colors
- Command history (Up/Down arrows)
- Persistent configuration

## Requirements

- Python 3.8+
- pyserial

## Installation

```bash
pip install pyserial
```

## Usage

```bash
cd pytncterm
python main.py
```

1. Go to **Settings > TNC** and select your TNC model.
2. Go to **Settings > Serial Port** and configure your COM port and baud rate.
3. Enter your callsign in **Settings > Station**.
4. Click **Connect**.
5. Type commands in the TX panel and press **Enter** to send.

## Keyboard Shortcuts

| Key | Action |
|---|---|
| Ctrl+K | Connect |
| Ctrl+D | Disconnect |
| Ctrl+L | Clear connection |
| Ctrl+, | Settings |
| Ctrl+Q | Quit |
| F1 | Help |
| Up/Down | Command history |

## Supported TNCs

Generic TNC-2, Kantronics KPC-3/KAM/KAM-XL, AEA PK-232/PK-88, MFJ-1270/1278, SCS PTC-II/III/Tracker, TNC-Pi, and any TNC with a serial terminal interface.

## License

MIT — Andrés Ortiz, EA7HQL

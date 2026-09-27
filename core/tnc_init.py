"""
TNC startup handshake and initialization.

Runs in a background thread after the serial port is opened:
  1. Probe: Ctrl-C + CR and wait for the "cmd:" prompt at the configured settings.
  2. If there is no answer and the model supports autobaud (e.g. PK-232 without
     battery-backed RAM), send "*" at the target baud rate using the TNC's
     power-up word format (PK-232: 7 bits, even parity) so the TNC locks to it.
  3. If the TNC still does not answer, scan other baud rates / formats.
  4. Switch the TNC to 8 bits, no parity (and to the target baud if needed),
     reconfigure the local port and verify the prompt again.
  5. Send the user initialization commands one by one, waiting for "cmd:".
"""

import threading
import time

# Per-model handshake profiles.
#   autobaud:     bool - TNC autobauds on "*" after a cold start
#   boot_formats: list of (databits, parity) - word formats to try for autobaud
#   baud_cmd:     str or None - command that sets the terminal baud rate
#   to_8n1:       list of str - commands that switch the TNC to 8 bits / no parity
#   restart:      str or None - command needed for the above to take effect
#   kiss_exit:    bool - try the KISS exit sequence (C0 FF C0) if the probe fails
PROFILES = {
    "AEA / Timewave PK-232": {
        "autobaud": True, "boot_formats": [(7, "Even"), (8, "None")],
        "baud_cmd": "TBAUD", "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "AEA PK-88": {
        "autobaud": True, "boot_formats": [(7, "Even"), (8, "None")],
        "baud_cmd": "TBAUD", "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "Kantronics KAM / KAM+": {
        "autobaud": True, "boot_formats": [(8, "None"), (7, "Even")],
        "baud_cmd": "ABAUD", "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "Kantronics KAM-XL": {
        "autobaud": True, "boot_formats": [(8, "None"), (7, "Even")],
        "baud_cmd": "ABAUD", "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "Kantronics KPC-3 / KPC-3+": {
        "autobaud": True, "boot_formats": [(8, "None"), (7, "Even")],
        "baud_cmd": "ABAUD", "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "MFJ-1278 / MFJ-1278B": {
        "autobaud": True, "boot_formats": [(7, "Even"), (8, "None")],
        "baud_cmd": None, "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "MFJ-1270 / MFJ-1274": {
        "autobaud": False, "boot_formats": [(7, "Even"), (8, "None")],
        "baud_cmd": None, "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
    "Generic / TNC-2 Compatible": {
        "autobaud": False, "boot_formats": [(8, "None"), (7, "Even")],
        "baud_cmd": None, "to_8n1": ["AWLEN 8", "PARITY 0"],
        "restart": "RESTART", "kiss_exit": True,
    },
}
DEFAULT_PROFILE = {
    "autobaud": False, "boot_formats": [(8, "None")],
    "baud_cmd": None, "to_8n1": [], "restart": None, "kiss_exit": False,
}

SCAN_BAUDS = [9600, 19200, 4800, 2400, 1200, 300, 38400]
PROMPT = b"cmd:"


def get_profile(model):
    """
    Args:
        model: str - TNC model name

    Returns: dict - handshake profile (see PROFILES)
    """
    return PROFILES.get(model, DEFAULT_PROFILE)


class TncInitializer:
    """
    Background TNC handshake + init command sender.

    Args:
        serial: SerialHandler - open serial handler
        model: str - TNC model name
        target: dict - desired line params: baudrate (int), databits (int),
                parity (str), stopbits (float)
        init_commands: str - init commands, one per line. "{CALL}" is replaced by
                       the callsign (lines using it are skipped if empty).
                       "@WAIT ms" pauses; lines starting with "#" are comments.
        callsign: str - station callsign
        do_handshake: bool - run probe/autobaud/scan before sending init commands
        on_status: callable(str, str) - (message, level) level in "info","ok","warn","error"
        on_done: callable(bool) - called at the end with success flag
    """

    def __init__(self, serial, model, target, init_commands="", callsign="",
                 do_handshake=True, on_status=None, on_done=None):
        self._ser = serial
        self._model = model
        self._profile = get_profile(model)
        self._target = target
        self._init = init_commands or ""
        self._call = (callsign or "").strip().upper()
        self._do_handshake = do_handshake
        self._on_status = on_status
        self._on_done = on_done
        # _buf: bytearray - RX bytes captured since last clear (masked to 7 bits, lowercase)
        self._buf = bytearray()
        self._buf_lock = threading.Lock()
        self._rx_event = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------ API

    def start(self):
        """Starts the handshake/init thread."""
        self._ser.add_listener(self._on_rx)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Requests the thread to stop as soon as possible."""
        self._stop.set()
        self._rx_event.set()

    def is_running(self):
        """Returns: bool - True while the thread is alive."""
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------ internals

    def _on_rx(self, data):
        """
        Serial listener: stores received bytes (7-bit masked, lowercase).

        Args:
            data: bytes - received chunk
        """
        cleaned = bytes(b & 0x7F for b in data).lower()
        with self._buf_lock:
            self._buf.extend(cleaned)
            if len(self._buf) > 4096:
                del self._buf[:-2048]
        self._rx_event.set()

    def _clear(self):
        """Discards captured RX data."""
        with self._buf_lock:
            self._buf.clear()
        self._rx_event.clear()

    def _snapshot(self):
        """Returns: bytes - copy of captured RX data."""
        with self._buf_lock:
            return bytes(self._buf)

    def _wait_for(self, patterns, timeout):
        """
        Waits until any pattern appears in the captured RX data.

        Args:
            patterns: list of bytes - lowercase patterns
            timeout: float - seconds

        Returns: bytes or None - matched pattern, or None on timeout/stop
        """
        end = time.monotonic() + timeout
        while not self._stop.is_set():
            buf = self._snapshot()
            for p in patterns:
                if p in buf:
                    return p
            remaining = end - time.monotonic()
            if remaining <= 0:
                return None
            self._rx_event.wait(min(remaining, 0.1))
            self._rx_event.clear()
        return None

    def _wait_quiet(self, quiet=0.4, maximum=3.0):
        """
        Waits until no data has been received for `quiet` seconds.

        Args:
            quiet: float - silence interval in seconds
            maximum: float - maximum total wait in seconds
        """
        end = time.monotonic() + maximum
        last_len = -1
        last_change = time.monotonic()
        while time.monotonic() < end and not self._stop.is_set():
            n = len(self._snapshot())
            if n != last_len:
                last_len = n
                last_change = time.monotonic()
            elif time.monotonic() - last_change >= quiet:
                return
            time.sleep(0.05)

    def _status(self, msg, level="info"):
        """
        Reports progress.

        Args:
            msg: str - message
            level: str - "info", "ok", "warn", "error"
        """
        if self._on_status:
            self._on_status(msg, level)

    def _send(self, data):
        """
        Sends str/bytes to the TNC.

        Args:
            data: str or bytes
        """
        self._ser.send(data)

    def _command(self, cmd, timeout=2.0):
        """
        Sends a command line and waits for the prompt.

        Args:
            cmd: str - command without terminator
            timeout: float - seconds to wait for "cmd:"

        Returns: tuple (bool, bytes) - (prompt seen, captured response)
        """
        self._clear()
        self._send(cmd + "\r")
        ok = self._wait_for([PROMPT], timeout) is not None
        return ok, self._snapshot()

    def _probe(self, timeout=1.5):
        """
        Checks whether the TNC answers with "cmd:" at current port settings.

        Args:
            timeout: float - seconds to wait

        Returns: bool - True if the prompt was received
        """
        self._clear()
        self._send(b"\x03")
        time.sleep(0.15)
        self._send(b"\r")
        return self._wait_for([PROMPT], timeout) is not None

    def _autobaud(self, databits, parity):
        """
        Sends "*" at the target baud rate with the given word format.

        Args:
            databits: int - 7 or 8
            parity: str - parity name

        Returns: bool - True if the TNC answered and reached the "cmd:" prompt
        """
        self._ser.reconfigure(baudrate=self._target["baudrate"], databits=databits,
                              parity=parity, stopbits=1)
        time.sleep(0.2)
        for attempt in range(2):
            if self._stop.is_set():
                return False
            self._clear()
            self._send(b"*")
            hit = self._wait_for([PROMPT, b"callsign", b"call sign"], 2.5)
            if hit is None and not self._snapshot().strip():
                # No answer at all: try again
                continue
            if hit in (b"callsign", b"call sign"):
                call = self._call or "NOCALL"
                self._status(f"TNC asks for callsign, sending {call}")
                self._clear()
                self._send(call + "\r")
                hit = self._wait_for([PROMPT], 4.0)
            if hit != PROMPT:
                self._wait_quiet()
                if self._probe(2.0):
                    hit = PROMPT
            if hit == PROMPT:
                return True
        return False

    def _switch_to_target(self, cur_baud, cur_bits, cur_parity):
        """
        Moves the TNC from its current format/baud to the target (8N1 @ target baud).

        Args:
            cur_baud: int - current baud rate
            cur_bits: int - current data bits
            cur_parity: str - current parity name

        Returns: bool - True if the TNC answers at target settings
        """
        t = self._target
        need_fmt = (cur_bits, cur_parity) != (t["databits"], t["parity"])
        need_baud = cur_baud != t["baudrate"]
        if not need_fmt and not need_baud:
            return True
        p = self._profile
        if need_baud and not p["baud_cmd"]:
            self._status(f"TNC answers at {cur_baud} bd but this model has no baud "
                         f"command; set the port to {cur_baud} bd", "warn")
            return False
        if need_fmt:
            for c in p["to_8n1"]:
                self._command(c)
        if need_baud:
            self._command(f"{p['baud_cmd']} {t['baudrate']}")
        if p["restart"]:
            self._clear()
            self._send(p["restart"] + "\r")
            time.sleep(0.3)
        self._ser.reconfigure(baudrate=t["baudrate"], databits=t["databits"],
                              parity=t["parity"], stopbits=t.get("stopbits", 1))
        self._wait_quiet(0.6, 5.0)
        for _ in range(3):
            if self._probe(2.0):
                return True
        return False

    def _handshake(self):
        """
        Full detection sequence. Leaves the port at target settings on success.

        Returns: bool - True if the TNC answers with "cmd:" at target settings
        """
        t = self._target
        p = self._profile

        self._status("Probing TNC...")
        if self._probe():
            self._status("TNC answered at configured settings", "ok")
            return True

        if p["kiss_exit"]:
            self._send(b"\xc0\xff\xc0")
            time.sleep(0.5)
            if self._probe():
                self._status("TNC was in KISS mode, now in command mode", "ok")
                return True

        if p["autobaud"]:
            for bits, parity in p["boot_formats"]:
                self._status(f"Autobaud: sending '*' at {t['baudrate']} bd "
                             f"{bits}{parity[0]}1...")
                if self._autobaud(bits, parity):
                    self._status(f"TNC locked at {t['baudrate']} bd {bits}{parity[0]}1", "ok")
                    if self._switch_to_target(t["baudrate"], bits, parity):
                        return True
                    self._status("TNC did not answer after switching to 8N1", "warn")
                if self._stop.is_set():
                    return False

        self._status("Scanning baud rates...")
        for baud in [t["baudrate"]] + [b for b in SCAN_BAUDS if b != t["baudrate"]]:
            for bits, parity in [(8, "None"), (7, "Even")]:
                if self._stop.is_set():
                    return False
                if (baud, bits, parity) == (t["baudrate"], t["databits"], t["parity"]):
                    continue
                self._ser.reconfigure(baudrate=baud, databits=bits, parity=parity,
                                      stopbits=1)
                time.sleep(0.1)
                if self._probe(1.0):
                    self._status(f"TNC found at {baud} bd {bits}{parity[0]}1", "ok")
                    if self._switch_to_target(baud, bits, parity):
                        return True
                    return False

        self._ser.reconfigure(baudrate=t["baudrate"], databits=t["databits"],
                              parity=t["parity"], stopbits=t.get("stopbits", 1))
        return False

    def _send_init_commands(self):
        """
        Sends init commands one per line waiting for the prompt between them.

        Returns: bool - True if every command got a prompt without an error reply
        """
        all_ok = True
        for raw in self._init.splitlines():
            if self._stop.is_set():
                return False
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.upper().startswith("@WAIT"):
                try:
                    time.sleep(int(line.split()[1]) / 1000.0)
                except (IndexError, ValueError):
                    pass
                continue
            if "{CALL}" in line:
                if not self._call:
                    self._status(f"Skipped '{line}' (no callsign configured)", "warn")
                    continue
                line = line.replace("{CALL}", self._call)
            ok, resp = self._command(line)
            if not ok:
                self._status(f"No prompt after '{line}'", "warn")
                all_ok = False
            elif b"?" in resp:
                self._status(f"TNC rejected '{line}'", "warn")
                all_ok = False
        return all_ok

    def _run(self):
        """Thread body: handshake + init commands. Always calls on_done."""
        success = False
        try:
            found = True
            if self._do_handshake:
                found = self._handshake()
                if not found:
                    self._status("TNC not detected (check cable, power and model)", "error")
            elif not self._probe():
                self._status("No 'cmd:' prompt, sending init commands anyway", "warn")
            if found and not self._stop.is_set():
                if self._init.strip():
                    self._status("Sending init commands...")
                    ok = self._send_init_commands()
                    self._status("Init commands sent" if ok else
                                 "Init finished with warnings", "ok" if ok else "warn")
                success = True
        except Exception as e:
            self._status(f"Init error: {e}", "error")
        finally:
            self._ser.remove_listener(self._on_rx)
            if self._on_done:
                self._on_done(success)

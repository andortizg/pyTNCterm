import threading
import queue

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


PARITY_NAMES = ("None", "Even", "Odd", "Mark", "Space")


class SerialHandler:
    """
    Manages serial port communication in a background thread.
    Data received is placed in a queue for the GUI to consume and, optionally,
    passed to registered listeners (used by the TNC initializer to wait for prompts).

    Attributes:
        rx_queue: queue.Queue - items are tuples ("data", bytes) or ("__DISCONNECTED__", None)
        is_connected: bool - whether the port is currently open
    """

    def __init__(self):
        # rx_queue: queue.Queue - incoming data from serial port
        self.rx_queue = queue.Queue()
        # _serial: serial.Serial or None - the serial port instance
        self._serial = None
        # _read_thread: threading.Thread or None - background reader thread
        self._read_thread = None
        # _running: bool - flag to control the reader thread
        self._running = False
        # is_connected: bool - connection status
        self.is_connected = False
        # _tx_bytes / _rx_bytes: int - byte counters
        self._tx_bytes = 0
        self._rx_bytes = 0
        # _tx_lock: threading.Lock - serializes writes from several threads
        self._tx_lock = threading.Lock()
        # _listeners: list of callable(bytes) - called from the reader thread
        self._listeners = []
        self._listeners_lock = threading.Lock()

    @staticmethod
    def list_ports():
        """
        Lists available serial ports on the system.

        Returns: list of str - port device names (e.g., ["COM3", "/dev/ttyUSB0"])
        """
        if not SERIAL_AVAILABLE:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def _map_params(databits, stopbits, parity):
        """
        Converts user-friendly values to pyserial constants.

        Args:
            databits: int - 7 or 8
            stopbits: int/float - 1, 1.5 or 2
            parity: str - "None", "Even", "Odd", "Mark", "Space"

        Returns: tuple (bytesize, stopbits, parity) - pyserial constants
        """
        parity_map = {
            "None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD, "Mark": serial.PARITY_MARK,
            "Space": serial.PARITY_SPACE,
        }
        stopbits_map = {
            1: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2: serial.STOPBITS_TWO,
        }
        bytesize = serial.SEVENBITS if int(databits) == 7 else serial.EIGHTBITS
        return (bytesize,
                stopbits_map.get(float(stopbits), serial.STOPBITS_ONE),
                parity_map.get(parity, serial.PARITY_NONE))

    def connect(self, port, baudrate=9600, databits=8, stopbits=1, parity="None",
                flow_control="None"):
        """
        Opens the serial port and starts the reader thread.

        Args:
            port: str - serial port name (e.g., "COM3", "/dev/ttyUSB0")
            baudrate: int - baud rate (300-115200)
            databits: int - data bits (7 or 8)
            stopbits: int/float - stop bits (1, 1.5, or 2)
            parity: str - "None", "Even", "Odd", "Mark", "Space"
            flow_control: str - "None", "RTS/CTS", "XON/XOFF"

        Returns: tuple (bool, str) - (success, message)
        """
        if not SERIAL_AVAILABLE:
            return False, "pyserial is not installed. Run: pip install pyserial"

        if self.is_connected:
            self.disconnect()

        try:
            bytesize, sbits, par = self._map_params(databits, stopbits, parity)
            self._serial = serial.Serial(
                port=port,
                baudrate=int(baudrate),
                bytesize=bytesize,
                stopbits=sbits,
                parity=par,
                timeout=0.05,
                write_timeout=10,
                rtscts=(flow_control == "RTS/CTS"),
                xonxoff=(flow_control == "XON/XOFF"),
            )
            # Keep DTR/RTS asserted: many TNCs need them to talk to the terminal
            try:
                self._serial.dtr = True
                if flow_control != "RTS/CTS":
                    self._serial.rts = True
            except Exception:
                pass
            self.is_connected = True
            self._tx_bytes = 0
            self._rx_bytes = 0
            self._running = True
            self._read_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._read_thread.start()
            return True, f"Connected to {port}"
        except Exception as e:
            self.is_connected = False
            self._serial = None
            return False, str(e)

    def reconfigure(self, baudrate=None, databits=None, parity=None, stopbits=None):
        """
        Changes line parameters of the open port without closing it.
        Only the arguments that are not None are changed.

        Args:
            baudrate: int or None - new baud rate
            databits: int or None - 7 or 8
            parity: str or None - "None", "Even", "Odd", "Mark", "Space"
            stopbits: int/float or None - 1, 1.5 or 2

        Returns: bool - True if applied
        """
        if not self._serial:
            return False
        try:
            cur_db = 7 if self._serial.bytesize == serial.SEVENBITS else 8
            bytesize, sbits, par = self._map_params(
                databits if databits is not None else cur_db,
                stopbits if stopbits is not None else 1,
                parity if parity is not None else "None")
            with self._tx_lock:
                if baudrate is not None:
                    self._serial.baudrate = int(baudrate)
                if databits is not None:
                    self._serial.bytesize = bytesize
                if parity is not None:
                    self._serial.parity = par
                if stopbits is not None:
                    self._serial.stopbits = sbits
                self._serial.reset_input_buffer()
            return True
        except Exception:
            return False

    def get_line_params(self):
        """
        Returns: dict with keys baudrate (int), databits (int), parity (str),
                 stopbits (float) of the open port, or {} if closed
        """
        if not self._serial:
            return {}
        par_rev = {serial.PARITY_NONE: "None", serial.PARITY_EVEN: "Even",
                   serial.PARITY_ODD: "Odd", serial.PARITY_MARK: "Mark",
                   serial.PARITY_SPACE: "Space"}
        return {
            "baudrate": self._serial.baudrate,
            "databits": 7 if self._serial.bytesize == serial.SEVENBITS else 8,
            "parity": par_rev.get(self._serial.parity, "None"),
            "stopbits": float(self._serial.stopbits),
        }

    def disconnect(self):
        """
        Stops the reader thread and closes the serial port.

        Returns: tuple (bool, str) - (success, message)
        """
        self._running = False
        if self._read_thread and self._read_thread.is_alive() \
                and self._read_thread is not threading.current_thread():
            self._read_thread.join(timeout=2.0)
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self.is_connected = False
        return True, "Disconnected"

    def send(self, data):
        """
        Sends data through the serial port.

        Args:
            data: str or bytes - data to send. Strings are encoded to latin-1.

        Returns: bool - True if sent successfully
        """
        if isinstance(data, str):
            data = data.encode("latin-1", errors="replace")
        return self.send_bytes(data)

    def send_bytes(self, data):
        """
        Sends raw bytes through the serial port (thread-safe).

        Args:
            data: bytes - raw bytes to send

        Returns: bool - True if sent successfully
        """
        if not self.is_connected or not self._serial:
            return False
        try:
            with self._tx_lock:
                self._serial.write(data)
            self._tx_bytes += len(data)
            return True
        except Exception:
            self._signal_lost()
            return False

    def flush_tx(self, timeout=None):
        """
        Blocks until the OS output buffer has been transmitted.

        Args:
            timeout: float or None - ignored by pyserial on most platforms (kept for API symmetry)

        Returns: bool - True if flushed
        """
        if not self._serial:
            return False
        try:
            self._serial.flush()
            return True
        except Exception:
            return False

    def send_break(self, duration=0.25):
        """
        Sends a serial BREAK signal.

        Args:
            duration: float - break duration in seconds (default 0.25)

        Returns: bool - True if sent successfully
        """
        if not self.is_connected or not self._serial:
            return False
        try:
            with self._tx_lock:
                self._serial.send_break(duration=duration)
            return True
        except Exception:
            self._signal_lost()
            return False

    def add_listener(self, callback):
        """
        Registers a function that receives every chunk of RX data (reader thread).

        Args:
            callback: callable(bytes) - must be fast and thread-safe
        """
        with self._listeners_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback):
        """
        Unregisters a listener previously added with add_listener.

        Args:
            callback: callable(bytes)
        """
        with self._listeners_lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _signal_lost(self):
        """Marks the connection as lost and notifies the GUI (only once)."""
        if self.is_connected:
            self.is_connected = False
            self.rx_queue.put(("__DISCONNECTED__", None))

    def _reader_loop(self):
        """
        Background thread loop: reads all pending bytes and enqueues them.
        Puts tuples of ("data", bytes) or ("__DISCONNECTED__", None) into rx_queue.
        """
        ser = self._serial
        while self._running and ser and ser.is_open:
            try:
                data = ser.read(ser.in_waiting or 1)
            except Exception:
                if self._running:
                    self._signal_lost()
                break
            if data:
                self._rx_bytes += len(data)
                self.rx_queue.put(("data", data))
                with self._listeners_lock:
                    listeners = list(self._listeners)
                for cb in listeners:
                    try:
                        cb(data)
                    except Exception:
                        pass

    def get_stats(self):
        """
        Returns: dict with keys "tx_bytes" (int) and "rx_bytes" (int)
        """
        return {"tx_bytes": self._tx_bytes, "rx_bytes": self._rx_bytes}

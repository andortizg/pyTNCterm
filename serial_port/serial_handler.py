import threading
import queue
import time

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class SerialHandler:
    """
    Manages serial port communication in a background thread.
    Data received is placed in a queue for the GUI to consume.
    
    Attributes:
        rx_queue: queue.Queue - received data (bytes) from the serial port
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
        # _tx_bytes: int - total bytes transmitted
        self._tx_bytes = 0
        # _rx_bytes: int - total bytes received
        self._rx_bytes = 0

    @staticmethod
    def list_ports():
        """
        Lists available serial ports on the system.
        
        Returns: list of str - port device names (e.g., ["COM3", "/dev/ttyUSB0"])
        """
        if not SERIAL_AVAILABLE:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port, baudrate=9600, databits=8, stopbits=1, parity="None", flow_control="None"):
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

        parity_map = {
            "None": serial.PARITY_NONE,
            "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD,
            "Mark": serial.PARITY_MARK,
            "Space": serial.PARITY_SPACE,
        }

        stopbits_map = {
            1: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2: serial.STOPBITS_TWO,
        }

        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=databits,
                stopbits=stopbits_map.get(stopbits, serial.STOPBITS_ONE),
                parity=parity_map.get(parity, serial.PARITY_NONE),
                timeout=0.1,
                rtscts=(flow_control == "RTS/CTS"),
                xonxoff=(flow_control == "XON/XOFF"),
            )
            self.is_connected = True
            self._tx_bytes = 0
            self._rx_bytes = 0
            self._running = True
            self._read_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._read_thread.start()
            return True, f"Connected to {port}"
        except Exception as e:
            self.is_connected = False
            return False, str(e)

    def disconnect(self):
        """
        Stops the reader thread and closes the serial port.
        
        Returns: tuple (bool, str) - (success, message)
        """
        self._running = False
        if self._read_thread and self._read_thread.is_alive():
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
        if not self.is_connected or not self._serial:
            return False
        try:
            if isinstance(data, str):
                data = data.encode("latin-1", errors="replace")
            self._serial.write(data)
            self._tx_bytes += len(data)
            return True
        except Exception:
            self.is_connected = False
            self.rx_queue.put(("__DISCONNECTED__", None))
            return False

    def send_bytes(self, data):
        """
        Sends raw bytes through the serial port (for control characters).

        Args:
            data: bytes - raw bytes to send

        Returns: bool - True if sent successfully
        """
        if not self.is_connected or not self._serial:
            return False
        try:
            self._serial.write(data)
            self._tx_bytes += len(data)
            return True
        except Exception:
            self.is_connected = False
            self.rx_queue.put(("__DISCONNECTED__", None))
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
            self._serial.send_break(duration=duration)
            return True
        except Exception:
            self.is_connected = False
            self.rx_queue.put(("__DISCONNECTED__", None))
            return False

    def _reader_loop(self):
        """
        Background thread loop: reads bytes from serial port and enqueues them.
        Puts tuples of ("data", bytes) or ("__DISCONNECTED__", None) into rx_queue.
        """
        while self._running and self._serial and self._serial.is_open:
            try:
                data = self._serial.read(256)
                if data:
                    self._rx_bytes += len(data)
                    self.rx_queue.put(("data", data))
            except Exception:
                if self._running:
                    self.is_connected = False
                    self.rx_queue.put(("__DISCONNECTED__", None))
                break
            time.sleep(0.01)

    def get_stats(self):
        """
        Returns: dict with keys "tx_bytes" (int) and "rx_bytes" (int)
        """
        return {"tx_bytes": self._tx_bytes, "rx_bytes": self._rx_bytes}

"""
YAPP (Yet Another Packet Protocol) File Transfer Handler
Implements YAPP protocol per WA7MBL spec Rev 1.1 (06/23/86)
with YappC checksum extension (FC1EBN / F6FBB 5.14) and Resume.

Protocol packet types (all start with type byte + length/subtype byte):
  SI  Send_Init     ENQ  01
  RR  Rcv_Rdy       ACK  01
  RF  Rcv_File      ACK  02
  AF  Ack_EOF       ACK  03   [Rev 1.1]
  AT  Ack_EOT       ACK  04   [Rev 1.1]
  CA  Can_Ack       ACK  05
  RT  Rcv_TPK       ACK  ACK  (YappC: data blocks carry a checksum byte)
  HD  Send_Hdr      SOH  len  (Filename) NUL (FileSize ASCII) NUL [(Date/Time) NUL]
  DT  Send_Data     STX  len  (Data) [Checksum]  {len=0 means 256 bytes}
  EF  Send_EOF      ETX  01
  ET  Send_EOT      EOT  01
  NR  Not_Rdy       NAK  len  (Reason ASCII)
  RE  Resume        NAK  len  R NUL (ReceivedSize ASCII) NUL [C NUL]
  CN  Cancel        CAN  len  (Reason ASCII)
  TX  Text          DLE  len  (ASCII text for display)

IMPORTANT: YAPP is binary. The TNC must be in transparent mode (TRANS) and
the serial link should use hardware flow control (RTS/CTS).

Threading: process_data() is called from the GUI thread, the crash timer and the
data sender run in their own threads. All callbacks may be invoked from any
thread; the caller must marshal them to the GUI thread.
"""
import os
import time
import threading
from enum import Enum, auto


class YappState(Enum):
    """
    Estados de la máquina de estados YAPP.
    Sender: IDLE -> S_INIT -> S_HEADER -> S_DATA -> S_EOF -> S_EOT -> DONE
    Receiver: IDLE -> R_WAIT -> R_HEADER -> R_DATA -> (R_HEADER ...) -> DONE
    """
    IDLE = auto()
    S_INIT = auto()
    S_HEADER = auto()
    S_DATA = auto()
    S_EOF = auto()
    S_EOT = auto()
    R_WAIT = auto()
    R_HEADER = auto()
    R_DATA = auto()
    DONE = auto()
    ERROR = auto()


class YappEvent(Enum):
    """Tipos de evento para el log de control del diálogo."""
    INFO = auto()
    SENT = auto()
    RECEIVED = auto()
    ERROR = auto()
    SUCCESS = auto()


# -- Protocol constants --
SOH = 0x01
STX = 0x02
ETX = 0x03
EOT = 0x04
ENQ = 0x05
ACK = 0x06
DLE = 0x10
NAK = 0x15
CAN = 0x18

MAX_DATA_LEN = 250        # Max data bytes per DT packet
CTRL_TIMEOUT_S = 60       # Crash timer for control exchanges (seconds)
RX_IDLE_TIMEOUT_S = 180   # Receiver: max silence between DT packets
RX_WAIT_TIMEOUT_S = 600   # Receiver: max wait for the sender's SI
MIN_EFF_BPS = 15          # Worst-case effective throughput (bytes/s) for EOF timer
MAX_SI_RETRIES = 5        # Max retries for initial SI
SI_RETRY_S = 20           # Interval between SI retries


def _safe_filename(name):
    """
    Removes any path component and illegal characters from a received filename.

    Args:
        name: str - filename from the HD packet

    Returns: str - sanitized filename (may be empty)
    """
    name = name.replace("\\", "/").split("/")[-1].strip()
    bad = '<>:"|?*'
    name = "".join("_" if (c in bad or ord(c) < 32) else c for c in name)
    return name.strip(". ")


def _unique_path(directory, filename):
    """
    Returns a path that does not overwrite an existing file (adds _1, _2...).

    Args:
        directory: str - target directory
        filename: str - desired filename

    Returns: str - full path
    """
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(filename)
    n = 1
    while os.path.exists(os.path.join(directory, f"{base}_{n}{ext}")):
        n += 1
    return os.path.join(directory, f"{base}_{n}{ext}")


class YappHandler:
    """
    Gestor de transferencias YAPP con máquina de estados completa.

    Args:
        send_raw: callable(bytes) -> bool - envía bytes crudos por el puerto serie
        on_progress: callable(int, int) - (bytes_transferred, total_bytes)
        on_event: callable(YappEvent, str) - mensajes de control
        on_finished: callable(bool, str) - al terminar (éxito, mensaje)
        block_delay_ms: int - pausa entre bloques DT (para TNCs sin control de flujo)
    """

    def __init__(self, send_raw=None, on_progress=None, on_event=None,
                 on_finished=None, block_delay_ms=0):
        self.send_raw = send_raw
        self.on_progress = on_progress
        self.on_event = on_event
        self.on_finished = on_finished
        self._block_delay = max(0, int(block_delay_ms)) / 1000.0

        self.state = YappState.IDLE
        self._rx_buf = bytearray()
        self._file_handle = None
        self._filename = ""
        self._file_path = ""
        self._file_size = 0
        self._bytes_transferred = 0
        self._download_dir = ""
        self._timer = None
        self._si_retries = 0
        self._yappc = False          # True: DT packets carry checksum
        self._sender_thread = None
        self._lock = threading.RLock()

    # ========================================================================
    # Public API
    # ========================================================================

    def start_send(self, filepath):
        """
        Inicia envío de archivo.

        Args:
            filepath: str - ruta completa del archivo

        Returns:
            tuple(bool, str) - (éxito, mensaje)
        """
        with self._lock:
            if self.state != YappState.IDLE:
                return False, "Transfer already in progress"
            if not os.path.isfile(filepath):
                return False, f"File not found: {filepath}"
            try:
                self._filename = os.path.basename(filepath)
                self._file_path = filepath
                self._file_size = os.path.getsize(filepath)
                self._file_handle = open(filepath, 'rb')
                self._bytes_transferred = 0
                self._si_retries = 0
                self._yappc = False
                self._rx_buf.clear()
                self.state = YappState.S_INIT
                self._log(YappEvent.INFO,
                          f"Starting send: {self._filename} ({self._file_size} bytes)")
                self._send_si()
                return True, f"Sending {self._filename}"
            except Exception as e:
                self._reset()
                return False, f"Error: {e}"

    def start_receive(self, download_dir):
        """
        Prepara para recibir archivo.

        Args:
            download_dir: str - directorio destino

        Returns:
            tuple(bool, str) - (éxito, mensaje)
        """
        with self._lock:
            if self.state != YappState.IDLE:
                return False, "Transfer already in progress"
            try:
                os.makedirs(download_dir, exist_ok=True)
            except OSError as e:
                return False, f"Cannot use download directory: {e}"
            self._download_dir = download_dir
            self._rx_buf.clear()
            self._bytes_transferred = 0
            self._filename = ""
            self._file_size = 0
            self._yappc = False
            self.state = YappState.R_WAIT
            self._log(YappEvent.INFO, "Waiting for sender (SI)...")
            self._start_timer(RX_WAIT_TIMEOUT_S)
            return True, "Waiting for file transfer"

    def process_data(self, data):
        """
        Procesa bytes crudos recibidos del puerto serie.

        Args:
            data: bytes - datos recibidos
        """
        with self._lock:
            if not self.is_active():
                return
            self._rx_buf.extend(data)
            self._process_buffer()

    def cancel(self):
        """Cancela la transferencia en curso (envía CN)."""
        with self._lock:
            if not self.is_active():
                return
            self._send_cancel("Cancelled by user")
            self._finish(False, "Transfer cancelled by user")

    def abort(self, message="Aborted"):
        """
        Termina la transferencia sin enviar nada (p.ej. puerto cerrado).

        Args:
            message: str - motivo
        """
        with self._lock:
            if self.is_active():
                self._finish(False, message)

    def is_active(self):
        """
        Returns:
            bool - True si hay transferencia activa
        """
        return self.state not in (YappState.IDLE, YappState.DONE, YappState.ERROR)

    @property
    def filename(self):
        return self._filename

    @property
    def file_size(self):
        return self._file_size

    @property
    def bytes_transferred(self):
        return self._bytes_transferred

    # ========================================================================
    # Protocol packet builders
    # ========================================================================

    def _send_si(self):
        """Envía SI (Send Init): ENQ 01"""
        self._send_packet(bytes([ENQ, 0x01]))
        self._log(YappEvent.SENT, "SI (Send Init)")
        self._start_timer(SI_RETRY_S)

    def _send_header(self):
        """Envía HD (Send Header): SOH len filename NUL filesize NUL"""
        name = self._filename.encode('ascii', errors='replace')[:200]
        payload = name + b'\x00' + str(self._file_size).encode('ascii') + b'\x00'
        self._send_packet(bytes([SOH, len(payload)]) + payload)
        self._log(YappEvent.SENT,
                  f"HD (Header) file={self._filename} size={self._file_size}")
        self.state = YappState.S_HEADER
        self._start_timer(CTRL_TIMEOUT_S)

    def _send_eof(self):
        """Envía EF (Send EOF): ETX 01. Timer scales with file size."""
        self._send_packet(bytes([ETX, 0x01]))
        self._log(YappEvent.SENT, "EF (End of File)")
        self.state = YappState.S_EOF
        # The TNC may still be transmitting buffered data over the air
        self._start_timer(CTRL_TIMEOUT_S + self._file_size / MIN_EFF_BPS)

    def _send_eot(self):
        """Envía ET (Send EOT): EOT 01"""
        self._send_packet(bytes([EOT, 0x01]))
        self._log(YappEvent.SENT, "ET (End of Transmission)")
        self.state = YappState.S_EOT
        self._start_timer(CTRL_TIMEOUT_S)

    def _send_ctrl(self, code, name):
        """
        Envía un paquete ACK de control.

        Args:
            code: int - subtipo (0x01 RR, 0x02 RF, 0x03 AF, 0x04 AT, 0x05 CA)
            name: str - texto para el log
        """
        self._send_packet(bytes([ACK, code]))
        self._log(YappEvent.SENT, name)

    def _send_nr(self, reason=""):
        """
        Envía NR (Not Ready): NAK len reason

        Args:
            reason: str - motivo del rechazo
        """
        payload = reason.encode('ascii', errors='replace')[:255]
        self._send_packet(bytes([NAK, len(payload)]) + payload)
        self._log(YappEvent.SENT, f"NR (Not Ready) {reason}")

    def _send_cancel(self, reason=""):
        """
        Envía CN (Cancel): CAN len reason

        Args:
            reason: str - motivo de cancelación
        """
        payload = reason.encode('ascii', errors='replace')[:255]
        self._send_packet(bytes([CAN, len(payload)]) + payload)
        self._log(YappEvent.SENT, f"CN (Cancel) {reason}")

    # ========================================================================
    # Buffer processing / State machine
    # ========================================================================

    def _process_buffer(self):
        """Procesa el buffer de recepción según el estado actual."""
        while len(self._rx_buf) >= 2 and self.is_active():
            first = self._rx_buf[0]
            second = self._rx_buf[1]

            # -- Cancel from remote at any time --
            if first == CAN:
                if len(self._rx_buf) < 2 + second:
                    return
                reason = bytes(self._rx_buf[2:2 + second]).decode('ascii', 'replace')
                del self._rx_buf[:2 + second]
                self._log(YappEvent.RECEIVED, f"CN (Cancel) {reason}")
                self._send_ctrl(0x05, "CA (Cancel Ack)")
                self._finish(False, f"Cancelled by remote: {reason}")
                return

            # -- Text from remote at any time (except inside data) --
            if first == DLE and self.state != YappState.R_DATA:
                if len(self._rx_buf) < 2 + second:
                    return
                text = bytes(self._rx_buf[2:2 + second]).decode('ascii', 'replace')
                del self._rx_buf[:2 + second]
                self._log(YappEvent.RECEIVED, f"TX: {text}")
                continue

            if self.state in (YappState.S_INIT, YappState.S_HEADER, YappState.S_DATA,
                              YappState.S_EOF, YappState.S_EOT):
                consumed = self._process_sender_response(first, second)
            elif self.state in (YappState.R_WAIT, YappState.R_HEADER):
                consumed = self._process_receiver_control(first, second)
            elif self.state == YappState.R_DATA:
                consumed = self._process_receiver_data(first, second)
            else:
                self._rx_buf.clear()
                return

            if not consumed:
                return  # Need more data

    def _process_sender_response(self, first, second):
        """
        Procesa respuestas mientras estamos enviando.

        Args:
            first: int - primer byte del paquete
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes del buffer
        """
        if first == ACK:
            del self._rx_buf[:2]
            st = self.state

            if second == 0x01:  # RR
                self._log(YappEvent.RECEIVED, "RR (Receive Ready)")
                if st == YappState.S_INIT:
                    self._cancel_timer()
                    self._send_header()
            elif second in (0x02, ACK):  # RF / RT (YappC)
                if second == ACK:
                    self._log(YappEvent.RECEIVED, "RT (Receive, YappC checksum)")
                    self._yappc = True
                else:
                    self._log(YappEvent.RECEIVED, "RF (Receive File)")
                if st in (YappState.S_INIT, YappState.S_HEADER):
                    self._cancel_timer()
                    self._start_data(0)
            elif second == 0x03:  # AF
                self._log(YappEvent.RECEIVED, "AF (Ack End of File)")
                if st == YappState.S_EOF:
                    self._cancel_timer()
                    self._send_eot()
            elif second == 0x04:  # AT
                self._log(YappEvent.RECEIVED, "AT (Ack End of Transmission)")
                if st == YappState.S_EOT:
                    self._finish(True, f"File sent successfully: {self._filename}")
            elif second == 0x05:  # CA
                self._log(YappEvent.RECEIVED, "CA (Cancel Ack)")
                self._finish(False, "Transfer cancelled")
            else:
                self._log(YappEvent.INFO, f"Ignored ACK {second:02X}")
            return True

        if first == NAK:
            if len(self._rx_buf) < 2 + second:
                return False
            payload = bytes(self._rx_buf[2:2 + second])
            del self._rx_buf[:2 + second]
            if payload[:2] == b'R\x00' and self.state == YappState.S_HEADER:
                self._handle_resume(payload)
            else:
                reason = payload.decode('ascii', errors='replace')
                self._log(YappEvent.RECEIVED, f"NR (Not Ready) {reason}")
                self._finish(False, f"Remote not ready: {reason}")
            return True

        # Unexpected byte (noise, TNC message) - discard
        del self._rx_buf[:1]
        return True

    def _handle_resume(self, payload):
        """
        Procesa RE (Resume): R NUL size NUL [C NUL]. Continúa desde el offset pedido.

        Args:
            payload: bytes - contenido del paquete NAK
        """
        parts = payload.split(b'\x00')
        try:
            offset = int(parts[1].decode('ascii'))
        except (IndexError, ValueError):
            offset = 0
        if len(parts) > 2 and parts[2] == b'C':
            self._yappc = True
        if offset < 0 or offset > self._file_size:
            offset = 0
        self._log(YappEvent.RECEIVED, f"RE (Resume) from byte {offset}")
        self._cancel_timer()
        self._start_data(offset)

    def _process_receiver_control(self, first, second):
        """
        Procesa paquetes de control en modo receptor (R_WAIT, R_HEADER).

        Args:
            first: int - primer byte
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes
        """
        if first == ENQ and second == 0x01:  # SI (also duplicated SI)
            del self._rx_buf[:2]
            self._log(YappEvent.RECEIVED, "SI (Send Init)")
            self._send_ctrl(0x01, "RR (Receive Ready)")
            self.state = YappState.R_HEADER
            self._start_timer(CTRL_TIMEOUT_S)
            return True

        if first == SOH and self.state == YappState.R_HEADER:
            if len(self._rx_buf) < 2 + second:
                return False
            payload = bytes(self._rx_buf[2:2 + second])
            del self._rx_buf[:2 + second]
            self._parse_header(payload)
            return True

        if first == EOT and second == 0x01:  # ET
            del self._rx_buf[:2]
            self._log(YappEvent.RECEIVED, "ET (End of Transmission)")
            self._send_ctrl(0x04, "AT (Ack End of Transmission)")
            self._finish(True, "Transfer complete")
            return True

        del self._rx_buf[:1]
        return True

    def _process_receiver_data(self, first, second):
        """
        Procesa paquetes de datos en modo receptor (R_DATA).

        Args:
            first: int - primer byte
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes
        """
        if first == STX:
            length = second if second != 0 else 256
            extra = 1 if self._yappc else 0
            if len(self._rx_buf) < 2 + length + extra:
                return False
            data = bytes(self._rx_buf[2:2 + length])
            if extra:
                chk = self._rx_buf[2 + length]
                if (sum(data) & 0xFF) != chk:
                    del self._rx_buf[:2 + length + extra]
                    self._send_cancel("Checksum error")
                    self._finish(False, "Checksum error in data block")
                    return True
            del self._rx_buf[:2 + length + extra]
            try:
                self._file_handle.write(data)
            except Exception as e:
                self._send_cancel("Write error")
                self._finish(False, f"File write error: {e}")
                return True
            self._bytes_transferred += length
            self._update_progress()
            self._start_timer(RX_IDLE_TIMEOUT_S)
            return True

        if first == ETX and second == 0x01:  # EF
            del self._rx_buf[:2]
            self._log(YappEvent.RECEIVED, "EF (End of File)")
            self._close_file()
            self._send_ctrl(0x03, "AF (Ack End of File)")
            if self._file_size and self._bytes_transferred != self._file_size:
                self._log(YappEvent.ERROR,
                          f"Size mismatch: got {self._bytes_transferred}, "
                          f"expected {self._file_size}")
            else:
                self._log(YappEvent.SUCCESS,
                          f"File received: {self._filename} "
                          f"({self._bytes_transferred} bytes)")
            self.state = YappState.R_HEADER
            self._start_timer(CTRL_TIMEOUT_S)
            return True

        if first == EOT and second == 0x01:  # ET without EF
            del self._rx_buf[:2]
            self._log(YappEvent.RECEIVED, "ET (End of Transmission)")
            self._close_file()
            self._send_ctrl(0x04, "AT (Ack End of Transmission)")
            self._finish(True, f"Received {self._filename} "
                               f"({self._bytes_transferred} bytes)")
            return True

        # Out of sync: discard one byte
        del self._rx_buf[:1]
        return True

    # ========================================================================
    # Header parsing
    # ========================================================================

    def _parse_header(self, payload):
        """
        Parsea el payload del header HD y abre el archivo destino.

        Args:
            payload: bytes - contenido tras SOH len
        """
        parts = payload.split(b'\x00')
        raw_name = parts[0].decode('latin-1', errors='replace') if parts else ""
        self._filename = _safe_filename(raw_name)
        try:
            self._file_size = int(parts[1].decode('ascii', errors='replace'))
        except (ValueError, IndexError):
            self._file_size = 0

        self._log(YappEvent.RECEIVED,
                  f"HD (Header) file={raw_name} size={self._file_size}")

        if not self._filename:
            self._send_nr("Invalid filename")
            self._finish(False, "Invalid filename in header")
            return

        filepath = _unique_path(self._download_dir, self._filename)
        try:
            self._file_handle = open(filepath, 'wb')
        except Exception as e:
            self._send_nr("Cannot create file")
            self._finish(False, f"Cannot create file: {e}")
            return
        self._file_path = filepath
        self._filename = os.path.basename(filepath)
        self._bytes_transferred = 0
        self._update_progress()
        self._send_ctrl(0x02, "RF (Receive File)")
        self.state = YappState.R_DATA
        self._start_timer(RX_IDLE_TIMEOUT_S)
        self._log(YappEvent.INFO, f"Receiving {self._filename}...")

    # ========================================================================
    # Data sender (background thread)
    # ========================================================================

    def _start_data(self, offset):
        """
        Pasa a S_DATA y lanza el hilo que envía los bloques DT.

        Args:
            offset: int - posición inicial en el archivo (resume)
        """
        try:
            self._file_handle.seek(offset)
        except Exception:
            offset = 0
            self._file_handle.seek(0)
        self._bytes_transferred = offset
        self.state = YappState.S_DATA
        self._log(YappEvent.INFO, "Sending data" + (" (YappC)" if self._yappc else "") + "...")
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

    def _sender_loop(self):
        """
        Envía bloques DT fuera del lock (para no bloquear la GUI) y termina con EF.
        Se detiene si el estado deja de ser S_DATA (cancelación).
        """
        while True:
            with self._lock:
                if self.state != YappState.S_DATA or not self._file_handle:
                    return
                data = self._file_handle.read(MAX_DATA_LEN)
                if not data:
                    self._close_file()
                    self._send_eof()
                    return
                pkt = bytes([STX, len(data) & 0xFF]) + data
                if self._yappc:
                    pkt += bytes([sum(data) & 0xFF])
            if not self._send_packet(pkt):
                with self._lock:
                    if self.state == YappState.S_DATA:
                        self._finish(False, "Serial write failed")
                return
            with self._lock:
                if self.state != YappState.S_DATA:
                    return
                self._bytes_transferred += len(data)
                self._update_progress()
            if self._block_delay:
                time.sleep(self._block_delay)

    # ========================================================================
    # Timer
    # ========================================================================

    def _start_timer(self, seconds):
        """
        Inicia (o reinicia) el crash timer.

        Args:
            seconds: float - tiempo hasta el timeout
        """
        self._cancel_timer()
        self._timer = threading.Timer(seconds, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self):
        """Cancela el crash timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self):
        """Callback cuando expira el crash timer (hilo del timer)."""
        with self._lock:
            if not self.is_active():
                return
            if self.state == YappState.S_INIT and self._si_retries < MAX_SI_RETRIES:
                self._si_retries += 1
                self._log(YappEvent.INFO,
                          f"Timeout, retrying SI ({self._si_retries}/{MAX_SI_RETRIES})...")
                self._send_si()
                return
            if self.state == YappState.S_DATA:
                return  # sender thread still running; no timer in this state
            self._send_cancel("Timeout")
            self._finish(False, "Timeout: no response from remote station")

    # ========================================================================
    # Helpers
    # ========================================================================

    def _send_packet(self, data):
        """
        Envía bytes crudos por el puerto serie.

        Args:
            data: bytes - paquete a enviar

        Returns: bool - resultado de send_raw (True si no hay send_raw)
        """
        if self.send_raw:
            return bool(self.send_raw(data))
        return True

    def _update_progress(self):
        """Notifica progreso al callback."""
        if self.on_progress:
            self.on_progress(self._bytes_transferred, self._file_size)

    def _log(self, event_type, message):
        """
        Registra evento de control.

        Args:
            event_type: YappEvent - tipo de evento
            message: str - mensaje descriptivo
        """
        if self.on_event:
            self.on_event(event_type, message)

    def _close_file(self):
        """Cierra el archivo abierto (si lo hay)."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

    def _finish(self, success, message):
        """
        Finaliza la transferencia.

        Args:
            success: bool - si fue exitosa
            message: str - mensaje final
        """
        self._cancel_timer()
        receiving_partial = (not success and self._file_handle is not None
                             and self.state == YappState.R_DATA)
        self._close_file()
        if receiving_partial:
            message += f" (partial file kept: {self._filename})"
        self.state = YappState.DONE if success else YappState.ERROR
        self._log(YappEvent.SUCCESS if success else YappEvent.ERROR, message)
        if self.on_finished:
            self.on_finished(success, message)

    def _reset(self):
        """Resetea todo el estado a IDLE."""
        self._cancel_timer()
        self._close_file()
        self._filename = ""
        self._file_size = 0
        self._bytes_transferred = 0
        self._rx_buf.clear()
        self._si_retries = 0
        self._yappc = False
        self.state = YappState.IDLE

    def reset_to_idle(self):
        """Resetea a IDLE (para reutilizar tras completar)."""
        with self._lock:
            self._reset()

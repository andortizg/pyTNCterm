"""
YAPP (Yet Another Packet Protocol) File Transfer Handler
Implements YAPP protocol per WA7MBL spec Rev 1.1 (06/23/86)
with YappC checksum extension (FC1EBN / F6FBB 5.14).

Protocol packet types (all start with type byte + length/subtype byte):
  SI  Send_Init     ENQ  01
  RR  Rcv_Rdy       ACK  01
  RF  Rcv_File      ACK  02
  AF  Ack_EOF       ACK  03   [Rev 1.1]
  AT  Ack_EOT       ACK  04   [Rev 1.1]
  CA  Can_Ack       ACK  05
  RT  Rcv_TPK       ACK  ACK  (YappC extension)
  HD  Send_Hdr      SOH  len  (Filename) NUL (FileSize ASCII) NUL
  DT  Send_Data     STX  len  (Data)     {len=0 means 256 bytes}
  EF  Send_EOF      ETX  01
  ET  Send_EOT      EOT  01
  NR  Not_Rdy       NAK  len  (Reason ASCII)
  RE  Resume        NAK  len  R NUL (ReceivedSize ASCII) NUL
  CN  Cancel        CAN  len  (Reason ASCII)
  TX  Text          DLE  len  (ASCII text for display)
"""
import os
import time
import threading
from enum import Enum, auto


class YappState(Enum):
    """
    Estados de la máquina de estados YAPP.
    Sender: IDLE -> S -> SH -> SD -> SE -> ST -> DONE
    Receiver: IDLE -> R -> RH -> RD -> DONE
    """
    IDLE = auto()
    # Sender states
    S_INIT = auto()       # Sending SI, waiting for RR/RF/NR
    S_HEADER = auto()     # Sent HD, waiting for RF/NR/RE
    S_DATA = auto()       # Sending DT packets
    S_EOF = auto()        # Sent EF, waiting for AF
    S_EOT = auto()        # Sent ET, waiting for AT
    # Receiver states
    R_WAIT = auto()       # Waiting for SI from sender
    R_HEADER = auto()     # Sent RR, waiting for HD/ET
    R_DATA = auto()       # Sent RF, receiving DT packets
    # Terminal states
    DONE = auto()
    ERROR = auto()
    CW_WAIT = auto()      # Cancel Wait - sent CN, waiting for CA


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

MAX_DATA_LEN = 250       # Max data bytes per DT packet (conservative)
TIMEOUT_S = 30            # Crash timer (seconds)
MAX_SI_RETRIES = 5        # Max retries for initial SI


class YappHandler:
    """
    Gestor de transferencias YAPP con máquina de estados completa.

    Args:
        send_raw: callable(bytes) -> bool - envía bytes crudos por el puerto serie
        on_progress: callable(int, int) - callback (bytes_transferred, total_bytes)
        on_event: callable(YappEvent, str) - callback para mensajes de control
        on_finished: callable(bool, str) - callback al terminar (éxito, mensaje)
        on_rx_data: callable(bytes) - callback para datos que NO son YAPP (passthrough)
    """

    def __init__(self, send_raw=None, on_progress=None, on_event=None,
                 on_finished=None, on_rx_data=None):
        # Callbacks
        self.send_raw = send_raw
        self.on_progress = on_progress
        self.on_event = on_event
        self.on_finished = on_finished
        self.on_rx_data = on_rx_data

        # State
        self.state = YappState.IDLE
        self._rx_buf = bytearray()
        self._file_handle = None
        self._filename = ""
        self._file_size = 0
        self._bytes_transferred = 0
        self._download_dir = ""
        self._timer = None
        self._si_retries = 0
        self._lock = threading.Lock()

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
            if not os.path.exists(filepath):
                return False, f"File not found: {filepath}"

            try:
                self._filename = os.path.basename(filepath)
                self._file_size = os.path.getsize(filepath)
                self._file_handle = open(filepath, 'rb')
                self._bytes_transferred = 0
                self._si_retries = 0
                self.state = YappState.S_INIT
                self._rx_buf.clear()

                self._log(YappEvent.INFO, f"Starting send: {self._filename} ({self._file_size} bytes)")
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

            os.makedirs(download_dir, exist_ok=True)
            self._download_dir = download_dir
            self._rx_buf.clear()
            self._bytes_transferred = 0
            self._filename = ""
            self._file_size = 0
            self.state = YappState.R_WAIT

            self._log(YappEvent.INFO, "Waiting for sender (SI)...")
            self._start_timer()
            return True, "Waiting for file transfer"

    def process_data(self, data):
        """
        Procesa bytes crudos recibidos del puerto serie.
        Debe ser llamado desde el polling loop de la GUI.

        Args:
            data: bytes - datos recibidos del serial
        """
        with self._lock:
            if self.state == YappState.IDLE:
                # Passthrough - not in YAPP mode
                if self.on_rx_data:
                    self.on_rx_data(data)
                return

            self._rx_buf.extend(data)
            self._process_buffer()

    def cancel(self):
        """Cancela la transferencia en curso."""
        with self._lock:
            if self.state in (YappState.IDLE, YappState.DONE, YappState.ERROR):
                return
            self._send_cancel("Cancelled by user")
            self._finish(False, "Transfer cancelled by user")

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
        self._start_timer()

    def _send_header(self):
        """Envía HD (Send Header): SOH len filename\\0 filesize\\0"""
        payload = self._filename.encode('ascii', errors='replace') + b'\x00'
        payload += str(self._file_size).encode('ascii') + b'\x00'
        pkt = bytes([SOH, len(payload)]) + payload
        self._send_packet(pkt)
        self._log(YappEvent.SENT, f"HD (Header) file={self._filename} size={self._file_size}")
        self.state = YappState.S_HEADER
        self._start_timer()

    def _send_data_block(self):
        """
        Envía un bloque DT (Send Data): STX len data.
        len=0 significa 256 bytes.

        Returns:
            bool - True si quedan más datos
        """
        if not self._file_handle:
            return False

        data = self._file_handle.read(MAX_DATA_LEN)
        if not data:
            return False

        length = len(data)
        # len byte: 0 means 256 (but we use MAX_DATA_LEN=250, so won't happen)
        len_byte = length if length < 256 else 0
        pkt = bytes([STX, len_byte]) + data
        self._send_packet(pkt)

        self._bytes_transferred += length
        self._update_progress()
        return True

    def _send_eof(self):
        """Envía EF (Send EOF): ETX 01"""
        self._send_packet(bytes([ETX, 0x01]))
        self._log(YappEvent.SENT, "EF (End of File)")
        self.state = YappState.S_EOF
        self._start_timer()

    def _send_eot(self):
        """Envía ET (Send EOT): EOT 01"""
        self._send_packet(bytes([EOT, 0x01]))
        self._log(YappEvent.SENT, "ET (End of Transmission)")
        self.state = YappState.S_EOT
        self._start_timer()

    def _send_rr(self):
        """Envía RR (Receive Ready): ACK 01"""
        self._send_packet(bytes([ACK, 0x01]))
        self._log(YappEvent.SENT, "RR (Receive Ready)")

    def _send_rf(self):
        """Envía RF (Receive File): ACK 02"""
        self._send_packet(bytes([ACK, 0x02]))
        self._log(YappEvent.SENT, "RF (Receive File)")

    def _send_af(self):
        """Envía AF (Ack EOF): ACK 03"""
        self._send_packet(bytes([ACK, 0x03]))
        self._log(YappEvent.SENT, "AF (Ack End of File)")

    def _send_at(self):
        """Envía AT (Ack EOT): ACK 04"""
        self._send_packet(bytes([ACK, 0x04]))
        self._log(YappEvent.SENT, "AT (Ack End of Transmission)")

    def _send_nr(self, reason=""):
        """
        Envía NR (Not Ready): NAK len reason

        Args:
            reason: str - motivo del rechazo
        """
        payload = reason.encode('ascii', errors='replace')
        pkt = bytes([NAK, len(payload)]) + payload
        self._send_packet(pkt)
        self._log(YappEvent.SENT, f"NR (Not Ready) {reason}")

    def _send_cancel(self, reason=""):
        """
        Envía CN (Cancel): CAN len reason

        Args:
            reason: str - motivo de cancelación
        """
        payload = reason.encode('ascii', errors='replace')
        pkt = bytes([CAN, len(payload)]) + payload
        self._send_packet(pkt)
        self._log(YappEvent.SENT, f"CN (Cancel) {reason}")

    def _send_ca(self):
        """Envía CA (Cancel Ack): ACK 05"""
        self._send_packet(bytes([ACK, 0x05]))
        self._log(YappEvent.SENT, "CA (Cancel Ack)")

    # ========================================================================
    # Buffer processing / State machine
    # ========================================================================

    def _process_buffer(self):
        """Procesa el buffer de recepción según el estado actual."""
        while len(self._rx_buf) >= 2:
            first = self._rx_buf[0]
            second = self._rx_buf[1]

            # -- Cancel from remote at any time --
            if first == CAN:
                length = second
                if len(self._rx_buf) < 2 + length:
                    return  # Wait for more data
                reason = bytes(self._rx_buf[2:2 + length]).decode('ascii', errors='replace')
                self._rx_buf = self._rx_buf[2 + length:]
                self._log(YappEvent.RECEIVED, f"CN (Cancel) {reason}")
                self._send_ca()
                self._finish(False, f"Cancelled by remote: {reason}")
                return

            # -- Route based on state --
            if self.state in (YappState.S_INIT, YappState.S_HEADER,
                              YappState.S_EOF, YappState.S_EOT):
                consumed = self._process_sender_response(first, second)
            elif self.state in (YappState.R_WAIT, YappState.R_HEADER):
                consumed = self._process_receiver_control(first, second)
            elif self.state == YappState.R_DATA:
                consumed = self._process_receiver_data(first, second)
            elif self.state == YappState.S_DATA:
                # Sender in data state shouldn't receive anything except CN (handled above)
                consumed = self._process_sender_data_interrupt(first, second)
            else:
                # Done/Error/Idle - discard
                self._rx_buf.clear()
                return

            if not consumed:
                return  # Need more data

    def _process_sender_response(self, first, second):
        """
        Procesa respuestas mientras estamos enviando.
        States: S_INIT, S_HEADER, S_EOF, S_EOT

        Args:
            first: int - primer byte del paquete
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes del buffer
        """
        self._cancel_timer()

        if first == ACK:
            self._rx_buf = self._rx_buf[2:]

            if second == 0x01:  # RR (Receive Ready)
                self._log(YappEvent.RECEIVED, "RR (Receive Ready)")
                if self.state == YappState.S_INIT:
                    self._send_header()
                return True

            elif second == 0x02:  # RF (Receive File)
                self._log(YappEvent.RECEIVED, "RF (Receive File)")
                if self.state in (YappState.S_INIT, YappState.S_HEADER):
                    self.state = YappState.S_DATA
                    self._log(YappEvent.INFO, "Sending data...")
                    self._send_data_loop()
                return True

            elif second == 0x03:  # AF (Ack EOF)
                self._log(YappEvent.RECEIVED, "AF (Ack End of File)")
                if self.state == YappState.S_EOF:
                    self._send_eot()
                return True

            elif second == 0x04:  # AT (Ack EOT)
                self._log(YappEvent.RECEIVED, "AT (Ack End of Transmission)")
                if self.state == YappState.S_EOT:
                    self._finish(True, f"File sent successfully: {self._filename}")
                return True

            elif second == 0x05:  # CA (Cancel Ack)
                self._log(YappEvent.RECEIVED, "CA (Cancel Ack)")
                self._finish(False, "Transfer cancelled")
                return True

            elif second == ACK:  # RT (Receive TPK / YappC) - ACK ACK
                self._log(YappEvent.RECEIVED, "RT (YappC requested - not supported, using standard)")
                # We respond as standard YAPP; receiver should still accept RF
                if self.state in (YappState.S_INIT, YappState.S_HEADER):
                    self.state = YappState.S_DATA
                    self._send_data_loop()
                return True

        elif first == NAK:
            # NR or RE (Resume)
            length = second
            if len(self._rx_buf) < 2 + length:
                return False  # Need more data
            payload = bytes(self._rx_buf[2:2 + length])
            self._rx_buf = self._rx_buf[2 + length:]

            if payload and payload[0:1] == b'R':
                # Resume request
                self._log(YappEvent.RECEIVED, f"RE (Resume) - not supported, restarting")
                # We don't support resume; send header again
                if self.state == YappState.S_HEADER:
                    self._file_handle.seek(0)
                    self._bytes_transferred = 0
                    self._send_header()
            else:
                reason = payload.decode('ascii', errors='replace')
                self._log(YappEvent.RECEIVED, f"NR (Not Ready) {reason}")
                self._finish(False, f"Remote not ready: {reason}")
            return True

        else:
            # Unexpected byte - discard one byte
            self._rx_buf = self._rx_buf[1:]
            return True

        return True

    def _process_receiver_control(self, first, second):
        """
        Procesa paquetes de control en modo receptor.
        States: R_WAIT, R_HEADER

        Args:
            first: int - primer byte
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes
        """
        self._cancel_timer()

        if first == ENQ and second == 0x01:
            # SI (Send Init)
            self._rx_buf = self._rx_buf[2:]
            self._log(YappEvent.RECEIVED, "SI (Send Init)")
            self._send_rr()
            self.state = YappState.R_HEADER
            self._start_timer()
            return True

        elif first == SOH:
            # HD (Header): SOH len payload
            length = second
            if len(self._rx_buf) < 2 + length:
                return False  # Need more data
            payload = bytes(self._rx_buf[2:2 + length])
            self._rx_buf = self._rx_buf[2 + length:]

            self._parse_header(payload)
            return True

        elif first == EOT and second == 0x01:
            # ET (End of Transmission) - no more files
            self._rx_buf = self._rx_buf[2:]
            self._log(YappEvent.RECEIVED, "ET (End of Transmission)")
            self._send_at()
            self._finish(True, "Transfer complete (no files)")
            return True

        elif first == ENQ and second == 0x01:
            # Duplicate SI
            self._rx_buf = self._rx_buf[2:]
            self._send_rr()
            return True

        else:
            # Unexpected - discard byte
            self._rx_buf = self._rx_buf[1:]
            return True

    def _process_receiver_data(self, first, second):
        """
        Procesa paquetes de datos en modo receptor.
        State: R_DATA

        Args:
            first: int - primer byte
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes
        """
        if first == STX:
            # DT (Data): STX len data
            length = second if second != 0 else 256
            if len(self._rx_buf) < 2 + length:
                return False  # Need more data

            data = bytes(self._rx_buf[2:2 + length])
            self._rx_buf = self._rx_buf[2 + length:]

            if self._file_handle:
                try:
                    self._file_handle.write(data)
                    self._bytes_transferred += length
                    self._update_progress()
                except Exception as e:
                    self._send_cancel(f"Write error: {e}")
                    self._finish(False, f"File write error: {e}")
            return True

        elif first == ETX and second == 0x01:
            # EF (End of File)
            self._rx_buf = self._rx_buf[2:]
            self._log(YappEvent.RECEIVED, "EF (End of File)")

            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None

            self._send_af()
            self.state = YappState.R_HEADER
            self._start_timer()
            self._log(YappEvent.SUCCESS,
                      f"File received: {self._filename} ({self._bytes_transferred} bytes)")
            return True

        elif first == EOT and second == 0x01:
            # ET (End of Transmission) - can come if no EF was sent
            self._rx_buf = self._rx_buf[2:]
            self._log(YappEvent.RECEIVED, "ET (End of Transmission)")
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            self._send_at()
            self._finish(True, f"Received {self._filename} ({self._bytes_transferred} bytes)")
            return True

        elif first == CAN:
            # Already handled in main process_buffer, but just in case
            length = second
            if len(self._rx_buf) < 2 + length:
                return False
            self._rx_buf = self._rx_buf[2 + length:]
            self._send_ca()
            self._finish(False, "Cancelled by remote")
            return True

        else:
            # Unexpected during data reception - could be corrupt
            self._rx_buf = self._rx_buf[1:]
            return True

    def _process_sender_data_interrupt(self, first, second):
        """
        Procesa datos recibidos inesperadamente durante envío de datos.
        Solo CN es esperado (manejado arriba). TX packets del servidor son aceptables.

        Args:
            first: int - primer byte
            second: int - segundo byte

        Returns:
            bool - True si se consumieron bytes
        """
        if first == DLE:
            # TX (Text from server): DLE len text
            length = second
            if len(self._rx_buf) < 2 + length:
                return False
            text = bytes(self._rx_buf[2:2 + length]).decode('ascii', errors='replace')
            self._rx_buf = self._rx_buf[2 + length:]
            self._log(YappEvent.RECEIVED, f"TX: {text}")
            return True
        else:
            # Unexpected - abort
            self._rx_buf.clear()
            self._send_cancel("Unexpected data during send")
            self._finish(False, "Protocol error: unexpected data during send")
            return True

    # ========================================================================
    # Header parsing
    # ========================================================================

    def _parse_header(self, payload):
        """
        Parsea el payload del header HD.

        Args:
            payload: bytes - contenido tras SOH len
        """
        parts = payload.split(b'\x00')
        if len(parts) >= 2:
            self._filename = parts[0].decode('ascii', errors='replace')
            try:
                self._file_size = int(parts[1].decode('ascii', errors='replace'))
            except (ValueError, IndexError):
                self._file_size = 0

        self._log(YappEvent.RECEIVED,
                  f"HD (Header) file={self._filename} size={self._file_size}")

        if not self._filename:
            self._send_nr("Invalid filename")
            self._finish(False, "Invalid filename in header")
            return

        # Abrir archivo para escritura
        filepath = os.path.join(self._download_dir, self._filename)
        try:
            self._file_handle = open(filepath, 'wb')
            self._bytes_transferred = 0
            self._send_rf()
            self.state = YappState.R_DATA
            self._log(YappEvent.INFO, f"Receiving {self._filename}...")
        except Exception as e:
            self._send_nr(f"Cannot create file: {e}")
            self._finish(False, f"Cannot create file: {e}")

    # ========================================================================
    # Data send loop
    # ========================================================================

    def _send_data_loop(self):
        """Envía todos los bloques de datos y luego EF."""
        while self.state == YappState.S_DATA:
            if not self._send_data_block():
                # No more data
                if self._file_handle:
                    self._file_handle.close()
                    self._file_handle = None
                self._send_eof()
                return

    # ========================================================================
    # Timer
    # ========================================================================

    def _start_timer(self):
        """Inicia el crash timer."""
        self._cancel_timer()
        self._timer = threading.Timer(TIMEOUT_S, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self):
        """Cancela el crash timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self):
        """Callback cuando expira el crash timer."""
        with self._lock:
            if self.state == YappState.S_INIT and self._si_retries < MAX_SI_RETRIES:
                self._si_retries += 1
                self._log(YappEvent.INFO, f"Timeout, retrying SI ({self._si_retries}/{MAX_SI_RETRIES})...")
                self._send_si()
            elif self.state != YappState.IDLE:
                self._log(YappEvent.ERROR, "Timeout - no response from remote")
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
        """
        if self.send_raw:
            self.send_raw(data)

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

    def _finish(self, success, message):
        """
        Finaliza la transferencia.

        Args:
            success: bool - si fue exitosa
            message: str - mensaje final
        """
        self._cancel_timer()
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

        self.state = YappState.DONE if success else YappState.ERROR
        event = YappEvent.SUCCESS if success else YappEvent.ERROR
        self._log(event, message)

        if self.on_finished:
            self.on_finished(success, message)

    def _reset(self):
        """Resetea todo el estado a IDLE."""
        self._cancel_timer()
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
        self._file_handle = None
        self._filename = ""
        self._file_size = 0
        self._bytes_transferred = 0
        self._rx_buf.clear()
        self._si_retries = 0
        self.state = YappState.IDLE

    def reset_to_idle(self):
        """Resetea a IDLE (para reutilizar tras completar)."""
        with self._lock:
            self._reset()

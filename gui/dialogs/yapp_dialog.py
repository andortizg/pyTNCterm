"""
YAPP File Transfer Dialog - shows progress, control messages, and transfer status.
"""
import tkinter as tk
import tkinter.ttk as ttk
import time
from gui import theme
from core.yapp_handler import YappEvent


class YappTransferDialog(tk.Toplevel):
    """
    Ventana de progreso de transferencia YAPP.
    Muestra log de mensajes de control con colores, barra de progreso,
    contadores de bytes y botón de cancelar.

    Args:
        parent: tk widget - ventana padre
        mode: str - "send" o "receive"
        filename: str - nombre del archivo (vacío si receive)
        on_cancel: callable() - callback para cancelar transferencia
    """

    def __init__(self, parent, mode="send", filename="", on_cancel=None):
        super().__init__(parent)
        self._mode = mode
        self._on_cancel = on_cancel
        self._start_time = time.time()
        self._closed = False

        title = "YAPP Send" if mode == "send" else "YAPP Receive"
        self.title(f"📡  {title}")
        self.geometry("560x420")
        self.configure(bg=theme.get("dialog_bg"))
        self.resizable(True, True)
        self.minsize(450, 320)
        self.transient(parent)
        self.protocol("WM_DELETE_CLOSE", self._do_cancel)

        self._build_ui(filename)
        self._center()
        self.grab_set()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self, filename):
        """Construye la interfaz del diálogo."""
        bg = theme.get("dialog_bg")
        fg = theme.get("dialog_fg")
        accent = theme.get("accent_primary")
        dim = theme.get("text_dim")

        main = tk.Frame(self, bg=bg)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # -- Header --
        hdr = tk.Frame(main, bg=bg)
        hdr.pack(fill=tk.X, pady=(0, 8))

        icon = "📤" if self._mode == "send" else "📥"
        label_text = "Sending file" if self._mode == "send" else "Receiving file"
        tk.Label(hdr, text=f"{icon}  {label_text}", font=("Segoe UI", 13, "bold"),
                 bg=bg, fg=accent).pack(side=tk.LEFT)

        # -- File info frame --
        info_frame = tk.Frame(main, bg=theme.get("bg_light"), padx=10, pady=8,
                              highlightbackground=theme.get("border_accent"),
                              highlightthickness=1)
        info_frame.pack(fill=tk.X, pady=(0, 8))

        # Filename
        fn_frame = tk.Frame(info_frame, bg=theme.get("bg_light"))
        fn_frame.pack(fill=tk.X)
        tk.Label(fn_frame, text="File:", font=("Segoe UI", 9),
                 bg=theme.get("bg_light"), fg=dim, width=8, anchor="w").pack(side=tk.LEFT)
        self._lbl_filename = tk.Label(fn_frame, text=filename or "Waiting...",
                                       font=("Consolas", 10, "bold"),
                                       bg=theme.get("bg_light"), fg=fg, anchor="w")
        self._lbl_filename.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Size
        sz_frame = tk.Frame(info_frame, bg=theme.get("bg_light"))
        sz_frame.pack(fill=tk.X)
        tk.Label(sz_frame, text="Size:", font=("Segoe UI", 9),
                 bg=theme.get("bg_light"), fg=dim, width=8, anchor="w").pack(side=tk.LEFT)
        self._lbl_size = tk.Label(sz_frame, text="—", font=("Consolas", 10),
                                   bg=theme.get("bg_light"), fg=fg, anchor="w")
        self._lbl_size.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # -- Progress bar --
        prog_frame = tk.Frame(main, bg=bg)
        prog_frame.pack(fill=tk.X, pady=(0, 4))

        # Custom canvas progress bar for better theming
        self._progress_canvas = tk.Canvas(prog_frame, height=22, bg=theme.get("bg_dark"),
                                           highlightthickness=1,
                                           highlightbackground=theme.get("border_accent"))
        self._progress_canvas.pack(fill=tk.X)
        self._progress_pct = 0.0

        # Stats line
        stats_frame = tk.Frame(main, bg=bg)
        stats_frame.pack(fill=tk.X, pady=(0, 8))

        self._lbl_transferred = tk.Label(stats_frame, text="0 bytes",
                                          font=("Consolas", 9), bg=bg,
                                          fg=theme.get("accent_secondary"), anchor="w")
        self._lbl_transferred.pack(side=tk.LEFT)

        self._lbl_speed = tk.Label(stats_frame, text="", font=("Consolas", 9),
                                    bg=bg, fg=dim, anchor="e")
        self._lbl_speed.pack(side=tk.RIGHT)

        self._lbl_pct = tk.Label(stats_frame, text="0%", font=("Consolas", 9, "bold"),
                                  bg=bg, fg=accent)
        self._lbl_pct.pack(side=tk.RIGHT, padx=(0, 12))

        # -- Control messages log --
        log_label = tk.Label(main, text="Protocol Messages", font=("Segoe UI", 9, "bold"),
                             bg=bg, fg=theme.get("accent_cyan"), anchor="w")
        log_label.pack(fill=tk.X, pady=(0, 2))

        log_frame = tk.Frame(main, bg=theme.get("bg_dark"),
                             highlightbackground=theme.get("border_accent"),
                             highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._log_text = tk.Text(
            log_frame, wrap=tk.WORD, font=("Consolas", 9),
            bg=theme.get("bg_dark"), fg=theme.get("text_secondary"),
            insertbackground=theme.get("bg_dark"),
            selectbackground=theme.get("bg_highlight"),
            selectforeground=fg,
            borderwidth=0, padx=6, pady=4, state=tk.DISABLED, cursor="arrow"
        )
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview,
                                  bg=theme.get("scrollbar_bg"),
                                  troughcolor=theme.get("bg_dark"),
                                  activebackground=theme.get("scrollbar_fg"))
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure tags for coloring
        self._log_text.tag_configure("time", foreground=theme.get("text_dim"),
                                      font=("Consolas", 8))
        self._log_text.tag_configure("sent", foreground=theme.get("accent_secondary"),
                                      font=("Consolas", 9, "bold"))
        self._log_text.tag_configure("received", foreground=theme.get("accent_primary"),
                                      font=("Consolas", 9, "bold"))
        self._log_text.tag_configure("info", foreground=theme.get("text_secondary"),
                                      font=("Consolas", 9))
        self._log_text.tag_configure("error", foreground=theme.get("accent_error"),
                                      font=("Consolas", 9, "bold"))
        self._log_text.tag_configure("success", foreground=theme.get("accent_secondary"),
                                      font=("Consolas", 9, "bold"))
        self._log_text.tag_configure("arrow_tx", foreground=theme.get("accent_secondary"),
                                      font=("Consolas", 9))
        self._log_text.tag_configure("arrow_rx", foreground=theme.get("accent_primary"),
                                      font=("Consolas", 9))

        # -- Buttons --
        btn_frame = tk.Frame(main, bg=bg)
        btn_frame.pack(fill=tk.X)

        self._btn_cancel = tk.Button(
            btn_frame, text="Cancel Transfer", font=("Segoe UI", 9, "bold"),
            bg=theme.get("accent_error"), fg="#ffffff",
            activebackground="#ff1744", activeforeground="#ffffff",
            borderwidth=0, padx=16, pady=5, cursor="hand2",
            command=self._do_cancel
        )
        self._btn_cancel.pack(side=tk.LEFT)

        self._btn_close = tk.Button(
            btn_frame, text="Close", font=("Segoe UI", 9),
            bg=theme.get("button_bg"), fg=theme.get("button_fg"),
            activebackground=theme.get("button_active"),
            borderwidth=0, padx=16, pady=5, cursor="hand2",
            command=self._do_close, state=tk.DISABLED
        )
        self._btn_close.pack(side=tk.RIGHT)

    # ========================================================================
    # Public update methods (called from main_window via YAPP handler callbacks)
    # ========================================================================

    def update_file_info(self, filename, file_size):
        """
        Actualiza información del archivo.

        Args:
            filename: str - nombre del archivo
            file_size: int - tamaño en bytes
        """
        if self._closed:
            return
        self._lbl_filename.configure(text=filename)
        if file_size > 0:
            self._lbl_size.configure(text=self._format_size(file_size))
        else:
            self._lbl_size.configure(text="Unknown")

    def update_progress(self, transferred, total):
        """
        Actualiza barra de progreso y contadores.

        Args:
            transferred: int - bytes transferidos
            total: int - bytes totales
        """
        if self._closed:
            return

        # Percentage
        if total > 0:
            pct = min(100.0, (transferred / total) * 100)
        else:
            pct = 0.0
        self._progress_pct = pct

        # Draw progress bar
        self._draw_progress_bar(pct)

        # Labels
        self._lbl_pct.configure(text=f"{pct:.1f}%")
        self._lbl_transferred.configure(
            text=f"{self._format_size(transferred)} / {self._format_size(total)}")

        # Speed
        elapsed = time.time() - self._start_time
        if elapsed > 0.5 and transferred > 0:
            speed = transferred / elapsed
            self._lbl_speed.configure(text=f"{self._format_size(int(speed))}/s")

    def log_event(self, event_type, message):
        """
        Añade mensaje al log de control.

        Args:
            event_type: YappEvent - tipo de evento
            message: str - mensaje
        """
        if self._closed:
            return

        self._log_text.configure(state=tk.NORMAL)

        # Timestamp
        ts = time.strftime("%H:%M:%S")
        self._log_text.insert(tk.END, f"[{ts}] ", "time")

        # Direction arrow and tag
        tag_map = {
            YappEvent.SENT: ("sent", "▲ TX  "),
            YappEvent.RECEIVED: ("received", "▼ RX  "),
            YappEvent.INFO: ("info", "  ℹ   "),
            YappEvent.ERROR: ("error", "  ✖   "),
            YappEvent.SUCCESS: ("success", "  ✔   "),
        }
        tag, prefix = tag_map.get(event_type, ("info", "      "))
        arrow_tag = "arrow_tx" if event_type == YappEvent.SENT else (
            "arrow_rx" if event_type == YappEvent.RECEIVED else tag)

        self._log_text.insert(tk.END, prefix, arrow_tag)
        self._log_text.insert(tk.END, message + "\n", tag)

        self._log_text.configure(state=tk.DISABLED)
        self._log_text.see(tk.END)

    def transfer_finished(self, success, message):
        """
        Indica que la transferencia terminó.

        Args:
            success: bool - éxito
            message: str - mensaje final
        """
        if self._closed:
            return

        if success:
            self._draw_progress_bar(100.0)
            self._lbl_pct.configure(text="100%")

        # Enable close, disable cancel
        self._btn_cancel.configure(state=tk.DISABLED)
        self._btn_close.configure(state=tk.NORMAL)
        self.protocol("WM_DELETE_CLOSE", self._do_close)

    # ========================================================================
    # Internal
    # ========================================================================

    def _draw_progress_bar(self, pct):
        """
        Dibuja la barra de progreso en el canvas.

        Args:
            pct: float - porcentaje (0-100)
        """
        c = self._progress_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1:
            return

        # Background track
        c.create_rectangle(0, 0, w, h, fill=theme.get("bg_dark"), outline="")

        # Filled portion
        fill_w = int(w * pct / 100)
        if fill_w > 0:
            # Gradient-like effect: darker at left, brighter toward right
            color = theme.get("accent_primary")
            c.create_rectangle(0, 0, fill_w, h, fill=color, outline="")

            # Highlight strip at top
            highlight = theme.get("accent_secondary")
            c.create_rectangle(0, 0, fill_w, 3, fill=highlight, outline="")

        # Percentage text
        text_color = "#ffffff" if pct > 50 else theme.get("text_primary")
        c.create_text(w // 2, h // 2, text=f"{pct:.1f}%",
                      fill=text_color, font=("Consolas", 9, "bold"))

    def _format_size(self, size):
        """
        Formatea tamaño en bytes a string legible.

        Args:
            size: int - tamaño en bytes

        Returns:
            str - tamaño formateado (ej: "1.5 KB")
        """
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"

    def _do_cancel(self):
        """Maneja cancelación."""
        if self._on_cancel:
            self._on_cancel()

    def _do_close(self):
        """Cierra el diálogo."""
        self._closed = True
        self.grab_release()
        self.destroy()

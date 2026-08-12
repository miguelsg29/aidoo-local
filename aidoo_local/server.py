"""Servidor local que suplanta la nube de Airzone (skaidoo1.airzonecloud.com).

El Aidoo (con su DNS redirigido a este equipo) conecta por TLS aceptando nuestro certificado
autofirmado. Aquí:
  - leemos su telemetría y mantenemos el estado del aire (AidooState),
  - le enviamos comandos (encolados) para controlarlo,
todo SIN la nube real de Airzone. Verificado: el Aidoo aguanta sin la nube y obedece.
"""
from __future__ import annotations
import socket
import ssl
import threading
import time

from . import protocol as P


class AidooServer:
    SETTLE_S = 5.0   # segundos a esperar tras (re)conectar antes de mandar comandos (el Aidoo
    #                  ignora comandos durante su volcado inicial de telemetría)

    def __init__(self, cert_path, key_path, port=443, on_change=None, logger=print):
        self.cert_path = cert_path
        self.key_path = key_path
        self.port = port
        self.on_change = on_change            # callback(state_dict) cuando cambia el estado
        self.log = logger
        self.state = P.AidooState()
        self._queue: list[bytes] = []
        self._qlock = threading.Lock()
        self._ctx = None
        self.connected = False
        self.last_seen = 0.0

    # ---- API de control (alto nivel) ----
    # Se actualiza el estado de forma OPTIMISTA al mandar el comando: el modo y la velocidad
    # no se leen de la telemetría (el Aidoo no los reporta), así que la fuente de verdad para
    # esos campos es lo último que hemos ordenado (el aire obedece, verificado vs Modbus).
    def set_power(self, on: bool):
        self._enqueue(P.cmd_power(on))
        self._optimistic(power=on)

    def set_mode(self, ha_mode: str):
        """ha_mode: off/auto/cool/heat/dry/fan_only. 'off' apaga; el resto enciende + fija modo."""
        if ha_mode == "off":
            self.set_power(False)
            return
        bit = P.HA_TO_MODE.get(ha_mode)
        if bit is None:
            return
        self.set_power(True)
        self._enqueue(P.cmd_mode(bit))
        self._optimistic(power=True, mode=ha_mode)

    def set_setpoint(self, celsius: float):
        self._enqueue(P.cmd_setpoint(celsius))
        self._optimistic(setpoint=round(float(celsius), 1))

    def set_fan(self, ha_fan: str):
        val = P.HA_TO_FAN.get(ha_fan)
        if val is not None:
            self._enqueue(P.cmd_fan(val))
            self._optimistic(fan=ha_fan)

    def send_raw(self, hexstr: str):
        """Encola un comando en crudo (hex) — útil para depurar/reversear registros nuevos."""
        data = bytes.fromhex(hexstr.strip().replace(" ", "").replace(":", ""))
        if data:
            self._enqueue(data)

    def _optimistic(self, **kw):
        for k, v in kw.items():
            setattr(self.state, k, v)
        if self.on_change:
            try:
                self.on_change(self.state.to_dict())
            except Exception:
                pass

    def _enqueue(self, cmd: bytes):
        with self._qlock:
            self._queue.append(cmd)
        self.log(f"[aidoo] comando encolado: {cmd.hex()}")

    # ---- servidor ----
    def _tls_ctx(self):
        if self._ctx is None:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(self.cert_path, self.key_path)
            try:
                ctx.set_ciphers("ALL:@SECLEVEL=0")
            except Exception:
                pass
            self._ctx = ctx
        return self._ctx

    def start(self):
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", self.port))
        s.listen(20)
        self.log(f"[aidoo] servidor (suplantando skaidoo1) escuchando en 0.0.0.0:{self.port}")
        while True:
            try:
                c, a = s.accept()
                threading.Thread(target=self._handle, args=(c, a), daemon=True).start()
            except Exception as e:
                self.log(f"[aidoo] accept error: {e}")

    def _handle(self, conn, addr):
        try:
            tls = self._tls_ctx().wrap_socket(conn, server_side=True)
        except Exception:
            return
        self.connected = True
        buf = b""
        conn_start = time.time()
        tls.settimeout(1.0)
        try:
            while True:
                # 1) enviar comandos encolados — SOLO tras el volcado inicial. El Aidoo ignora
                #    los comandos durante su ráfaga de telemetría de arranque (verificado: a los
                #    ~6 s los ACKea y aplica; antes no). La conexión es persistente, así que solo
                #    el primer comando tras (re)conectar espera; los siguientes van al instante.
                if time.time() - conn_start >= self.SETTLE_S:
                    with self._qlock:
                        pending, self._queue = self._queue, []
                    for cmd in pending:
                        try:
                            tls.sendall(cmd)
                            self.log(f"[aidoo] --> enviado {cmd.hex()}")
                        except Exception:
                            with self._qlock:
                                self._queue.insert(0, cmd)   # reintentar en la próxima conexión
                            raise
                # 2) leer telemetría
                try:
                    d = tls.recv(8192)
                except socket.timeout:
                    continue
                if not d:
                    break
                self.last_seen = time.time()
                buf += d
                frames, buf = P.parse_frames(buf)
                changed = False
                for typ, reg, data in frames:
                    if typ == 0x01 and self.state.update_from_report(reg, data):
                        changed = True
                if changed and self.on_change:
                    try:
                        self.on_change(self.state.to_dict())
                    except Exception as e:
                        self.log(f"[aidoo] on_change error: {e}")
        except Exception:
            pass
        finally:
            self.connected = False
            try:
                tls.close()
            except Exception:
                pass

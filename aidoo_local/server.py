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
from collections import deque

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
        self._samples = deque(maxlen=240)  # (timestamp, current_temp) para estimar ETA a confort

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

    def set_timer(self, minutes: int):
        """Temporizador de apagado en minutos (0 = cancelar)."""
        m = max(0, int(minutes))
        self._enqueue(P.cmd_timer(m))
        self._optimistic(timer_min=m)

    def set_led(self, on: bool):
        self._enqueue(P.cmd_led(bool(on)))
        self._optimistic(led=bool(on))

    def send_raw(self, hexstr: str):
        """Encola un comando en crudo (hex) — útil para depurar/reversear registros nuevos."""
        data = bytes.fromhex(hexstr.strip().replace(" ", "").replace(":", ""))
        if data:
            self._enqueue(data)

    def _optimistic(self, **kw):
        for k, v in kw.items():
            setattr(self.state, k, v)
        self._notify()

    def _notify(self):
        if self.on_change:
            try:
                self.on_change(self.snapshot())
            except Exception:
                pass

    def snapshot(self) -> dict:
        """Estado + ETA a confort calculado en local."""
        d = self.state.to_dict()
        d["eta_min"] = self.eta_minutes()
        return d

    def eta_minutes(self):
        """Estima los minutos hasta alcanzar la consigna, por regresión lineal de la Tª ambiente
        (como hace la nube de Airzone, que no manda este dato: lo calculamos nosotros)."""
        st = self.state
        if not st.power or st.setpoint is None or st.current_temp is None:
            return None
        pts = [(t, v) for (t, v) in self._samples if self._samples and self._samples[-1][0] - t <= 1500]
        if len(pts) < 3:
            return None
        t0 = pts[0][0]
        xs = [t - t0 for t, _ in pts]
        ys = [v for _, v in pts]
        n = len(xs)
        sx, sy = sum(xs), sum(ys)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, ys))
        denom = n * sxx - sx * sx
        if denom == 0:
            return None
        slope = (n * sxy - sx * sy) / denom          # °C por segundo
        gap = st.setpoint - st.current_temp
        if abs(gap) < 0.2:
            return 0
        if abs(slope) < 1e-5 or (gap > 0) != (slope > 0):
            return None                              # estable o alejándose
        mins = (gap / slope) / 60.0
        return round(mins) if 0 <= mins <= 24 * 60 else None

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
        threading.Thread(target=self._sampler, daemon=True).start()

    def _sampler(self):
        """Muestrea la Tª ambiente cada 30 s (aunque no cambie) para tener una serie temporal
        con la que estimar el ETA a confort aunque la temperatura baje despacio."""
        while True:
            time.sleep(30)
            if self.state.power and self.state.current_temp is not None:
                self._samples.append((time.time(), self.state.current_temp))

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
                if changed:
                    self._notify()
        except Exception:
            pass
        finally:
            self.connected = False
            try:
                tls.close()
            except Exception:
                pass

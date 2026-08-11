"""Protocolo binario del Airzone Aidoo (reverseado por MITM de la nube skaidoo1).

Trama:  TT REG LEN <LEN bytes de datos> CKSUM
  TT   = 0x01 informe (Aidoo -> nube)  |  0x02 comando (nube -> Aidoo)
  REG  = registro
  LEN  = nº de bytes de datos
  CKSUM= suma de todos los bytes previos (mod 256)

Escritura con máscara (comandos):  datos = <mask16 BE> <value16 BE>, donde la máscara marca
los bits a CONSERVAR (los demás toman el valor). Las temperaturas van en LE16 ×10.

Registros mapeados (verificados en vivo + cruzados con Modbus):
  0x00 encendido, 0x07 modo, 0x08 consigna, 0x0b ventilador, 0x0c temperatura ambiente.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# --- registros ---
REG_POWER = 0x00
REG_MODE = 0x07
REG_SETPOINT = 0x08
REG_FAN = 0x0B
REG_CURRENT_TEMP = 0x0C

# --- modos (byte alto de reg 0x07; bitmask) <-> nombres de Home Assistant ---
MODE_TO_HA = {0x01: "auto", 0x02: "cool", 0x04: "heat", 0x08: "dry", 0x10: "fan_only"}
HA_TO_MODE = {v: k for k, v in MODE_TO_HA.items()}

# --- velocidad de ventilador ---
FAN_TO_HA = {0x04: "low", 0x10: "medium", 0x40: "high"}
HA_TO_FAN = {v: k for k, v in FAN_TO_HA.items()}


def checksum(body: bytes) -> int:
    return sum(body) & 0xFF


def frame(typ: int, reg: int, data: bytes) -> bytes:
    body = bytes([typ, reg, len(data)]) + data
    return body + bytes([checksum(body)])


def parse_frames(buf: bytes):
    """Trocea un buffer en tramas (typ, reg, datos). Tolera basura: si el checksum no cuadra,
    avanza 1 byte. Devuelve (lista de tramas, bytes sobrantes sin completar)."""
    out = []
    i = 0
    n = len(buf)
    while i + 4 <= n:
        typ, reg, ln = buf[i], buf[i + 1], buf[i + 2]
        end = i + 3 + ln
        if end + 1 > n:
            break  # trama incompleta: esperar más datos
        data = buf[i + 3:end]
        cs = buf[end]
        if typ in (0x01, 0x02) and checksum(buf[i:end]) == cs:
            out.append((typ, reg, data))
            i = end + 1
        else:
            i += 1  # resincronizar
    return out, buf[i:]


def _le16(data: bytes) -> int:
    """Los 2 bytes de valor de una trama de temperatura van en data[2:4], little-endian."""
    d = data[2:4] if len(data) >= 4 else data
    return int.from_bytes(d.ljust(2, b"\x00")[:2], "little")


# --- comandos (nube -> Aidoo) ---
def cmd_power(on: bool) -> bytes:
    # máscara 0xfffe = conserva todo menos el bit 0; valor bit0 = on/off
    return frame(0x02, REG_POWER, bytes([0xFF, 0xFE, 0x00, 0x01 if on else 0x00]))


def cmd_mode(mode_bit: int) -> bytes:
    # máscara 0x00ff = conserva byte bajo; el modo va en el byte alto
    return frame(0x02, REG_MODE, bytes([0x00, 0xFF, mode_bit & 0xFF, 0x00]))


def cmd_setpoint(celsius: float) -> bytes:
    v = int(round(celsius * 10))
    return frame(0x02, REG_SETPOINT, bytes([0x00, 0x00]) + v.to_bytes(2, "little"))


def cmd_fan(fan_val: int) -> bytes:
    return frame(0x02, REG_FAN, bytes([0x00, 0xFF, fan_val & 0xFF, 0x00]))


@dataclass
class AidooState:
    """Estado del aire, actualizado desde la telemetría del Aidoo."""
    power: bool | None = None
    mode: str | None = None          # auto/cool/heat/dry/fan_only
    setpoint: float | None = None
    current_temp: float | None = None
    fan: str | None = None           # low/medium/high
    raw: dict = field(default_factory=dict)  # último dato crudo por registro (depuración)

    def hvac_mode(self) -> str:
        """Modo HVAC de Home Assistant (off si está apagado; si no, el modo)."""
        if self.power is False:
            return "off"
        return self.mode or "off"

    def update_from_report(self, reg: int, data: bytes) -> bool:
        """Aplica un informe (typ 0x01). Devuelve True si cambió algo relevante."""
        self.raw[reg] = data.hex()
        before = (self.power, self.mode, self.setpoint, self.current_temp, self.fan)
        if reg == REG_POWER and len(data) >= 4:
            # bit0 del último byte del bloque de estado = encendido
            self.power = bool(data[-1] & 0x01)
        elif reg == REG_MODE and len(data) >= 3:
            self.mode = MODE_TO_HA.get(data[2], self.mode)
        elif reg == REG_SETPOINT and len(data) >= 4:
            self.setpoint = _le16(data) / 10.0
        elif reg == REG_CURRENT_TEMP and len(data) >= 4:
            self.current_temp = _le16(data) / 10.0
        elif reg == REG_FAN and len(data) >= 3:
            self.fan = FAN_TO_HA.get(data[2], self.fan)
        after = (self.power, self.mode, self.setpoint, self.current_temp, self.fan)
        return before != after

    def to_dict(self) -> dict:
        return {"power": self.power, "hvac_mode": self.hvac_mode(), "mode": self.mode,
                "setpoint": self.setpoint, "current_temp": self.current_temp, "fan": self.fan}

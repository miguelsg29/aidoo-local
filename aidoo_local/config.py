"""Configuración de aidoo-local. Lee variables de entorno y, si existe, un fichero .env
(que NO se sube al repo). Genera el certificado autofirmado si no existe."""
from __future__ import annotations
import os
import subprocess

# El Aidoo busca este dominio; redirige su DNS a este servidor. El cert lleva su SAN.
SKAIDOO_HOST = "skaidoo1.airzonecloud.com"


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _e(k, d=None):
    return os.environ.get(k, d)


class Config:
    def __init__(self):
        load_env()
        self.listen_port = int(_e("AIDOO_PORT", "443"))
        self.cert_path = _e("AIDOO_CERT", "certs/cert.pem")
        self.key_path = _e("AIDOO_KEY", "certs/key.pem")
        self.mqtt_host = _e("MQTT_HOST", "")
        self.mqtt_port = int(_e("MQTT_PORT", "1883"))
        self.mqtt_user = _e("MQTT_USER", "") or None
        self.mqtt_pass = _e("MQTT_PASS", "") or None
        self.node_id = _e("AIDOO_NODE", "aidoo_lg")
        self.name = _e("AIDOO_NAME", "Aire LG (local)")
        self.min_temp = float(_e("AIDOO_MIN_TEMP", "16"))
        self.max_temp = float(_e("AIDOO_MAX_TEMP", "30"))
        self.temp_step = float(_e("AIDOO_TEMP_STEP", "0.5"))

    def ensure_cert(self):
        """Genera un cert autofirmado con el SAN de airzonecloud si no existe. El Aidoo NO
        valida el certificado, así que este autofirmado le sirve para conectar."""
        if os.path.exists(self.cert_path) and os.path.exists(self.key_path):
            return
        os.makedirs(os.path.dirname(self.cert_path) or ".", exist_ok=True)
        san = (f"subjectAltName=DNS:{SKAIDOO_HOST},DNS:*.airzonecloud.com,"
               "DNS:*.airzonecloud.net")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-keyout", self.key_path, "-out", self.cert_path, "-days", "3650",
                        "-nodes", "-subj", f"/CN={SKAIDOO_HOST}", "-addext", san],
                       check=True, capture_output=True)

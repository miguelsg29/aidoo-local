"""Punto de entrada: `python -m aidoo_local`.

Arranca el servidor que suplanta la nube de Airzone (skaidoo1) y, si hay broker MQTT
configurado, publica el aire como entidad climate en Home Assistant.
"""
import time

from .config import Config
from .server import AidooServer
from .mqtt_bridge import MqttBridge


def main():
    cfg = Config()
    cfg.ensure_cert()
    print(f"[aidoo-local] v{__import__('aidoo_local').__version__}")
    srv = AidooServer(cfg.cert_path, cfg.key_path, port=cfg.listen_port)
    srv.start()
    if cfg.mqtt_host:
        MqttBridge(srv, cfg.mqtt_host, cfg.mqtt_port, cfg.mqtt_user, cfg.mqtt_pass,
                   node_id=cfg.node_id, name=cfg.name, min_temp=cfg.min_temp,
                   max_temp=cfg.max_temp, temp_step=cfg.temp_step).start()
        print(f"[aidoo-local] MQTT -> {cfg.mqtt_host}:{cfg.mqtt_port} (entidad climate en HA)")
    else:
        print("[aidoo-local] sin MQTT_HOST: solo servidor (define MQTT_* para la entidad en HA)")
    print("[aidoo-local] redirige por DNS skaidoo1.airzonecloud.com a este equipo y reinicia el Aidoo")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()

"""Puente MQTT: expone el aire (a través del AidooServer) como una entidad `climate` de
Home Assistant, con autodescubrimiento (MQTT discovery). HA controla el aire por el servidor
local, sin la nube de Airzone.
"""
from __future__ import annotations
import json
import threading
import time

import paho.mqtt.client as mqtt


class MqttBridge:
    def __init__(self, server, host, port=1883, user=None, password=None,
                 node_id="aidoo_lg", name="Aire LG (local)",
                 min_temp=16, max_temp=30, temp_step=0.5, logger=print):
        self.srv = server
        self.host, self.port, self.user, self.password = host, port, user, password
        self.node = node_id
        self.name = name
        self.min_temp, self.max_temp, self.temp_step = min_temp, max_temp, temp_step
        self.log = logger
        b = f"aidoo_local/{node_id}"
        self.t = {
            "avail": f"{b}/available",
            "mode_set": f"{b}/mode/set", "mode": f"{b}/mode",
            "temp_set": f"{b}/temp/set", "temp": f"{b}/temp",
            "current": f"{b}/current",
            "fan_set": f"{b}/fan/set", "fan": f"{b}/fan",
        }
        self.disc_topic = f"homeassistant/climate/{node_id}/config"
        self.client = mqtt.Client(client_id=f"aidoo-local-{node_id}")
        if user:
            self.client.username_pw_set(user, password or "")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.will_set(self.t["avail"], "offline", retain=True)
        server.on_change = self._publish_state

    def start(self):
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()
        threading.Thread(target=self._heartbeat, daemon=True).start()

    # ---- discovery ----
    def _discovery_payload(self):
        return {
            "name": self.name,
            "unique_id": self.node,
            "device": {"identifiers": [f"aidoo_local_{self.node}"],
                       "name": self.name, "manufacturer": "Airzone (Aidoo, local)",
                       "model": "Aidoo Wi-Fi (nube suplantada)"},
            "availability_topic": self.t["avail"],
            "modes": ["off", "auto", "cool", "heat", "dry", "fan_only"],
            "mode_command_topic": self.t["mode_set"], "mode_state_topic": self.t["mode"],
            "temperature_command_topic": self.t["temp_set"],
            "temperature_state_topic": self.t["temp"],
            "current_temperature_topic": self.t["current"],
            "fan_modes": ["low", "medium", "high"],
            "fan_mode_command_topic": self.t["fan_set"], "fan_mode_state_topic": self.t["fan"],
            "min_temp": self.min_temp, "max_temp": self.max_temp, "temp_step": self.temp_step,
            "temperature_unit": "C",
        }

    def _on_connect(self, client, userdata, flags, rc):
        self.log(f"[mqtt] conectado (rc={rc})")
        client.publish(self.disc_topic, json.dumps(self._discovery_payload()), retain=True)
        for topic in (self.t["mode_set"], self.t["temp_set"], self.t["fan_set"]):
            client.subscribe(topic)
        client.publish(self.t["avail"], "online", retain=True)
        self._publish_state(self.srv.state.to_dict())

    def _on_message(self, client, userdata, msg):
        val = msg.payload.decode(errors="replace").strip()
        try:
            if msg.topic == self.t["mode_set"]:
                self.srv.set_mode(val)
            elif msg.topic == self.t["temp_set"]:
                self.srv.set_setpoint(float(val))
            elif msg.topic == self.t["fan_set"]:
                self.srv.set_fan(val)
        except Exception as e:
            self.log(f"[mqtt] error procesando {msg.topic}={val}: {e}")

    def _publish_state(self, st: dict):
        c = self.client
        if st.get("hvac_mode") is not None:
            c.publish(self.t["mode"], st["hvac_mode"], retain=True)
        if st.get("setpoint") is not None:
            c.publish(self.t["temp"], st["setpoint"], retain=True)
        if st.get("current_temp") is not None:
            c.publish(self.t["current"], st["current_temp"], retain=True)
        if st.get("fan") is not None:
            c.publish(self.t["fan"], st["fan"], retain=True)

    def _heartbeat(self):
        """Publica disponibilidad según el Aidoo esté conectado, y reemite el estado."""
        while True:
            time.sleep(20)
            try:
                self.client.publish(self.t["avail"],
                                    "online" if self.srv.connected else "offline", retain=True)
                self._publish_state(self.srv.state.to_dict())
            except Exception:
                pass

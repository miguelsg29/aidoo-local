"""Puente MQTT: expone el aire (a través del AidooServer) en Home Assistant por MQTT discovery.

Entidades publicadas (todas bajo un mismo dispositivo):
  - climate  : encendido, modo, consigna, temperatura, ventilador
  - number   : temporizador de apagado (minutos, 0=cancelar)
  - switch   : LED
  - sensor   : Tª Trabajo, Tª Retorno, y "Tiempo a confort" (ETA calculado en local)
HA controla el aire por el servidor local, sin la nube de Airzone.
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
            "timer_set": f"{b}/timer/set", "timer": f"{b}/timer",
            "led_set": f"{b}/led/set", "led": f"{b}/led",
            "work": f"{b}/work", "return": f"{b}/return", "eta": f"{b}/eta",
        }
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
    def _device(self):
        return {"identifiers": [f"aidoo_local_{self.node}"], "name": self.name,
                "manufacturer": "Airzone (Aidoo, local)", "model": "Aidoo Wi-Fi (nube suplantada)"}

    def _publish_discovery(self):
        c, dev, av = self.client, self._device(), self.t["avail"]

        def pub(kind, obj_id, cfg):
            cfg.update({"availability_topic": av, "device": dev,
                        "unique_id": obj_id, "object_id": obj_id})
            c.publish(f"homeassistant/{kind}/{obj_id}/config", json.dumps(cfg), retain=True)

        pub("climate", self.node, {
            "name": self.name,
            "modes": ["off", "auto", "cool", "heat", "dry", "fan_only"],
            "mode_command_topic": self.t["mode_set"], "mode_state_topic": self.t["mode"],
            "temperature_command_topic": self.t["temp_set"], "temperature_state_topic": self.t["temp"],
            "current_temperature_topic": self.t["current"],
            "fan_modes": ["auto", "low", "medium", "high"],
            "fan_mode_command_topic": self.t["fan_set"], "fan_mode_state_topic": self.t["fan"],
            "min_temp": self.min_temp, "max_temp": self.max_temp, "temp_step": self.temp_step,
            "temperature_unit": "C"})
        pub("number", f"{self.node}_timer", {
            "name": "Temporizador", "icon": "mdi:timer-outline",
            "command_topic": self.t["timer_set"], "state_topic": self.t["timer"],
            "min": 0, "max": 720, "step": 30, "unit_of_measurement": "min", "mode": "slider"})
        pub("switch", f"{self.node}_led", {
            "name": "LED", "icon": "mdi:led-on",
            "command_topic": self.t["led_set"], "state_topic": self.t["led"],
            "payload_on": "ON", "payload_off": "OFF"})
        pub("sensor", f"{self.node}_work", {
            "name": "Tª Trabajo", "state_topic": self.t["work"],
            "device_class": "temperature", "unit_of_measurement": "°C"})
        pub("sensor", f"{self.node}_return", {
            "name": "Tª Retorno", "state_topic": self.t["return"],
            "device_class": "temperature", "unit_of_measurement": "°C"})
        pub("sensor", f"{self.node}_eta", {
            "name": "Tiempo a confort", "icon": "mdi:timer-sand",
            "state_topic": self.t["eta"], "unit_of_measurement": "min"})

    def _on_connect(self, client, userdata, flags, rc):
        self.log(f"[mqtt] conectado (rc={rc})")
        self._publish_discovery()
        for topic in (self.t["mode_set"], self.t["temp_set"], self.t["fan_set"],
                      self.t["timer_set"], self.t["led_set"]):
            client.subscribe(topic)
        client.publish(self.t["avail"], "online", retain=True)
        self._publish_state(self.srv.snapshot())

    def _on_message(self, client, userdata, msg):
        val = msg.payload.decode(errors="replace").strip()
        try:
            if msg.topic == self.t["mode_set"]:
                self.srv.set_mode(val)
            elif msg.topic == self.t["temp_set"]:
                self.srv.set_setpoint(float(val))
            elif msg.topic == self.t["fan_set"]:
                self.srv.set_fan(val)
            elif msg.topic == self.t["timer_set"]:
                self.srv.set_timer(int(float(val)))
            elif msg.topic == self.t["led_set"]:
                self.srv.set_led(val.upper() == "ON")
        except Exception as e:
            self.log(f"[mqtt] error procesando {msg.topic}={val}: {e}")

    def _publish_state(self, st: dict):
        c = self.client
        pubs = {
            "mode": st.get("hvac_mode"), "temp": st.get("setpoint"),
            "current": st.get("current_temp"), "fan": st.get("fan"),
            "timer": st.get("timer_min"), "work": st.get("work_temp"),
            "return": st.get("return_temp"), "eta": st.get("eta_min"),
        }
        for key, v in pubs.items():
            if v is not None:
                c.publish(self.t[key], v, retain=True)
        if st.get("led") is not None:
            c.publish(self.t["led"], "ON" if st["led"] else "OFF", retain=True)

    def _heartbeat(self):
        """Publica disponibilidad según el Aidoo esté conectado, y reemite el estado (con ETA)."""
        while True:
            time.sleep(20)
            try:
                self.client.publish(self.t["avail"],
                                    "online" if self.srv.connected else "offline", retain=True)
                self._publish_state(self.srv.snapshot())
            except Exception:
                pass

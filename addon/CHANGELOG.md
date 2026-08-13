# Changelog

## 0.2.2
- ETA a confort: muestreo periódico de la Tª ambiente (cada 30 s) en vez de solo al cambiar,
  para estimar aunque la temperatura baje despacio (antes no acumulaba serie temporal).

## 0.2.1
- Panel web: etiqueta "Estado del LED" con botones ON/OFF, botón Apagar más visible,
  y modo Auto en lugar destacado (Ventilador a la fila).

## 0.2.0
- Nuevos controles y sensores (reverseados de la app por MITM y verificados byte a byte):
  - **Temporizador** de apagado (entidad `number`, minutos; 0 = cancelar) — reg 0x87.
  - **LED** (entidad `switch`) — reg 0x89.
  - **Tª Trabajo** y **Tª Retorno** (sensores) — reg 0x2d / 0x23.
  - **Tiempo a confort** (sensor calculado en local por regresión de la Tª ambiente, como la nube).
- El panel web muestra los sensores y permite temporizador/LED.

## 0.1.2
- Panel web de control y pruebas: estado en vivo (encendido, modo, consigna, temperatura,
  ventilador), controles, y una sección de depuración (registros del Aidoo + envío de
  comandos en crudo). En la app se abre desde la barra lateral de Home Assistant (ingress);
  en modo suelto, en `http://<equipo>:8098`. Sin dependencias nuevas (servidor HTTP integrado).

## 0.1.1
- Terminología «app» (Home Assistant 2026.2 renombró «Add-ons» a «Apps»).
- Documentado que el Aidoo exige el **puerto 443** libre en el equipo (si HA ya lo usa,
  libéralo o ejecuta la app en otro equipo de la red apuntando `skaidoo1` a esa IP).

## 0.1.0
- Primera versión. Control local (sin nube de Airzone) de un Airzone Aidoo Wi-Fi y su aire,
  publicado en Home Assistant como entidad `climate` por MQTT: encendido, modos
  (auto/frío/calor/deshu/ventilador), consigna, velocidad de ventilador y temperatura ambiente.
- La app suplanta `skaidoo1.airzonecloud.com` (redirige ese DNS a Home Assistant) y abre el
  puerto 443. MQTT se autoconfigura desde el broker de Home Assistant.

# Changelog

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

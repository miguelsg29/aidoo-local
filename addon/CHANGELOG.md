# Changelog

## 0.1.0
- Primera versión. Control local (sin nube de Airzone) de un Airzone Aidoo Wi-Fi y su aire,
  publicado en Home Assistant como entidad `climate` por MQTT: encendido, modos
  (auto/frío/calor/deshu/ventilador), consigna, velocidad de ventilador y temperatura ambiente.
- El add-on suplanta `skaidoo1.airzonecloud.com` (redirige ese DNS a Home Assistant) y abre el
  puerto 443. MQTT se autoconfigura desde el broker de Home Assistant.

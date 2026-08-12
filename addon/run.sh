#!/bin/sh
# Lee la configuración de la app de Home Assistant y arranca Aidoo Local.
CONFIG="/data/options.json"

export AIDOO_NAME=$(jq -r '.AIDOO_NAME // "Aire (local)"' $CONFIG)
export AIDOO_MIN_TEMP=$(jq -r '.AIDOO_MIN_TEMP // 16' $CONFIG)
export AIDOO_MAX_TEMP=$(jq -r '.AIDOO_MAX_TEMP // 30' $CONFIG)
export AIDOO_TEMP_STEP=$(jq -r '.AIDOO_TEMP_STEP // 0.5' $CONFIG)
export MQTT_HOST=$(jq -r '.MQTT_HOST // ""' $CONFIG)
export MQTT_PORT=$(jq -r '.MQTT_PORT // 1883' $CONFIG)
export MQTT_USER=$(jq -r '.MQTT_USER // ""' $CONFIG)
export MQTT_PASS=$(jq -r '.MQTT_PASS // ""' $CONFIG)

# Autoconfiguración de MQTT desde Home Assistant: si no pones el broker a mano, el Supervisor
# nos da host/puerto/usuario/contraseña del add-on de Mosquitto. Requiere "services: mqtt:want".
if [ -z "$MQTT_HOST" ] && [ -n "$SUPERVISOR_TOKEN" ]; then
    MQTT_SVC=$(curl -s -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/services/mqtt)
    if [ "$(echo "$MQTT_SVC" | jq -r '.result // ""')" = "ok" ]; then
        export MQTT_HOST=$(echo "$MQTT_SVC" | jq -r '.data.host // ""')
        export MQTT_PORT=$(echo "$MQTT_SVC" | jq -r '.data.port // 1883')
        export MQTT_USER=$(echo "$MQTT_SVC" | jq -r '.data.username // ""')
        export MQTT_PASS=$(echo "$MQTT_SVC" | jq -r '.data.password // ""')
        echo "[INFO] MQTT autoconfigurado desde Home Assistant: ${MQTT_HOST}:${MQTT_PORT}"
    else
        echo "[INFO] MQTT: Home Assistant no devolvió broker. ¿Tienes la app 'Mosquitto broker'?"
        echo "       (o rellena MQTT_HOST/USER/PASS a mano para un broker externo)."
    fi
fi

# Certificado TLS persistente en /data (se genera una vez, con el SAN de airzonecloud).
export AIDOO_CERT=/data/cert.pem
export AIDOO_KEY=/data/key.pem
export AIDOO_PORT=443
export AIDOO_WEB_PORT=8098
export PYTHONPATH=/app

echo "[INFO] Aidoo Local: escuchando en :443. Redirige por DNS skaidoo1.airzonecloud.com a esta IP"
echo "       y reinicia el Aidoo. La entidad climate aparecerá en Home Assistant."
exec python3 -m aidoo_local

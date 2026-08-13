# aidoo-local

Control **local y sin nube** de un aire acondicionado gobernado por un **Airzone Aidoo
Wi-Fi** (probado con un Aidoo para LG, modelo AZAI6WSCLGE), e integración en **Home
Assistant**. En la línea de [Clean Assistant](https://github.com/miguelsg29/clean-assistant)
para el Conga: hace al aparato **independiente de la nube del fabricante**.

## Por qué

El Aidoo Wi-Fi «normal» (no Pro) **no expone API local** (solo la tiene el Aidoo Pro, en el
puerto 3000) — depende de la nube de Airzone (`skaidoo1.airzonecloud.com`). Este proyecto
**suplanta esa nube**: el Aidoo cree que habla con Airzone, pero habla con este servidor, que
lee su estado y lo controla. Así el aire funciona **aunque Airzone cierre sus servidores** y
sin mandarles datos.

> Descubierto por ingeniería inversa (MITM de la conexión TLS del Aidoo). El Aidoo **no valida
> el certificado del servidor**, así que un cert autofirmado le vale para conectar.

## Cómo funciona

```
   Aire (LG)  <--wired--  Aidoo Wi-Fi
                              │  TLS (DNS: skaidoo1.airzonecloud.com -> este servidor)
                              ▼
                     ┌──────────────────────┐
                     │   aidoo-local          │
                     │   server  → suplanta   │
                     │             skaidoo1   │
                     │   mqtt    → HA climate  │
                     └───────────┬────────────┘
                                 ▼
                          Home Assistant
```

El protocolo es un **binario propio sobre TLS** (reverseado). Trama:
`TT REG LEN <datos> CKSUM`, donde `TT=01` informe (Aidoo→nube) y `TT=02` comando
(nube→Aidoo); el checksum es la suma de los bytes previos. Registros mapeados:

| Registro | Función | Codificación |
|---|---|---|
| `0x00` | Encendido/apagado | bit 0 |
| `0x07` | Modo | byte alto: auto=`01`, frío=`02`, calor=`04`, deshu=`08`, ventilador=`10` |
| `0x08` | Consigna | entero 16-bit little-endian ×10 |
| `0x0b` | Velocidad ventilador | baja=`04`, media=`10`, alta=`40` |
| `0x0c` | Temperatura ambiente (lectura) | entero 16-bit little-endian ×10 |

Detalle clave: el Aidoo **ignora los comandos durante su volcado de arranque**; hay que
enviarlos unos segundos después de (re)conectar (lo gestiona el servidor).

## Instalación como app de Home Assistant (recomendado)

Este repositorio **es también un repositorio de Apps de Home Assistant** (add-ons), así corre
siempre encendido dentro de HA.

> Desde **Home Assistant 2026.2**, los «Add-ons» se llaman ahora **«Apps»**. Si tu HA es
> anterior, es exactamente lo mismo que «Add-ons».

1. **Añade el repositorio**: en Home Assistant, **Ajustes → Apps → Tienda de Apps →
   menú ⋮ → Repositorios**, pega `https://github.com/miguelsg29/aidoo-local` y **Añadir**.
2. **Instala «Aidoo Local»** y arráncalo. MQTT se **autoconfigura** desde el broker de HA
   (Mosquitto); solo rellena `MQTT_*` a mano si usas un broker externo.
3. **Redirige el DNS**: haz que **`skaidoo1.airzonecloud.com`** apunte a la **IP de Home
   Assistant** (AdGuard Home / Pi-hole / router). La app abre el **puerto 443** (que debe
   estar libre en HA — ver «Nota sobre el puerto 443»).
4. **Reinicia el Aidoo** (corta la corriente y vuelve a darle) para que reconecte a HA.
5. Aparecerá la entidad **climate** en Home Assistant (autodescubrimiento MQTT), y un
   **panel web** de control/pruebas en la **barra lateral** de HA (ingress).

> ### Nota sobre el puerto 443
> El Aidoo se conecta **obligatoriamente al puerto 443** (fijo en su firmware), así que la app
> debe escuchar en el 443 del equipo al que rediriges `skaidoo1`. Si en Home Assistant ya hay
> algo usando el 443 (p. ej. un proxy SSL, Nginx, Duck DNS o HA con SSL), la app no arrancará
> («port 443 already in use»): libera ese puerto o **ejecuta la app en otro equipo** de la red
> con el 443 libre (apunta `skaidoo1` a esa IP y `MQTT_HOST` a tu broker de HA — la entidad
> aparece en HA igualmente).

## Ejecutar en otro equipo con Docker (recomendado si HA ya usa el 443)

Si en Home Assistant el 443 está ocupado (p. ej. por **Nginx Proxy Manager**), ejecuta el app
en **otro equipo** de la red con el 443 libre (una Raspberry, un NAS, un mini-PC…). La entidad
sigue apareciendo en Home Assistant por MQTT.

```bash
cp .env.example .env          # ajusta MQTT_* (broker de HA) y AIDOO_NAME
docker compose up -d --build
```

Luego redirige por DNS `skaidoo1.airzonecloud.com` a la **IP de ese equipo** y reinicia el Aidoo.

### Sin Docker

1. `pip install -r requirements.txt`
2. `cp .env.example .env` y ajusta `MQTT_*`.
3. Redirige `skaidoo1.airzonecloud.com` a la IP de este equipo (puerto 443 libre).
4. `python -m aidoo_local` (el certificado autofirmado se genera solo).
5. Reinicia el Aidoo.

Para volver a la nube de Airzone (app oficial), quita la reescritura DNS de `skaidoo1`.

## Estado

Verificado en vivo contra un Aidoo real, **cruzando CADA valor con la interfaz Modbus del
propio aparato** como referencia:
- ✅ **Control** de los 5 modos (auto/frío/calor/deshu/ventilador), encendido/apagado, las 3
  velocidades de ventilador y la consigna (incl. medios grados) — el aire obedece.
- ✅ **Lectura** de encendido, consigna y temperatura ambiente desde la telemetría (coincide
  con Modbus). El **modo y la velocidad** del ventilador NO los reporta el Aidoo, así que se
  llevan por **seguimiento optimista** (lo último ordenado; el aire obedece igual).
- ✅ **Extras reverseados de la app** (por MITM, verificados byte a byte): **temporizador** de
  apagado (`number`), **LED** (`switch`), sensores **Tª Trabajo** y **Tª Retorno**, y
  **Tiempo a confort** (ETA calculado en local, como hace la nube).
- ✅ El Aidoo funciona de forma estable con la nube suplantada, sin errores.
- ✅ Empaquetado como **app de Home Assistant** (add-on, en `addon/`) con **panel web**
  (ingress / `http://<equipo>:8098`) para control y pruebas.
- ⬜ Nota: la unidad LG solo aporta datos básicos; consumo/temperaturas extendidas del Modbus
  leen 0 en este equipo (son de bombas de calor agua/ACS).

## Privacidad

Nada de identidad del aparato ni de la red va al repositorio: los certificados, el `.env`
(IPs, credenciales MQTT) y cualquier log/estado están en `.gitignore`. La MAC y el SSID que
el Aidoo emite se quedan en runtime, nunca en el código.

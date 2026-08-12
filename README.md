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

## Instalación como add-on de Home Assistant (recomendado)

Este repositorio **es también un repositorio de add-ons de Home Assistant**, así corre
siempre encendido dentro de HA.

1. **Añade el repositorio**: en Home Assistant, **Ajustes → Add-ons → Tienda de add-ons →
   menú ⋮ → Repositorios**, pega `https://github.com/miguelsg29/aidoo-local` y **Añadir**.
2. **Instala «Aidoo Local»** y arráncalo. MQTT se **autoconfigura** desde el broker de HA
   (Mosquitto); solo rellena `MQTT_*` a mano si usas un broker externo.
3. **Redirige el DNS**: haz que **`skaidoo1.airzonecloud.com`** apunte a la **IP de Home
   Assistant** (AdGuard Home / Pi-hole / router). El add-on abre el **puerto 443**.
4. **Reinicia el Aidoo** (corta la corriente y vuelve a darle) para que reconecte a HA.
5. Aparecerá la entidad **climate** en Home Assistant (autodescubrimiento MQTT).

## Puesta en marcha (manual, sin add-on)

1. **Instala dependencias**: `pip install -r requirements.txt`.
2. **Configura**: copia `.env.example` a `.env` y ajusta `MQTT_*` (broker de Home Assistant).
3. **Redirige el DNS**: haz que **`skaidoo1.airzonecloud.com`** apunte a la IP de este equipo.
   Abre el **puerto 443**.
4. **Arranca**: `python -m aidoo_local`. El certificado autofirmado se genera solo.
5. **Reinicia el Aidoo** para que reconecte aquí.

Para volver a la nube de Airzone (app oficial), quita la reescritura DNS de `skaidoo1`.

## Estado

Verificado en vivo contra un Aidoo real, **cruzando CADA valor con la interfaz Modbus del
propio aparato** como referencia:
- ✅ **Control** de los 5 modos (auto/frío/calor/deshu/ventilador), encendido/apagado, las 3
  velocidades de ventilador y la consigna (incl. medios grados) — el aire obedece.
- ✅ **Lectura** de encendido, consigna y temperatura ambiente desde la telemetría (coincide
  con Modbus). El **modo y la velocidad** del ventilador NO los reporta el Aidoo, así que se
  llevan por **seguimiento optimista** (lo último ordenado; el aire obedece igual).
- ✅ El Aidoo funciona de forma estable con la nube suplantada, sin errores.
- ✅ Empaquetado como **add-on de Home Assistant** (`addon/`).
- ⬜ Pendiente/afinar: velocidad de ventilador «auto», más sensores (consumo, errores).

## Privacidad

Nada de identidad del aparato ni de la red va al repositorio: los certificados, el `.env`
(IPs, credenciales MQTT) y cualquier log/estado están en `.gitignore`. La MAC y el SSID que
el Aidoo emite se quedan en runtime, nunca en el código.

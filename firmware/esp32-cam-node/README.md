# Nodo ESP32-CAM — Bioterio

Firmware del nodo de captura para una jaula. Solo transmite video (MJPEG) y
telemetría (JSON) por WiFi — **no hace tracking ni IA**, eso lo hace la PC
central (próxima etapa del proyecto).

Pensado para la placa **AI-Thinker ESP32-CAM** (la que trae el kit de
Nagame Electrónica con antena externa + placa base programadora, y la
mayoría de los kits ESP32-CAM del mercado).

## Arquitectura del firmware

```
src/
├── main.cpp               → orquesta todo + salvaguardas de resiliencia del nodo
├── wifi_manager.h/.cpp     → conecta y reconecta WiFi (backoff exponencial)
├── camera_manager.h/.cpp   → inicializa la cámara OV2640
├── temperature_sensor.h/.cpp → lee temperatura (DS18B20 opcional, o NAN si está deshabilitado)
└── http_server.h/.cpp      → expone /stream, /capture, /status (+ auth opcional)
```

Cada módulo tiene una sola responsabilidad y no conoce el resto del
sistema más de lo necesario: `http_server` no sabe qué SSID usa el nodo,
`wifi_manager` no sabe nada de HTTP, y `temperature_sensor` es el único
archivo que sabe si `ENABLE_TEMP_SENSOR` está prendido o no. Esto hace que
cada pieza se pueda cambiar (otro sensor, otra forma de reconectar WiFi)
sin tocar las demás.

## 1. Requisitos

- **VSCode** + extensión **PlatformIO IDE** (buscarla en el marketplace de
  extensiones de VSCode), o el CLI: `pip install platformio`.
- La **placa base programadora** que vino en el kit (o un adaptador USB-TTL
  tipo CP2102/FTDI) para flashear por USB.
- Drivers del chip USB-serial instalados (CP2102 o CH340, según la placa
  base — Windows normalmente los instala solo al conectar, si no aparece el
  puerto COM hay que instalarlos manualmente).

## 2. Configuración inicial (una sola vez)

1. Copiá `include/config.example.h` como `include/config.h`.
2. Completá en `config.h`:
   - `WIFI_SSID` / `WIFI_PASSWORD`: la red WiFi del bioterio.
   - `NODE_ID`: un nombre único para esta jaula (ej. `"jaula_01"`) — también
     se usa como nombre mDNS (`http://jaula_01.local`).
3. `config.h` está en `.gitignore` a propósito, para no subir la contraseña
   de WiFi a ningún repositorio.

## 3. Compilar y flashear

Con la placa conectada por USB (y en modo flasheo — ver sección 5 si no
sube el programa):

```bash
# Desde esta carpeta (firmware/esp32-cam-node)
pio run              # solo compila
pio run -t upload    # compila y flashea
pio device monitor   # abre el monitor serie (115200 baudios)
```

Si usás VSCode con la extensión PlatformIO, es lo mismo pero con los
botones de la barra inferior (✓ compilar, → flashear, 🔌 monitor).

Al arrancar, el monitor serie va a imprimir la IP asignada, el nombre mDNS
y las 3 URLs del nodo:

```
Conectando a WiFi 'jaula_01'. conectado.
mDNS activo: http://jaula_01.local

Nodo 'jaula_01' listo.
  Video:   http://192.168.0.160:81/stream
  Foto:    http://192.168.0.160/capture
  Estado:  http://192.168.0.160/status
```

## 4. Probar que funciona

- **Video en vivo**: abrí `http://<ip>:81/stream` (o `http://<node_id>.local:81/stream`)
  en el navegador (Chrome lo muestra directo) o en VLC (Media > Abrir
  ubicación de red).
- **Foto suelta**: `http://<ip>/capture`.
- **Estado del nodo**: `http://<ip>/status` devuelve un JSON con uptime,
  señal WiFi (rssi), memoria libre y temperatura (si está habilitado el
  sensor).
- O usá el script de prueba en [`/tools`](../../tools) desde la PC (ver su
  README — está gestionado con `uv`).

## 5. Si la placa no entra en modo flasheo

Algunas placas base ESP32-CAM-MB tienen un switch físico "prog/run" o
requieren mantener presionado un botón durante el upload. Si `pio run -t
upload` falla con timeout esperando el chip:

1. Mantené presionado el botón RESET/IO0 de la placa base.
2. Ejecutá `pio run -t upload`.
3. Soltá el botón apenas empiece a ver `Connecting....` o los puntos de
   sincronización.

## 6. Problemas de compilación conocidos

- Si el compilador tira un error tipo `no member named 'pin_sccb_sda'`,
  es porque tu versión del core `arduino-esp32` usa el nombre viejo. Abrí
  [`src/camera_manager.cpp`](src/camera_manager.cpp) y cambiá
  `pin_sccb_sda` / `pin_sccb_scl` por `pin_sscb_sda` / `pin_sscb_scl` (son
  el mismo pin, cambió el nombre del campo entre versiones del framework).

## 7. Ajustes según el montaje físico

- **Orientación de la imagen**: si la cámara queda montada al revés o
  espejada según cómo se atornille en el estante, ajustá `CAMERA_VFLIP` /
  `CAMERA_HMIRROR` en `config.h`.
- **Resolución**: `CAMERA_FRAMESIZE` está en VGA (640×480) por defecto —
  suficiente para el tracking, no satura la red con muchos nodos.
- **Sensor de temperatura (opcional)**: poniendo `ENABLE_TEMP_SENSOR 1` en
  `config.h` y conectando un DS18B20 al pin `TEMP_SENSOR_PIN`, el valor
  aparece automáticamente en `/status`.

## 8. Seguridad

Los endpoints no requieren autenticación por defecto — pensado para una
red interna del bioterio ya segmentada del resto de la red/internet. Si
hace falta, definí `API_KEY` en `config.h` con un valor no vacío: a partir
de ahí, todos los requests a `/stream`, `/capture` y `/status` necesitan el
header `X-API-Key: <ese valor>` o reciben `401 Unauthorized`.

Esto **no reemplaza** una red segmentada ni TLS: si en algún momento el
nodo necesita ser accesible desde fuera de la red del bioterio, ponelo
detrás de una VPN o un reverse proxy en la PC central en vez de exponerlo
directo — el ESP32 no tiene capacidad para manejar HTTPS de forma
eficiente a este volumen de tráfico.

## 9. Resiliencia (pensado para 24/7 durante semanas)

- **WiFi**: se reconecta solo con backoff exponencial (1s → 30s) si se
  corta la señal; solo reinicia el equipo si falla la conexión *inicial*.
- **Memoria**: si la memoria libre cae por debajo de `MIN_FREE_HEAP_BYTES`
  (20KB por defecto sugerido — fragmentación esperable tras días de
  streaming continuo), reinicia de forma preventiva.
- **Reinicio preventivo semanal**: por defecto sugerido a los 7 días de
  uptime continuo (configurable con `MAX_UPTIME_BEFORE_RESTART_S`), para no
  depender de que nada falle para hacer una limpieza de estado.
- **Cámara**: si falla de forma persistente (no un frame suelto, sino
  fallos consecutivos sostenidos), el nodo se reinicia solo en vez de
  quedar sirviendo un stream roto indefinidamente.
- **Watchdog de bloqueos**: el core de Arduino ya trae un watchdog de
  tareas que reinicia el equipo si `loop()` se cuelga sin ceder CPU; por
  eso `loop()` siempre termina con un `delay()` corto.

### Límite conocido: pocas conexiones simultáneas a `/stream`

El ESP32 tiene un pool de sockets muy chico (confirmado con hardware
real: alcanza con 5-8 conexiones concurrentes, incluso mal cerradas, para
agotarlo). Cuando se agota, el nodo deja de responder en `/stream` — a
veces incluso en `/status` — hasta que las conexiones viejas se liberan
solas o se reinicia el equipo.

**En la práctica**: evitá tener más de **un cliente a la vez** mirando el
`/stream` de un mismo nodo (por ejemplo, `bioterio-view-stream` y
`bioterio-debug-view` corriendo juntos contra el mismo nodo, o varias
pestañas del navegador abiertas). El servidor central (`bioterio-server`)
ya asume un solo consumidor por nodo, así que no tiene este problema en
uso normal — el riesgo aparece si además corrés herramientas de
diagnóstico contra un nodo que el servidor central ya está consumiendo.

Se intentó mitigar esto a nivel firmware (timeouts más cortos +
`lru_purge_enable` en el servidor HTTP) pero la prueba rompió el caso
normal en vez de arreglar el de contención, así que se revertió. Si el
pool se agota, hace falta resetear el nodo (botón físico, o reflashear).
Diagnosticarlo bien queda como tarea pendiente.

## 10. Qué falta para el sistema completo

Este firmware es solo el nodo. Los próximos pasos del proyecto son:

1. Validar el nodo de noche con el sensor NoIR + LEDs 940nm (si ya se
   consiguió ese módulo de cámara).
2. Armar el servidor central en Python que consuma `/stream` de todos los
   nodos, corra YOLO + tracking, y guarde resultados en MySQL.
3. Repetir el flasheo para cada jaula, cambiando solo `NODE_ID` (y la IP
   estática, si se decide fijarlas) en cada `config.h`.

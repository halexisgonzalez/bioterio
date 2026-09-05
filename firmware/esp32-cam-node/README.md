# Nodo ESP32-CAM — Bioterio

Firmware del nodo de captura para una jaula. Solo transmite video (MJPEG) y
telemetría (JSON) por WiFi — **no hace tracking ni IA**, eso lo hace la PC
central (próxima etapa del proyecto).

Pensado para la placa **AI-Thinker ESP32-CAM** (la que trae el kit de
Nagame Electrónica con antena externa + placa base programadora, y la
mayoría de los kits ESP32-CAM del mercado).

---

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
   - `NODE_ID`: un nombre único para esta jaula (ej. `"jaula_01"`).
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

Al arrancar, el monitor serie va a imprimir la IP asignada y las 3 URLs
del nodo, algo así:

```
Nodo 'jaula_01' listo.
  Video:   http://192.168.1.114:81/stream
  Foto:    http://192.168.1.114/capture
  Estado:  http://192.168.1.114/status
```

## 4. Probar que funciona

- **Video en vivo**: abrí `http://<ip>:81/stream` en el navegador (Chrome
  lo muestra directo) o en VLC (Media > Abrir ubicación de red).
- **Foto suelta**: `http://<ip>/capture`.
- **Estado del nodo**: `http://<ip>/status` devuelve un JSON con uptime,
  señal WiFi (rssi), memoria libre y temperatura (si está habilitado el
  sensor).
- O usá el script de prueba en [`/tools/test_stream.py`](../../tools/test_stream.py)
  desde la PC (ver el README de esa carpeta).

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
  [`src/main.cpp`](src/main.cpp) y cambiá `pin_sccb_sda` / `pin_sccb_scl`
  por `pin_sscb_sda` / `pin_sscb_scl` (son el mismo pin, cambió el nombre
  del campo entre versiones del framework).

## 7. Ajustes según el montaje físico

- **Orientación de la imagen**: si la cámara queda montada al revés o
  espejada según cómo se atornille en el estante, ajustá `CAMERA_VFLIP` /
  `CAMERA_HMIRROR` en `config.h`.
- **Resolución**: `CAMERA_FRAMESIZE` está en VGA (640×480) por defecto —
  ver la justificación técnica en la documentación del proyecto
  (suficiente para el tracking, no satura la red con muchos nodos).
- **Sensor de temperatura (opcional)**: poniendo `ENABLE_TEMP_SENSOR 1` en
  `config.h` y conectando un DS18B20 al pin `TEMP_SENSOR_PIN`, el valor
  aparece automáticamente en `/status`.

## 8. Qué falta para el sistema completo

Este firmware es solo el nodo. Los próximos pasos del proyecto son:

1. Validar el nodo de noche con el sensor NoIR + LEDs 940nm (si ya se
   consiguió ese módulo de cámara).
2. Armar el servidor central en Python que consuma `/stream` de todos los
   nodos, corra YOLO + tracking, y guarde resultados en MySQL.
3. Repetir el flasheo para cada jaula, cambiando solo `NODE_ID` (y la IP
   estática, si se decide fijarlas) en cada `config.h`.

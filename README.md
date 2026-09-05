# Bioterio — Tracking por Visión por Computadora

Sistema de visión por computadora para monitorear ratones dentro de jaulas
de bioterio (trayectoria, actividad, uso del espacio, temperatura) de forma
continua, 24/7, durante varias semanas, en múltiples jaulas simultáneas.

## Estructura del repo

```
bioterio/
├── pyproject.toml                         → workspace de uv (une tools/ y server/ en un solo entorno)
├── docs/
│   ├── etapa1-investigacion-hardware.md   → relevamiento del entorno y especificaciones de hardware
│   ├── etapa1-investigacion-hardware.pdf  → misma info, en PDF
│   └── fotos-relevamiento/                → fotos del bioterio (racks, jaulas, distancias)
├── firmware/
│   └── esp32-cam-node/                    → firmware del nodo de captura (ESP32-CAM, PlatformIO, C++)
├── tools/                                 → utilidades en Python: validar un nodo desde la PC
│   └── src/bioterio_tools/
│       ├── node_client.py                 → cliente HTTP del nodo (status + stream) — reutilizable
│       ├── mjpeg_stream.py                → lector del stream MJPEG
│       └── view_stream.py                 → CLI para ver el video de un nodo
└── server/                                → servidor central: ingesta multi-nodo + tracking + MySQL
    └── src/bioterio_server/
        ├── detection/                     → detector v1 (resta de fondo, sin modelo entrenado)
        ├── tracking/                      → asignación de IDs a los animales detectados
        ├── pipeline/                      → un hilo por nodo (captura → detección → tracking)
        └── storage/                       → persistencia batcheada en MySQL
```

## Arquitectura general

- **Nodo por jaula**: ESP32-CAM (placa económica) transmite video MJPEG y
  telemetría por WiFi. No procesa IA. El firmware está separado en módulos
  con responsabilidad única (WiFi, cámara, temperatura, servidor HTTP) e
  incluye reconexión automática de WiFi, autenticación opcional por API
  key, descubrimiento por mDNS y reinicios preventivos ante memoria baja o
  fallas persistentes de cámara — pensado para correr 24/7 sin supervisión
  durante semanas. Ver [firmware/esp32-cam-node](firmware/esp32-cam-node).
- **PC central** ([server/](server)): un hilo por nodo consume su stream,
  detecta al animal (v1: resta de fondo, sin modelo entrenado — ver el
  README de `server/` para el detalle y las limitaciones), le asigna un ID
  con un tracker de centroides, y guarda posición/estado/temperatura en
  MySQL por lotes. Reutiliza el cliente HTTP de [tools/](tools) en vez de
  duplicarlo (ambos viven en un mismo workspace de `uv`).
- **tools/**: utilidades de línea de comandos para validar un nodo desde
  la PC (ver su video, chequear su `/status`) — útil tanto en el
  desarrollo del firmware como para depurar un nodo ya desplegado.

Ver el detalle de decisiones y justificaciones técnicas en
[docs/etapa1-investigacion-hardware.md](docs/etapa1-investigacion-hardware.md).

## Empezar rápido (Python)

```bash
uv sync --all-packages          # instala tools/ y server/ en un solo entorno
uv run --package bioterio-tools bioterio-view-stream <ip-del-nodo>
```

Ver [server/README.md](server/README.md) para levantar el servidor
central completo (necesita MySQL — hay un `docker-compose.yml` listo).

## Estado actual

- [x] Relevamiento del entorno físico y definición de hardware (nodo ESP32-CAM)
- [x] Firmware del nodo (stream MJPEG + captura + status JSON, con
      seguridad/resiliencia/mDNS)
- [x] Servidor central en Python (ingesta multi-nodo + detección v1 +
      tracking), validado en vivo contra hardware real
- [x] Persistencia en MySQL (esquema + inserts por lotes, validado en vivo)
- [ ] Validación del nodo con sensor NoIR + LEDs 940nm de noche
- [ ] Reemplazar el detector v1 (resta de fondo) por un modelo entrenado
- [ ] Dashboard / reportes

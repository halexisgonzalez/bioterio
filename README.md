# Bioterio — Tracking por Visión por Computadora

Sistema de visión por computadora para monitorear ratones dentro de jaulas
de bioterio (trayectoria, actividad, uso del espacio, temperatura) de forma
continua, 24/7, durante varias semanas, en múltiples jaulas simultáneas.

## Estructura del repo

```
bioterio/
├── docs/
│   ├── etapa1-investigacion-hardware.md   → relevamiento del entorno y especificaciones de hardware
│   ├── etapa1-investigacion-hardware.pdf  → misma info, en PDF
│   └── fotos-relevamiento/                → fotos del bioterio (racks, jaulas, distancias)
├── firmware/
│   └── esp32-cam-node/                    → firmware del nodo de captura (ESP32-CAM, PlatformIO)
└── tools/
    └── test_stream.py                     → script en Python para validar el stream de un nodo desde la PC
```

## Arquitectura general

- **Nodo por jaula**: ESP32-CAM (placa económica) transmite video MJPEG y
  telemetría por WiFi. No procesa IA — ver [firmware/esp32-cam-node](firmware/esp32-cam-node).
- **PC central**: consume el stream de todos los nodos, corre detección +
  tracking (YOLO/ByteTrack) y guarda resultados en MySQL. *(próxima etapa,
  aún no implementada en este repo)*.

Ver el detalle de decisiones y justificaciones técnicas en
[docs/etapa1-investigacion-hardware.md](docs/etapa1-investigacion-hardware.md).

## Estado actual

- [x] Relevamiento del entorno físico y definición de hardware (nodo ESP32-CAM)
- [x] Firmware del nodo (stream MJPEG + captura + status JSON)
- [ ] Validación del nodo con sensor NoIR + LEDs 940nm de noche
- [ ] Servidor central en Python (ingesta multi-nodo + YOLO + tracking)
- [ ] Persistencia en MySQL
- [ ] Dashboard / reportes

# Videos de ejemplo

Grabaciones reales de ratones para validar detección y tracking sin
depender de un nodo ESP32-CAM conectado. Los `.mp4` no se suben a git
(pesan varios GB, ver `.gitignore`): este README describe qué hay en cada
carpeta para poder reconstruirla desde el origen (carpeta compartida de
Drive).

| Carpeta | Archivo | Resolución / FPS / duración | Contenido |
|---|---|---|---|
| `open_field/` | `VID_20231009_114251.mp4` | 1280×720 · 29.7 fps · 7.3 min | Arena de campo abierto, vista cenital, piso blanco con grilla de cinta negra (4×3). **Un** ratón blanco, buena iluminación. Es el caso más parecido al montaje del proyecto. |
| `caja_cenital_2024/` | `XVR_ch1_main_20241027153700_20241027162425.mp4` | 960×1080 · 15 fps · 47 min | DVR, cámara mirando hacia abajo dentro de una caja blanca profunda (lente gran angular). Ratón blanco sobre fondo blanco: bajo contraste. Overlay de fecha/hora y "CAM 1". |
| `caja_cenital_2024/` | `XVR_ch2_main_20241027153700_20241027162500.mp4` | 960×1080 · 12 fps · 48 min | Misma sesión, segunda cámara: caja de paredes negras, poca luz. Overlay "CAM 2". |
| `jaulas_laterales_2021/` | `XVR_ch2_main_20210720140749_20210720150000.mp4` | 960×1080 · 12 fps · 52 min | Vista lateral/oblicua de jaulas de vidrio con viruta, **varios** ratones blancos (algunos marcados con color), reflejos en el vidrio. Caso difícil, útil para probar el tracker con varios animales. |

Uso con el visor de depuración (ver `server/README.md`):

```bash
uv run --package bioterio-server bioterio-debug-view data/videos/open_field/VID_20231009_114251.mp4
```

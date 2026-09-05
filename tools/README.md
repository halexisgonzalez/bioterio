# bioterio-tools

Utilidades en Python para validar y depurar los nodos ESP32-CAM del
bioterio desde la PC. Es parte del workspace de `uv` del repo (junto con
[`server/`](../server), que reutiliza `node_client.py` de acá para no
duplicar código).

## Estructura

```
tools/
├── pyproject.toml
└── src/bioterio_tools/
    ├── node_client.py   → cliente HTTP del nodo (status, stream) — reutilizable
    ├── mjpeg_stream.py  → lector del stream MJPEG (ver nota abajo)
    └── view_stream.py   → CLI que usa node_client para mostrar el video
```

`node_client.py` está separado del CLI a propósito: no sabe nada de
argparse ni de ventanas, así que `bioterio-server` (el servidor central
que consume el stream de todos los nodos para correr detección +
tracking) lo importa tal cual en vez de reescribir esta lógica.

### Por qué `mjpeg_stream.py` y no `cv2.VideoCapture`

`cv2.VideoCapture` (con el backend FFmpeg de OpenCV) no logra abrir el
stream multipart que expone el firmware del nodo — se cuelga ~30 segundos
y falla sin conectar (validado contra hardware real). `MjpegStream` lee el
stream a mano con `requests` y decodifica cada frame JPEG con
`cv2.imdecode`, con una interfaz (`isOpened`/`read`/`release`) parecida a
la de `cv2.VideoCapture` para que el resto del código casi no note la
diferencia. Como ventaja adicional, al no depender del cliente HTTP
interno de OpenCV, si el nodo tiene `API_KEY` habilitada el header
`X-API-Key` se puede mandar también al abrir el video (no solo en
`/status`).

## Instalar

Desde la **raíz del repo** (el workspace de `uv` cubre `tools/` y
`server/` con un solo entorno):

```bash
uv sync --all-packages
```

## Uso

```bash
# Ver el stream en vivo (abre una ventana, 'q' para cerrar)
uv run --package bioterio-tools bioterio-view-stream 192.168.0.160

# También funciona con el nombre mDNS del nodo
uv run --package bioterio-tools bioterio-view-stream jaula_01.local

# Solo validar que el nodo responde, sin abrir ventana (útil en scripts)
uv run --package bioterio-tools bioterio-view-stream jaula_01.local --no-display

# Logs más detallados
uv run --package bioterio-tools bioterio-view-stream jaula_01.local -v

# Si el nodo tiene API_KEY habilitada en su config.h
uv run --package bioterio-tools bioterio-view-stream jaula_01.local --api-key "el-valor-configurado"
```

(Parado dentro de la carpeta `tools/`, `--package bioterio-tools` se
puede omitir.)

## Desarrollo

```bash
uv run ruff check .   # lint
```

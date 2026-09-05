# bioterio-tools

Utilidades en Python para validar y depurar los nodos ESP32-CAM del
bioterio desde la PC, antes/mientras se arma el servidor central de
tracking. Gestionado con [`uv`](https://docs.astral.sh/uv/) — no hace
falta crear ni activar un virtualenv a mano.

## Estructura

```
tools/
├── pyproject.toml
├── uv.lock
└── src/bioterio_tools/
    ├── node_client.py   → cliente HTTP del nodo (status, stream) — reutilizable
    └── view_stream.py   → CLI que usa node_client para mostrar el video
```

`node_client.py` está separado del CLI a propósito: no sabe nada de
argparse ni de ventanas, así que el futuro servidor central en Python
(el que va a consumir el stream de todos los nodos para correr YOLO +
tracking) puede importarlo tal cual en vez de reescribir esta lógica.

## Instalar

```bash
cd tools
uv sync
```

Esto crea un `.venv` local y descarga exactamente las versiones fijadas en
`uv.lock`.

## Uso

```bash
# Ver el stream en vivo (abre una ventana, 'q' para cerrar)
uv run bioterio-view-stream 192.168.0.160

# También funciona con el nombre mDNS del nodo
uv run bioterio-view-stream jaula_01.local

# Solo validar que el nodo responde, sin abrir ventana (útil en scripts)
uv run bioterio-view-stream jaula_01.local --no-display

# Logs más detallados
uv run bioterio-view-stream jaula_01.local -v
```

Si el nodo tiene `API_KEY` habilitada en su `config.h`:

```bash
uv run bioterio-view-stream jaula_01.local --api-key "el-valor-configurado"
```

**Nota:** la API key solo se envía al pedir `/status` — OpenCV no permite
mandar headers custom al abrir una URL de video, así que si el nodo exige
autenticación, la validación del stream en sí hay que hacerla con otra
herramienta (ej. `curl -H "X-API-Key: ..." http://<host>:81/stream`). Para
uso normal en la red interna del bioterio, `API_KEY` se deja deshabilitada
(ver README del firmware).

## Desarrollo

```bash
uv run ruff check .   # lint
```

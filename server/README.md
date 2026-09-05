# bioterio-server

Servidor central: consume el stream de todos los nodos ESP32-CAM, detecta
y trackea a los animales, y guarda los resultados en MySQL. Gestionado con
[`uv`](https://docs.astral.sh/uv/), como parte del workspace del repo
(comparte código con [`tools/`](../tools) — ver `bioterio_tools.node_client`).

## Arquitectura

```
src/bioterio_server/
├── main.py                          → arma todo, corre el loop principal, apagado ordenado
├── config.py                        → carga .env, único lugar que lee variables de entorno
├── nodes.py / zones.py              → parseo de configuración (lista de nodos, zonas de interés)
├── detection/
│   ├── base.py                      → interfaz Detector (Protocol) — punto de extensión
│   ├── background_subtraction.py    → detector v1: resta de fondo (MOG2), sin modelo entrenado
│   ├── yolo_detector.py             → detector basado en YOLO (ultralytics)
│   └── factory.py                   → elige el detector según DETECTOR_BACKEND
├── tracking/
│   └── centroid_tracker.py          → asigna IDs estables a los centroides detectados
├── pipeline/
│   └── node_worker.py               → un hilo por nodo: captura → detección → tracking → cola
└── storage/
    ├── models.py                    → PositionSample (fila tipada)
    └── mysql_repository.py          → único lugar del proyecto que escribe SQL
```

Cada nodo corre en su propio hilo (`NodeWorker`), aislado de los demás: si
a uno se le corta la conexión, reintenta solo y no afecta a los otros. Las
muestras de todos los nodos se acumulan en una cola compartida y se
escriben en MySQL por lotes cada `BATCH_FLUSH_INTERVAL_S` segundos (no en
cada frame), para no saturar la base de datos.

### Sobre el detector v1 (importante)

Todavía no hay un dataset propio ni un modelo entrenado para reconocer al
roedor, así que el detector actual (`BackgroundSubtractionDetector`) usa
resta de fondo (MOG2): compara cada frame contra un modelo del fondo
"vacío" de la jaula y marca como detección cualquier mancha que se mueve
dentro de un rango de tamaño esperable para un ratón. Funciona sin
entrenar nada, pero:

- Puede confundir sombras marcadas, movimiento del aserrín o reflejos con
  el animal.
- No distingue "ratón" de "cualquier otra cosa que se mueva" del tamaño
  correcto.
- Necesita unos segundos al arrancar para "aprender" cómo es el fondo
  quieto (evitar mover objetos de la jaula justo al iniciar el servidor).

### Sobre el detector YOLO (`yolo_detector.py`)

Ya existe una segunda implementación de `Detector` basada en
[ultralytics](https://docs.ultralytics.com/) (YOLO11). Se elige con:

```bash
# en .env
DETECTOR_BACKEND=yolo
YOLO_MODEL_PATH=yolo11n.pt   # o la ruta a un modelo propio (.pt)
YOLO_CONFIDENCE=0.4
YOLO_CLASSES=                # vacío = todas las clases del modelo

# o por línea de comandos, con debug_view:
uv run --package bioterio-server bioterio-debug-view <ip> --detector yolo
```

**Estado actual — importante**: por defecto usa `yolo11n.pt`, un modelo
pre-entrenado en COCO. **COCO no tiene una clase "ratón"/"rata"**, así que
esto sirve para probar que el cableado funciona (carga del modelo,
inferencia, conversión a `Detection`, tracking) pero no va a reconocer al
roedor de forma útil — confirmado con hardware real: en una imagen de
prueba sin ningún objeto de COCO, el modelo "adivinó" un paraguas con 46%
de confianza en una esquina oscura cualquiera.

Para detección real de roedores hay dos caminos, ninguno resuelto todavía:

1. **Modelo pre-entrenado de terceros**: existen modelos públicos de
   detección de roedores en [Roboflow Universe](https://universe.roboflow.com/)
   (ej. [DID-Rodent-YOLOv8](https://universe.roboflow.com/winter-zebrafish-test/did-rodent-yolov8),
   1510 imágenes). Requiere crear una cuenta gratuita de Roboflow, generar
   un API key, y descargar el `.pt` — después basta con apuntar
   `YOLO_MODEL_PATH` a ese archivo. Calidad no verificada todavía.
2. **Modelo propio**: una vez que haya video real de un ratón en la jaula
   final, recolectar frames, anotarlos (bounding boxes) y entrenar/afinar
   un YOLO propio con `ultralytics` (`yolo train ...`).

Mientras tanto, `background_subtraction` sigue siendo el detector por
defecto — no es mejor en precisión, pero no depende de descargar nada.

**GPU**: en una máquina con GPU NVIDIA, `pip`/`uv` instalan por defecto el
build de PyTorch sin CUDA (mucho más liviano) a menos que se apunte
explícitamente al índice de PyTorch con soporte CUDA. Con un modelo nano
la CPU alcanza para probar; para producción con más nodos/FPS conviene
configurar el índice CUDA (pendiente, no bloqueante).

### Sobre el tracker (importante)

`CentroidTracker` es un algoritmo clásico y liviano (sin dependencias de
ML): empareja cada detección nueva con el track existente más cercano.
Si dos animales se cruzan o quedan amontonados, puede intercambiar sus
IDs — la misma limitación que se documentó desde el diseño original del
proyecto. Para identidad robusta con varios animales hace falta
re-identificación visual (marcas de color o un modelo entrenado).

## 1. Levantar MySQL

Con Docker (recomendado para empezar):

```bash
cd server
docker compose up -d
```

Esto crea la base `bioterio` con el esquema de [`schema.sql`](schema.sql)
ya aplicado. Si usás un MySQL propio en vez de Docker, corré
`mysql < schema.sql` a mano una vez.

## 2. Configurar

```bash
cp .env.example .env
```

Completá `BIOTERIO_NODES` con tus nodos reales, por ejemplo:

```
BIOTERIO_NODES=jaula_01=192.168.0.160,jaula_02=jaula_02.local
```

Si usaste `docker compose up` con los valores por defecto, el resto del
`.env` (usuario/contraseña de MySQL) ya viene alineado — no hace falta
tocarlo.

## 3. Instalar y correr

Desde la raíz del repo (el workspace de `uv` cubre `tools/` y `server/`
con un solo entorno):

```bash
uv sync --all-packages
uv run --package bioterio-server bioterio-server
```

Vas a ver logs por cada nodo conectándose, y cada `BATCH_FLUSH_INTERVAL_S`
segundos un resumen de cuántas muestras se escribieron. `Ctrl+C` hace un
apagado ordenado (detiene los workers y cierra la conexión a MySQL antes
de salir).

## 4. Verificar los datos

```bash
docker compose exec mysql mysql -ubioterio -pbioterio bioterio \
  -e "SELECT node_id, track_id, pos_x, pos_y, is_moving, sampled_at FROM position_samples ORDER BY sampled_at DESC LIMIT 10;"
```

## Notas de diseño

- **Unidades**: `pos_x`/`pos_y` están en píxeles del frame, no en
  centímetros. Convertir a distancia real requiere calibrar píxeles→cm
  usando el tamaño conocido de la jaula (se guardan `frame_width`/
  `frame_height` en cada fila justamente para poder hacer esa cuenta más
  adelante sin volver a grabar nada).
- **Resiliencia**: si MySQL se cae, el servidor sigue acumulando muestras
  en memoria (hasta un tope de `MAX_BUFFERED_SAMPLES`, después descarta
  las más viejas) y reintenta en el siguiente ciclo de flush — no se
  cae ni pierde los nodos conectados por un corte de la base de datos.
  Ojo: esto cubre cortes de la base de datos, no una muerte abrupta del
  proceso del servidor (`kill -9`, corte de luz) — en ese caso se pierde
  como máximo el último `BATCH_FLUSH_INTERVAL_S` de muestras sin escribir
  todavía. Un `Ctrl+C` normal sí hace un apagado ordenado sin perder nada
  (ver `main.py`).
- **Pendiente / próximos pasos**: detectar oclusión total (cuando el
  animal entra a una casa cerrada y desaparece del todo) para registrar
  explícitamente el estado "oculto" en vez de simplemente dejar de
  emitir muestras; conseguir un modelo YOLO que reconozca roedores de
  verdad (ver sección de detección YOLO arriba); dashboard de reportes
  sobre estos datos.

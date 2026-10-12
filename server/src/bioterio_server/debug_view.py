"""CLI de depuración visual: reutiliza el detector y el tracker reales del
servidor, pero en vez de guardar en MySQL dibuja las detecciones y los
tracks encima del video en una ventana.

Sirve para confirmar visualmente que el pipeline de visión por computadora
está haciendo algo — hasta ahora solo se veía el video crudo (el nodo) o
números sueltos en una tabla (MySQL), nunca la parte de "qué ve el
algoritmo".

La fuente puede ser un nodo (IP/hostname) o un archivo de video grabado
(ver data/videos/): con un archivo se puede validar detección y tracking
contra ratones reales sin tener un nodo conectado, y repetir exactamente
la misma prueba al comparar detectores o ajustar parámetros.

Uso:
    uv run bioterio-debug-view 192.168.0.160
    uv run bioterio-debug-view data/videos/open_field/VID_20231009_114251.mp4
    uv run bioterio-debug-view <video> --no-display --output anotado.mp4 --max-seconds 60
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
from bioterio_tools.node_client import (
    DEFAULT_CONNECT_RETRIES,
    NodeEndpoints,
    NodeUnreachableError,
    open_stream,
)

from bioterio_server.detection.base import Detector
from bioterio_server.detection.factory import VALID_BACKENDS, build_detector
from bioterio_server.tracking.centroid_tracker import CentroidTracker, Track

logger = logging.getLogger(__name__)

_TRACK_COLORS = [
    (0, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
    (0, 255, 255),
    (255, 0, 255),
    (255, 255, 0),
]

_MAX_DISPLAY_WIDTH = 1280


def _color_for(track_id: int) -> tuple[int, int, int]:
    return _TRACK_COLORS[track_id % len(_TRACK_COLORS)]


def _draw_detection_boxes(frame, detections) -> None:
    """Recuadros verdes finos: todo lo que el detector marcó como "se mueve",
    antes de que el tracker le asigne (o no) una identidad estable."""
    for d in detections:
        x1 = int(d.center_x - d.width / 2)
        y1 = int(d.center_y - d.height / 2)
        x2 = int(d.center_x + d.width / 2)
        y2 = int(d.center_y + d.height / 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 1)


def _draw_tracks(frame, tracks: dict[int, Track]) -> None:
    """Punto + ID de color: los tracks con identidad estable, solo los que
    se vieron en este frame (disappeared_frames == 0)."""
    for track in tracks.values():
        if track.disappeared_frames > 0:
            continue
        color = _color_for(track.track_id)
        center = (int(track.center_x), int(track.center_y))
        cv2.circle(frame, center, 6, color, -1)
        cv2.putText(
            frame,
            f"ID {track.track_id}",
            (center[0] + 10, center[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )


@dataclass
class RunStats:
    """Resumen de una corrida, para comparar detectores/parámetros con números
    y no solo a ojo. Con un único animal en cuadro, lo ideal es
    frames_with_detection ~= frames y tracks_created == 1."""

    frames: int = 0
    frames_with_detection: int = 0
    frames_with_multiple: int = 0
    total_detections: int = 0
    tracks_created: int = 0

    def log_summary(self) -> None:
        if not self.frames:
            logger.info("No se procesó ningún frame")
            return
        logger.info(
            "Resumen: %d frames | con detección: %.1f%% | con >1 detección: %.1f%% | "
            "detecciones/frame: %.2f | tracks creados: %d",
            self.frames,
            100 * self.frames_with_detection / self.frames,
            100 * self.frames_with_multiple / self.frames,
            self.total_detections / self.frames,
            self.tracks_created,
        )


class _VideoFileSource:
    """Archivo de video con la misma interfaz read()/release() que el stream
    de un nodo. Al terminar el archivo read() devuelve (False, None), igual
    que un stream cortado — la diferencia es que acá no se reconecta."""

    def __init__(self, path: Path, start_s: float) -> None:
        self._capture = cv2.VideoCapture(str(path))
        if not self._capture.isOpened():
            raise OSError(f"No se pudo abrir el video {path}")
        self.fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0
        if start_s > 0:
            self._capture.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000)

    def read(self):
        return self._capture.read()

    def release(self) -> None:
        self._capture.release()


def run(
    source: str,
    detector: Detector,
    display: bool = True,
    output_path: Path | None = None,
    start_s: float = 0.0,
    max_seconds: float | None = None,
) -> RunStats:
    is_file = Path(source).is_file()
    if is_file:
        stream = _VideoFileSource(Path(source), start_s)
        fps = stream.fps
    else:
        endpoints = NodeEndpoints(host=source)
        stream = open_stream(endpoints)
        fps = 10.0  # el nodo no informa FPS; solo se usa para el video de salida

    tracker = CentroidTracker()
    stats = RunStats()
    writer = None
    window_name = f"Debug CV - {source} (q para salir)"
    max_frames = int(max_seconds * fps) if max_seconds else None

    logger.info(
        "Fuente abierta. El detector de resta de fondo necesita unos segundos para "
        "'aprender' cómo es el fondo quieto — evitá mover objetos de la jaula recién al arrancar."
    )

    try:
        consecutive_failures = 0
        while max_frames is None or stats.frames < max_frames:
            ok, frame = stream.read()
            if not ok:
                if is_file:
                    logger.info("Fin del video")
                    break
                consecutive_failures += 1
                logger.warning("Frame perdido (%d seguidos)", consecutive_failures)
                if consecutive_failures >= DEFAULT_CONNECT_RETRIES:
                    logger.error("Demasiados frames perdidos seguidos, reconectando...")
                    stream.release()
                    stream = open_stream(endpoints)
                    consecutive_failures = 0
                else:
                    time.sleep(0.5)  # evita un loop apretado mientras se decide reconectar
                continue

            consecutive_failures = 0
            detections = detector.detect(frame)
            centroids = [(d.center_x, d.center_y) for d in detections]
            tracks = tracker.update(centroids)

            stats.frames += 1
            stats.total_detections += len(detections)
            stats.frames_with_detection += bool(detections)
            stats.frames_with_multiple += len(detections) > 1
            stats.tracks_created = max(stats.tracks_created, max(tracks, default=-1) + 1)

            annotated = frame.copy()
            _draw_detection_boxes(annotated, detections)
            _draw_tracks(annotated, tracks)
            cv2.putText(
                annotated,
                f"frame {stats.frames}  detecciones: {len(detections)}  tracks activos: {len(tracks)}",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

            if output_path is not None:
                if writer is None:
                    height, width = annotated.shape[:2]
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    writer = cv2.VideoWriter(
                        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
                    )
                writer.write(annotated)

            if display:
                if annotated.shape[1] > _MAX_DISPLAY_WIDTH:
                    scale = _MAX_DISPLAY_WIDTH / annotated.shape[1]
                    annotated = cv2.resize(annotated, None, fx=scale, fy=scale)
                cv2.imshow(window_name, annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        stream.release()
        if writer is not None:
            writer.release()
        if display:
            cv2.destroyAllWindows()

    stats.log_summary()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "source",
        help="IP/hostname del nodo (ej: 192.168.0.160 o jaula_01.local) o ruta a un archivo de video",
    )
    parser.add_argument(
        "--detector",
        choices=VALID_BACKENDS,
        default="background_subtraction",
        help="Motor de detección a usar (default: background_subtraction)",
    )
    parser.add_argument("--yolo-model", default="yolo11n.pt", help="Ruta o nombre del modelo YOLO")
    parser.add_argument("--yolo-confidence", type=float, default=0.4)
    parser.add_argument(
        "--yolo-classes",
        default=None,
        help="Clases a filtrar, separadas por coma (ej: 'cat,dog'). Vacío = todas.",
    )
    parser.add_argument("--no-display", action="store_true", help="No abrir ventana (útil con --output)")
    parser.add_argument("--output", type=Path, default=None, help="Guardar el video anotado en este .mp4")
    parser.add_argument("--start", type=float, default=0.0, help="Segundo del video desde el cual arrancar")
    parser.add_argument("--max-seconds", type=float, default=None, help="Procesar como máximo N segundos")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    detector = build_detector(
        backend=args.detector,
        yolo_model_path=args.yolo_model,
        yolo_confidence=args.yolo_confidence,
        yolo_classes=args.yolo_classes.split(",") if args.yolo_classes else None,
    )

    try:
        run(
            args.source,
            detector,
            display=not args.no_display,
            output_path=args.output,
            start_s=args.start,
            max_seconds=args.max_seconds,
        )
    except (NodeUnreachableError, OSError) as exc:
        logger.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

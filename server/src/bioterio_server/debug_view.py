"""CLI de depuración visual: reutiliza el detector y el tracker reales del
servidor, pero en vez de guardar en MySQL dibuja las detecciones y los
tracks encima del video en una ventana.

Sirve para confirmar visualmente que el pipeline de visión por computadora
está haciendo algo — hasta ahora solo se veía el video crudo (el nodo) o
números sueltos en una tabla (MySQL), nunca la parte de "qué ve el
algoritmo".

Uso:
    uv run bioterio-debug-view 192.168.0.160
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import cv2
from bioterio_tools.node_client import (
    DEFAULT_CONNECT_RETRIES,
    NodeEndpoints,
    NodeUnreachableError,
    open_stream,
)

from bioterio_server.detection.background_subtraction import (
    BackgroundSubtractionDetector,
)
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


def run(host: str) -> None:
    endpoints = NodeEndpoints(host=host)
    stream = open_stream(endpoints)
    detector = BackgroundSubtractionDetector()
    tracker = CentroidTracker()
    window_name = f"Debug CV - {host} (q para salir)"

    logger.info(
        "Stream abierto. El detector necesita unos segundos para 'aprender' "
        "cómo es el fondo quieto — evitá mover objetos de la jaula recién al arrancar."
    )

    try:
        consecutive_failures = 0
        while True:
            ok, frame = stream.read()
            if not ok:
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

            annotated = frame.copy()
            _draw_detection_boxes(annotated, detections)
            _draw_tracks(annotated, tracks)
            cv2.putText(
                annotated,
                f"detecciones: {len(detections)}  tracks activos: {len(tracks)}",
                (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

            cv2.imshow(window_name, annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        stream.release()
        cv2.destroyAllWindows()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="IP o hostname del nodo (ej: 192.168.0.160 o jaula_01.local)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        run(args.host)
    except NodeUnreachableError as exc:
        logger.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

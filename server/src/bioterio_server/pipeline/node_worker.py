"""Un hilo por nodo: lee su stream, detecta, trackea y encola muestras.

Cada worker corre de forma totalmente independiente de los demás nodos —
si a uno se le corta el wifi o se cuelga, no afecta a los otros. Cualquier
excepción se atrapa y el worker reintenta solo con backoff, en vez de
tirar abajo el proceso completo (un nodo con problemas no debe frenar el
registro de datos de los demás).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime, timezone

from bioterio_tools.node_client import NodeEndpoints, fetch_status, open_stream

from bioterio_server.detection.base import Detector
from bioterio_server.storage.models import PositionSample
from bioterio_server.tracking.centroid_tracker import CentroidTracker
from bioterio_server.zones import Zone

logger = logging.getLogger(__name__)

STATUS_REFRESH_INTERVAL_S = 10.0  # la temperatura no hace falta pedirla en cada muestra
WORKER_RETRY_DELAY_S = 5.0


class NodeWorker(threading.Thread):
    def __init__(
        self,
        node_id: str,
        host: str,
        detector: Detector,
        zones: list[Zone],
        sample_interval_s: float,
        movement_threshold_px: float,
        max_disappeared_frames: int,
        output_queue: queue.Queue[PositionSample],
        run_id: str,
    ) -> None:
        super().__init__(name=f"NodeWorker-{node_id}", daemon=True)
        self._node_id = node_id
        self._endpoints = NodeEndpoints(host=host)
        self._detector = detector
        self._zones = zones
        self._sample_interval_s = sample_interval_s
        self._movement_threshold_px = movement_threshold_px
        self._tracker = CentroidTracker(max_disappeared_frames=max_disappeared_frames)
        self._output_queue = output_queue
        self._run_id = run_id
        self._stop_event = threading.Event()
        self._last_positions: dict[int, tuple[float, float]] = {}
        self._cached_temp_c: float | None = None
        self._last_status_at = 0.0

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_once()
            except Exception:
                logger.exception(
                    "Fallo en el worker de %s, reintentando en %.0fs", self._node_id, WORKER_RETRY_DELAY_S
                )
                self._stop_event.wait(WORKER_RETRY_DELAY_S)

    def _run_once(self) -> None:
        logger.info("Conectando a %s (%s)...", self._node_id, self._endpoints.host)
        capture = open_stream(self._endpoints)
        logger.info("Nodo %s conectado, iniciando tracking", self._node_id)

        last_sample_at = 0.0
        try:
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    raise ConnectionError(f"Se perdió el stream de {self._node_id}")

                now = time.monotonic()
                if now - last_sample_at < self._sample_interval_s:
                    continue
                last_sample_at = now

                self._process_frame(frame, now)
        finally:
            capture.release()

    def _process_frame(self, frame, now: float) -> None:
        height, width = frame.shape[:2]
        detections = self._detector.detect(frame)
        centroids = [(d.center_x, d.center_y) for d in detections]
        tracks = self._tracker.update(centroids)

        if now - self._last_status_at >= STATUS_REFRESH_INTERVAL_S:
            status = fetch_status(self._endpoints)
            self._cached_temp_c = status.temp_c if status else None
            self._last_status_at = now

        sampled_at = datetime.now(timezone.utc)

        for track in tracks.values():
            if track.disappeared_frames > 0:
                continue  # no se vio al animal en este frame: no inventamos una posición

            cx, cy = track.center_x, track.center_y
            previous = self._last_positions.get(track.track_id)
            displacement = ((cx - previous[0]) ** 2 + (cy - previous[1]) ** 2) ** 0.5 if previous else 0.0
            is_moving = displacement >= self._movement_threshold_px
            self._last_positions[track.track_id] = (cx, cy)

            zone_label = next((z.label for z in self._zones if z.contains(cx, cy)), None)

            self._output_queue.put(
                PositionSample(
                    node_id=self._node_id,
                    track_id=f"{self._run_id}:{track.track_id}",
                    sampled_at=sampled_at,
                    pos_x=cx,
                    pos_y=cy,
                    frame_width=width,
                    frame_height=height,
                    is_moving=is_moving,
                    zone_label=zone_label,
                    temp_c=self._cached_temp_c,
                )
            )

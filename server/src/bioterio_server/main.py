"""Punto de entrada del servidor central.

Arranca un NodeWorker por nodo configurado, y cada BATCH_FLUSH_INTERVAL_S
segundos drena todo lo que se acumuló en la cola compartida y lo escribe
en MySQL de una sola vez (bulk insert) — evita miles de INSERTs sueltos
por segundo, tal como se pensó desde el diseño original del proyecto.
"""

from __future__ import annotations

import logging
import queue
import signal
import threading
import uuid

from bioterio_server.config import load_settings
from bioterio_server.detection.factory import build_detector
from bioterio_server.pipeline.node_worker import NodeWorker
from bioterio_server.storage.models import PositionSample
from bioterio_server.storage.mysql_repository import MySQLRepository

logger = logging.getLogger(__name__)

# Cota de seguridad: si MySQL queda caído por mucho tiempo, no crecemos la
# memoria sin límite — se descartan las muestras más viejas y se sigue.
MAX_BUFFERED_SAMPLES = 50_000


def _install_shutdown_handler(stop_event: threading.Event) -> None:
    def _handle(*_args: object) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle)
        except (ValueError, AttributeError, OSError):
            pass  # SIGTERM no siempre está disponible (ej. algunos entornos Windows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = load_settings()
    run_id = uuid.uuid4().hex[:8]
    logger.info("Iniciando servidor central (run_id=%s) con %d nodo(s)", run_id, len(settings.nodes))

    repository = MySQLRepository(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
    )

    output_queue: queue.Queue[PositionSample] = queue.Queue()
    workers: list[NodeWorker] = []
    for node in settings.nodes:
        repository.ensure_node_registered(node.node_id)
        # Un detector por nodo (no compartido): la resta de fondo necesita
        # su propio estado por cámara, y para YOLO evita tener que resolver
        # llamadas concurrentes de varios hilos sobre el mismo modelo.
        detector = build_detector(
            backend=settings.detector_backend,
            yolo_model_path=settings.yolo_model_path,
            yolo_confidence=settings.yolo_confidence,
            yolo_classes=settings.yolo_classes,
        )
        worker = NodeWorker(
            node_id=node.node_id,
            host=node.host,
            detector=detector,
            zones=settings.zones.get(node.node_id, []),
            sample_interval_s=settings.sample_interval_s,
            movement_threshold_px=settings.movement_threshold_px,
            max_disappeared_frames=settings.max_disappeared_frames,
            output_queue=output_queue,
            run_id=run_id,
        )
        worker.start()
        workers.append(worker)

    stop_event = threading.Event()
    _install_shutdown_handler(stop_event)

    pending: list[PositionSample] = []
    try:
        while not stop_event.is_set():
            stop_event.wait(settings.batch_flush_interval_s)
            _drain_queue_into(output_queue, pending)

            if len(pending) > MAX_BUFFERED_SAMPLES:
                dropped = len(pending) - MAX_BUFFERED_SAMPLES
                logger.warning("Buffer al límite, descartando %d muestras viejas", dropped)
                pending = pending[-MAX_BUFFERED_SAMPLES:]

            if not pending:
                continue

            try:
                repository.insert_samples(pending)
                pending.clear()
            except Exception:
                logger.exception(
                    "Fallo al escribir en MySQL, se reintenta en el próximo ciclo (%d muestras en espera)",
                    len(pending),
                )
    finally:
        logger.info("Deteniendo workers...")
        for worker in workers:
            worker.stop()
        for worker in workers:
            worker.join(timeout=5)
        repository.close()

    return 0


def _drain_queue_into(source: queue.Queue[PositionSample], destination: list[PositionSample]) -> None:
    while True:
        try:
            destination.append(source.get_nowait())
        except queue.Empty:
            return


if __name__ == "__main__":
    raise SystemExit(main())

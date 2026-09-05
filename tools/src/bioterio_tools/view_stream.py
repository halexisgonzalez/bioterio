"""CLI para validar un nodo ESP32-CAM del bioterio desde la PC.

Uso:
    uv run bioterio-view-stream 192.168.0.160
    uv run bioterio-view-stream jaula_01.local --no-display -v
"""

from __future__ import annotations

import argparse
import logging
import sys

import cv2

from bioterio_tools.node_client import (
    DEFAULT_CONNECT_RETRIES,
    DEFAULT_HTTP_PORT,
    DEFAULT_STREAM_PORT,
    NodeEndpoints,
    NodeUnreachableError,
    fetch_status,
    open_stream,
)

logger = logging.getLogger(__name__)


def display_stream(endpoints: NodeEndpoints) -> None:
    """Muestra el video en una ventana hasta que el usuario presione 'q'.

    Si se pierden muchos frames seguidos (no una falla puntual, sino el nodo
    realmente caído) reintenta reconectar en vez de trabarse mostrando el
    último frame para siempre.
    """
    capture = open_stream(endpoints)
    window_name = f"ESP32-CAM {endpoints.host}"

    try:
        consecutive_failures = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                consecutive_failures += 1
                logger.warning("Frame perdido (%d seguidos)", consecutive_failures)
                if consecutive_failures >= DEFAULT_CONNECT_RETRIES:
                    logger.error("Demasiados frames perdidos seguidos, reconectando...")
                    capture.release()
                    capture = open_stream(endpoints)
                    consecutive_failures = 0
                continue

            consecutive_failures = 0
            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="IP o hostname del nodo (ej: 192.168.0.160 o jaula_01.local)")
    parser.add_argument("--stream-port", type=int, default=DEFAULT_STREAM_PORT)
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument(
        "--api-key",
        default=None,
        help="Valor de API_KEY del nodo, si tiene autenticación habilitada (solo aplica a /status)",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Solo valida /status, no abre ventana de video (útil para scripts/CI)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    endpoints = NodeEndpoints(
        host=args.host,
        stream_port=args.stream_port,
        http_port=args.http_port,
        api_key=args.api_key,
    )

    status = fetch_status(endpoints)
    if status is not None:
        logger.info("Estado del nodo: %s", status)
    else:
        logger.warning("Sigo igual e intento abrir el stream aunque /status no respondió.")

    if args.no_display:
        return 0 if status is not None else 1

    try:
        display_stream(endpoints)
    except NodeUnreachableError as exc:
        logger.error(str(exc))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

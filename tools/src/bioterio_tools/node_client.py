"""Cliente HTTP para hablar con un nodo ESP32-CAM.

Separado de la lógica de línea de comandos (view_stream.py) a propósito:
este módulo no sabe nada de argparse ni de mostrar ventanas, así que se
puede reutilizar tal cual desde el futuro servidor central en Python que
va a consumir el stream de todos los nodos para correr tracking.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import cv2
import requests

logger = logging.getLogger(__name__)

DEFAULT_STREAM_PORT = 81
DEFAULT_HTTP_PORT = 80
DEFAULT_STATUS_TIMEOUT_S = 3.0
DEFAULT_CONNECT_RETRIES = 5
DEFAULT_RETRY_BACKOFF_S = 2.0


class NodeUnreachableError(Exception):
    """El nodo no respondió tras agotar los reintentos configurados."""


@dataclass(frozen=True)
class NodeEndpoints:
    """URLs de un nodo ESP32-CAM, derivadas de su host (IP o `<node_id>.local`)."""

    host: str
    stream_port: int = DEFAULT_STREAM_PORT
    http_port: int = DEFAULT_HTTP_PORT
    api_key: str | None = None

    @property
    def stream_url(self) -> str:
        return f"http://{self.host}:{self.stream_port}/stream"

    @property
    def status_url(self) -> str:
        return f"http://{self.host}:{self.http_port}/status"

    @property
    def capture_url(self) -> str:
        return f"http://{self.host}:{self.http_port}/capture"

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}


@dataclass
class NodeStatus:
    """Respuesta tipada de /status, en vez de pasar un dict suelto por todos lados."""

    node_id: str
    uptime_s: int
    rssi_dbm: int
    free_heap: int
    temp_c: float | None
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_json(cls, payload: dict) -> NodeStatus:
        return cls(
            node_id=payload.get("node_id", "?"),
            uptime_s=payload.get("uptime_s", 0),
            rssi_dbm=payload.get("rssi_dbm", 0),
            free_heap=payload.get("free_heap", 0),
            temp_c=payload.get("temp_c"),
            raw=payload,
        )


def fetch_status(
    endpoints: NodeEndpoints, timeout_s: float = DEFAULT_STATUS_TIMEOUT_S
) -> NodeStatus | None:
    """Devuelve el estado del nodo, o None si no respondió (nunca lanza por timeout/red)."""
    try:
        response = requests.get(
            endpoints.status_url, headers=endpoints.auth_headers, timeout=timeout_s
        )
        response.raise_for_status()
        return NodeStatus.from_json(response.json())
    except requests.RequestException as exc:
        logger.warning("No se pudo leer %s (%s)", endpoints.status_url, exc)
        return None


def open_stream(
    endpoints: NodeEndpoints,
    retries: int = DEFAULT_CONNECT_RETRIES,
    backoff_s: float = DEFAULT_RETRY_BACKOFF_S,
) -> cv2.VideoCapture:
    """Abre el stream MJPEG, reintentando con backoff si el nodo no responde todavía.

    Nota: OpenCV no permite mandar headers custom al abrir un stream por URL,
    así que si el nodo tiene API_KEY habilitada esto va a fallar — la
    autenticación hoy solo cubre /status y /capture (ver README).
    """
    for attempt in range(1, retries + 1):
        capture = cv2.VideoCapture(endpoints.stream_url)
        if capture.isOpened():
            return capture
        capture.release()
        logger.warning(
            "Intento %d/%d: no se pudo abrir %s", attempt, retries, endpoints.stream_url
        )
        time.sleep(backoff_s)
    raise NodeUnreachableError(f"No se pudo abrir el stream en {endpoints.stream_url}")

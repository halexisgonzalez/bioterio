"""Lector de streams MJPEG (multipart/x-mixed-replace) sobre HTTP.

`cv2.VideoCapture` (backend FFmpeg) no logra abrir el stream multipart que
expone el firmware del nodo: se cuelga ~30 segundos y falla sin conectar
(validado contra el nodo físico). En vez de depender de eso, este lector
es deliberadamente simple: acumula bytes del response hasta encontrar un
frame JPEG completo (delimitado por los marcadores estándar SOI/EOI,
0xFFD8...0xFFD9) y lo decodifica con `cv2.imdecode`. Como usamos
`requests` en vez del cliente HTTP interno de OpenCV, de paso podemos
mandar headers custom (por ejemplo X-API-Key si el nodo tiene
autenticación habilitada), cosa que con `cv2.VideoCapture` no era posible.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"
_MAX_BUFFER_BYTES = 2_000_000  # cota de seguridad si el stream viene corrupto y nunca cierra un frame


class MjpegStream:
    """Interfaz deliberadamente parecida a `cv2.VideoCapture` (isOpened/read/release)
    para que reemplazarlo en el código existente sea un cambio mínimo."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        chunk_size: int = 4096,
        timeout_s: float = 10.0,
    ) -> None:
        self._url = url
        self._headers = headers or {}
        self._chunk_size = chunk_size
        self._timeout_s = timeout_s
        self._response: requests.Response | None = None
        self._iterator = None
        self._buffer = b""

    def open(self) -> bool:
        try:
            self._response = requests.get(
                self._url, headers=self._headers, stream=True, timeout=self._timeout_s
            )
            self._response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("No se pudo abrir %s (%s)", self._url, exc)
            self._response = None
            return False
        self._iterator = self._response.iter_content(chunk_size=self._chunk_size)
        self._buffer = b""
        return True

    def isOpened(self) -> bool:
        return self._response is not None

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._iterator is None:
            return False, None
        try:
            while True:
                start = self._buffer.find(_JPEG_SOI)
                end = self._buffer.find(_JPEG_EOI, start + 2) if start != -1 else -1
                if start != -1 and end != -1:
                    jpg_bytes = self._buffer[start : end + 2]
                    self._buffer = self._buffer[end + 2 :]
                    frame = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        return True, frame
                    continue  # frame corrupto: seguimos buscando el siguiente

                chunk = next(self._iterator)
                self._buffer += chunk
                if len(self._buffer) > _MAX_BUFFER_BYTES:
                    logger.warning("Buffer de stream muy grande sin encontrar un frame, se descarta")
                    self._buffer = self._buffer[-4096:]
        except (StopIteration, requests.RequestException) as exc:
            logger.warning("Stream cortado (%s)", exc)
            return False, None

    def release(self) -> None:
        if self._response is not None:
            self._response.close()
        self._response = None
        self._iterator = None

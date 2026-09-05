"""Interfaz que debe cumplir cualquier estrategia de detección.

El resto del pipeline (tracking, métricas, storage) solo conoce esta
interfaz — nunca sabe si por debajo hay resta de fondo o un modelo YOLO
entrenado. Esto es lo que permite reemplazar `BackgroundSubtractionDetector`
por un `YoloDetector` el día que haya un dataset propio, agregando una
clase nueva sin tocar ninguna otra (principio abierto/cerrado).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Detection:
    """Un objeto detectado en un frame, en coordenadas de píxel."""

    center_x: float
    center_y: float
    width: float
    height: float


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...

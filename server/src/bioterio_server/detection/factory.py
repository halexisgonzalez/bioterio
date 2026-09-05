"""Fabrica el detector a usar según configuración.

Mantiene a main.py y debug_view.py desacoplados de las implementaciones
concretas — sumar un detector nuevo (ej. un modelo propio ya entrenado)
solo requiere agregarlo acá, sin tocar el resto del pipeline.
"""

from __future__ import annotations

from bioterio_server.detection.background_subtraction import (
    BackgroundSubtractionDetector,
)
from bioterio_server.detection.base import Detector
from bioterio_server.detection.yolo_detector import YoloDetector

VALID_BACKENDS = ("background_subtraction", "yolo")


def build_detector(
    backend: str,
    yolo_model_path: str = "yolo11n.pt",
    yolo_confidence: float = 0.4,
    yolo_classes: list[str] | None = None,
) -> Detector:
    normalized = backend.strip().lower()
    if normalized == "background_subtraction":
        return BackgroundSubtractionDetector()
    if normalized == "yolo":
        return YoloDetector(
            model_path=yolo_model_path,
            confidence_threshold=yolo_confidence,
            target_class_names=yolo_classes,
        )
    raise ValueError(f"DETECTOR_BACKEND desconocido: '{backend}' (opciones: {', '.join(VALID_BACKENDS)})")

"""Detector basado en un modelo YOLO (ultralytics).

Implementa la misma interfaz `Detector` que `BackgroundSubtractionDetector`
(detect(frame) -> list[Detection]), así que reemplazar uno por otro no
requiere tocar tracking, métricas ni storage — es exactamente el punto de
extensión que se dejó preparado desde el diseño original.

IMPORTANTE — estado actual (ver server/README.md para el detalle):
Por defecto usa un modelo pre-entrenado en COCO (ej. "yolo11n.pt"), que
**no tiene una clase "ratón"/"rata"**. Sirve para validar que todo el
cableado (carga del modelo, inferencia, conversión a Detection, tracking)
funciona de punta a punta, pero no va a detectar al roedor de forma
confiable todavía. Para eso hace falta apuntar YOLO_MODEL_PATH a un
modelo entrenado específicamente para roedores (público, vía Roboflow u
otro origen, o uno propio entrenado con imágenes reales de la jaula).
"""

from __future__ import annotations

import logging

import numpy as np
from ultralytics import YOLO

from bioterio_server.detection.base import Detection

logger = logging.getLogger(__name__)


class YoloDetector:
    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.4,
        target_class_names: list[str] | None = None,
    ) -> None:
        # Si model_path es un nombre conocido (ej. "yolo11n.pt") y no existe
        # localmente, ultralytics lo descarga solo la primera vez.
        self._model = YOLO(model_path)
        self._confidence_threshold = confidence_threshold
        self._target_class_names = (
            {name.strip().lower() for name in target_class_names} if target_class_names else None
        )

        available = set(self._model.names.values())
        if self._target_class_names and not self._target_class_names & {c.lower() for c in available}:
            logger.warning(
                "Ninguna de las clases pedidas %s existe en el modelo %s (clases disponibles: %s)",
                sorted(self._target_class_names),
                model_path,
                sorted(available),
            )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # verbose=False: evita que ultralytics imprima una línea de log por frame.
        results = self._model.predict(frame, conf=self._confidence_threshold, verbose=False)

        detections = []
        for box in results[0].boxes:
            class_name = self._model.names[int(box.cls[0])]
            if self._target_class_names and class_name.lower() not in self._target_class_names:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    center_x=(x1 + x2) / 2,
                    center_y=(y1 + y2) / 2,
                    width=x2 - x1,
                    height=y2 - y1,
                )
            )
        return detections

"""Detector v1: resta de fondo (MOG2) + contornos.

No requiere ningún modelo entrenado ni dataset propio — funciona apenas se
instala el proyecto, a costa de ser menos preciso que un modelo entrenado
específicamente para el roedor (puede confundir sombras marcadas o
movimiento del aserrín con el animal, y no distingue "ratón" de "otro
objeto que se mueve"). Implementa la misma interfaz `Detector` que
usaría un futuro `YoloDetector`, así que reemplazarlo más adelante no
requiere tocar tracking, métricas ni storage.
"""

from __future__ import annotations

import cv2
import numpy as np

from bioterio_server.detection.base import Detection


class BackgroundSubtractionDetector:
    # min_area_px en ~600: un ratón adulto ocupa un bounding box de varios
    # miles de píxeles en VGA (ver docs/etapa1-investigacion-hardware.md);
    # el ruido de compresión JPEG / parpadeo de luces genera blobs de
    # apenas decenas de píxeles, así que un umbral bajo (150 originalmente)
    # dejaba pasar puro ruido — confirmado con hardware real: sin sujeto
    # real en cuadro, generaba varios tracks efímeros en posiciones fijas.
    def __init__(self, min_area_px: int = 600, max_area_px: int = 20000) -> None:
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=40, detectShadows=True
        )
        self._min_area_px = min_area_px
        self._max_area_px = max_area_px

    def detect(self, frame: np.ndarray) -> list[Detection]:
        mask = self._subtractor.apply(frame)
        # 127: descarta la zona gris que MOG2 marca como sombra (detectShadows=True),
        # nos quedamos solo con el blanco (movimiento real).
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        # Erosiona primero con un kernel más grande para borrar el ruido
        # chico (compresión JPEG, parpadeo) antes de buscar contornos.
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not (self._min_area_px <= area <= self._max_area_px):
                continue
            x, y, w, h = cv2.boundingRect(contour)
            detections.append(Detection(center_x=x + w / 2, center_y=y + h / 2, width=w, height=h))
        return detections

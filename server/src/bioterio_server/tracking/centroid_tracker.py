"""Tracker de centroides: asigna un ID estable a cada detección, cuadro a cuadro.

Algoritmo clásico (greedy nearest-centroid), liviano y sin dependencias de
ML — a diferencia de ByteTrack/BoT-SORT no necesita torch ni un modelo.
Limitación conocida y documentada desde el diseño original del proyecto:
si dos animales se cruzan o quedan amontonados, el tracker puede
intercambiar sus IDs. Para identidad robusta con varios animales hace
falta re-identificación visual (marcas de color o un modelo entrenado),
fuera del alcance de este v1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Track:
    track_id: int
    center_x: float
    center_y: float
    disappeared_frames: int = 0


def _pairwise_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Matriz de distancias euclídeas entre cada fila de `a` y cada fila de `b`."""
    diff = a[:, None, :] - b[None, :, :]
    return np.sqrt((diff**2).sum(axis=2))


class CentroidTracker:
    def __init__(self, max_disappeared_frames: int = 30, max_match_distance_px: float = 100.0) -> None:
        self._next_id = 0
        self._tracks: dict[int, Track] = {}
        self._max_disappeared_frames = max_disappeared_frames
        self._max_match_distance_px = max_match_distance_px

    def update(self, centroids: list[tuple[float, float]]) -> dict[int, Track]:
        if not centroids:
            for track in list(self._tracks.values()):
                track.disappeared_frames += 1
                if track.disappeared_frames > self._max_disappeared_frames:
                    del self._tracks[track.track_id]
            return dict(self._tracks)

        if not self._tracks:
            for cx, cy in centroids:
                self._register(cx, cy)
            return dict(self._tracks)

        track_ids = list(self._tracks.keys())
        existing = np.array([[self._tracks[tid].center_x, self._tracks[tid].center_y] for tid in track_ids])
        incoming = np.array(centroids)
        distances = _pairwise_distances(existing, incoming)

        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()

        # Empareja de menor a mayor distancia (greedy), sin reusar un track o
        # una detección ya emparejados.
        for flat_idx in np.argsort(distances, axis=None):
            track_idx, detection_idx = np.unravel_index(flat_idx, distances.shape)
            if track_idx in matched_tracks or detection_idx in matched_detections:
                continue
            if distances[track_idx, detection_idx] > self._max_match_distance_px:
                continue
            track_id = track_ids[track_idx]
            cx, cy = centroids[detection_idx]
            self._tracks[track_id].center_x = cx
            self._tracks[track_id].center_y = cy
            self._tracks[track_id].disappeared_frames = 0
            matched_tracks.add(track_idx)
            matched_detections.add(detection_idx)

        for track_idx, tid in enumerate(track_ids):
            if track_idx not in matched_tracks:
                self._tracks[tid].disappeared_frames += 1
                if self._tracks[tid].disappeared_frames > self._max_disappeared_frames:
                    del self._tracks[tid]

        for detection_idx, (cx, cy) in enumerate(centroids):
            if detection_idx not in matched_detections:
                self._register(cx, cy)

        return dict(self._tracks)

    def _register(self, cx: float, cy: float) -> None:
        self._tracks[self._next_id] = Track(track_id=self._next_id, center_x=cx, center_y=cy)
        self._next_id += 1

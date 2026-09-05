from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PositionSample:
    """Una posición muestreada de un track en un instante dado.

    pos_x/pos_y están en píxeles del frame tal como lo entrega el nodo (no
    en centímetros): convertir a distancia real requiere calibrar
    píxeles→cm con el tamaño conocido de la jaula — queda pendiente como
    mejora futura (ver README), por eso se guardan también frame_width y
    frame_height, para poder calcularlo después sin volver a grabar nada.
    """

    node_id: str
    track_id: str
    sampled_at: datetime
    pos_x: float
    pos_y: float
    frame_width: int
    frame_height: int
    is_moving: bool
    zone_label: str | None
    temp_c: float | None

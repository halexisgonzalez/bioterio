"""Zonas de interés por nodo (comedero, casa, etc.) para clasificar posiciones.

No resuelve oclusión total (cuando el animal entra a una casa cerrada y la
detección lo pierde por completo) — eso queda documentado como mejora
futura en el README. Lo que sí permite: si el algoritmo de detección lo ve
parcialmente o la zona no lo tapa del todo, cada muestra queda etiquetada
con en qué zona configurada cae, si en alguna.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    label: str
    x1: int
    y1: int
    x2: int
    y2: int

    def contains(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


def parse_zones(raw: str) -> dict[str, list[Zone]]:
    """Parsea BIOTERIO_ZONES="jaula_01:comedero:0,0,100,80;jaula_01:casa:400,300,640,480".

    Formato por zona: "<node_id>:<etiqueta>:<x1>,<y1>,<x2>,<y2>", separadas por ";".
    Coordenadas en píxeles sobre el frame tal como lo entrega el nodo.
    """
    zones_by_node: dict[str, list[Zone]] = {}
    for entry in filter(None, (part.strip() for part in raw.split(";"))):
        try:
            node_id, label, coords = entry.split(":")
            x1, y1, x2, y2 = (int(v) for v in coords.split(","))
        except ValueError as exc:
            raise ValueError(
                f"Zona inválida: '{entry}' (formato esperado: node_id:etiqueta:x1,y1,x2,y2)"
            ) from exc
        zones_by_node.setdefault(node_id.strip(), []).append(Zone(label.strip(), x1, y1, x2, y2))
    return zones_by_node

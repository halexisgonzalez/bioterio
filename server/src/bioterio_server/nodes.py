"""Parseo de la lista de nodos a monitorear, desde una variable de entorno."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeConfig:
    node_id: str
    host: str


def parse_nodes(raw: str) -> list[NodeConfig]:
    """Parsea BIOTERIO_NODES="jaula_01=192.168.0.160,jaula_02=jaula_02.local"."""
    nodes = []
    for entry in filter(None, (part.strip() for part in raw.split(","))):
        node_id, _, host = entry.partition("=")
        if not node_id or not host:
            raise ValueError(f"Entrada de nodo inválida: '{entry}' (formato esperado id=host)")
        nodes.append(NodeConfig(node_id=node_id.strip(), host=host.strip()))
    if not nodes:
        raise ValueError("BIOTERIO_NODES no tiene ningún nodo válido")
    return nodes

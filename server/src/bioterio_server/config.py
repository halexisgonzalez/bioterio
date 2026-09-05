"""Carga de configuración desde variables de entorno / archivo .env.

Un solo lugar en todo el proyecto que lee os.environ — el resto del código
recibe un objeto `Settings` ya validado (evita ir a buscar env vars sueltas
por todos lados y facilita testear con settings a medida).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from bioterio_server.nodes import NodeConfig, parse_nodes
from bioterio_server.zones import Zone, parse_zones


@dataclass(frozen=True)
class Settings:
    nodes: list[NodeConfig]
    zones: dict[str, list[Zone]]  # node_id -> zonas configuradas (vacío si no hay)

    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str

    sample_interval_s: float
    batch_flush_interval_s: float
    movement_threshold_px: float
    max_disappeared_frames: int


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def load_settings(env_file: str | Path | None = ".env") -> Settings:
    if env_file and Path(env_file).exists():
        load_dotenv(env_file)

    nodes_raw = os.environ.get("BIOTERIO_NODES", "")
    if not nodes_raw:
        raise RuntimeError(
            "BIOTERIO_NODES no está definido. Copiá .env.example a .env y completá al menos un nodo."
        )

    return Settings(
        nodes=parse_nodes(nodes_raw),
        zones=parse_zones(os.environ.get("BIOTERIO_ZONES", "")),
        mysql_host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        mysql_port=_env_int("MYSQL_PORT", 3306),
        mysql_user=os.environ.get("MYSQL_USER", "bioterio"),
        mysql_password=os.environ.get("MYSQL_PASSWORD", ""),
        mysql_database=os.environ.get("MYSQL_DATABASE", "bioterio"),
        sample_interval_s=_env_float("SAMPLE_INTERVAL_S", 0.5),
        batch_flush_interval_s=_env_float("BATCH_FLUSH_INTERVAL_S", 10.0),
        movement_threshold_px=_env_float("MOVEMENT_THRESHOLD_PX", 4.0),
        max_disappeared_frames=_env_int("MAX_DISAPPEARED_FRAMES", 30),
    )

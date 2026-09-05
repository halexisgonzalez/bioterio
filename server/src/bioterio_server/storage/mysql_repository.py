"""Todo el SQL del proyecto vive acá — ningún otro módulo escribe una query.

Si el día de mañana cambia el motor de base de datos o el esquema, este es
el único archivo que hay que tocar.
"""

from __future__ import annotations

import logging

import pymysql

from bioterio_server.storage.models import PositionSample

logger = logging.getLogger(__name__)


class MySQLRepository:
    def __init__(self, host: str, port: int, user: str, password: str, database: str) -> None:
        self._connection_kwargs = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "autocommit": True,
            "connect_timeout": 5,
        }
        self._connection: pymysql.connections.Connection | None = None

    def _connect(self) -> pymysql.connections.Connection:
        if self._connection is None or not self._connection.open:
            self._connection = pymysql.connect(**self._connection_kwargs)
        return self._connection

    def ensure_node_registered(self, node_id: str) -> None:
        connection = self._connect()
        with connection.cursor() as cursor:
            cursor.execute("INSERT IGNORE INTO nodes (node_id) VALUES (%s)", (node_id,))

    def insert_samples(self, samples: list[PositionSample]) -> None:
        """Insert por lotes: se llama cada BATCH_FLUSH_INTERVAL_S segundos con
        todo lo acumulado, no en cada frame — evita saturar la base de datos
        con miles de INSERTs sueltos por segundo (ver diseño original del
        proyecto: downsampling + bulk insert)."""
        if not samples:
            return

        connection = self._connect()
        rows = [
            (
                s.node_id,
                s.track_id,
                s.sampled_at,
                s.pos_x,
                s.pos_y,
                s.frame_width,
                s.frame_height,
                s.is_moving,
                s.zone_label,
                s.temp_c,
            )
            for s in samples
        ]
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO position_samples
                    (node_id, track_id, sampled_at, pos_x, pos_y,
                     frame_width, frame_height, is_moving, zone_label, temp_c)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        logger.debug("Insertadas %d muestras en MySQL", len(rows))

    def close(self) -> None:
        if self._connection is not None and self._connection.open:
            self._connection.close()

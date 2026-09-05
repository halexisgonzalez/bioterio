-- Esquema de la base de datos del bioterio.
-- Se aplica solo automáticamente al crear el contenedor de docker-compose
-- (monta este archivo en /docker-entrypoint-initdb.d). En una instalación
-- de MySQL existente, correrlo a mano una vez: mysql < schema.sql

CREATE TABLE IF NOT EXISTS nodes (
    node_id       VARCHAR(64) PRIMARY KEY,
    label         VARCHAR(128) NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS position_samples (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    node_id       VARCHAR(64) NOT NULL,
    -- "<run_id>:<id_local>": id local del tracker + identificador de la
    -- corrida del servidor, para que dos corridas distintas nunca choquen
    -- aunque el tracker reinicie su numeración desde 0 cada vez.
    track_id      VARCHAR(80) NOT NULL,
    sampled_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    pos_x         FLOAT NOT NULL,
    pos_y         FLOAT NOT NULL,
    -- Tamaño del frame al momento de la muestra: permite normalizar/calibrar
    -- píxeles -> cm más adelante sin tener que volver a grabar nada.
    frame_width   SMALLINT NOT NULL,
    frame_height  SMALLINT NOT NULL,
    is_moving     BOOLEAN NOT NULL,
    zone_label    VARCHAR(64) NULL,
    temp_c        FLOAT NULL,
    CONSTRAINT fk_position_samples_node FOREIGN KEY (node_id) REFERENCES nodes (node_id),
    INDEX idx_node_time (node_id, sampled_at)
);

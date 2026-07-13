-- schema.sql
-- Base de datos: puestos_2026.db
-- Pipeline de Datos Electorales — Boyaca 2026 (Camara CA / Senado SE)

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Tabla de staging (raw): lo que el scraper inserta tal cual llega de
-- la API / sample_data, antes de normalizar. Permite reproducir el ETL
-- sin volver a golpear la API.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_resultados (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    municipio       TEXT NOT NULL,
    codmpio         TEXT NOT NULL,
    codpuesto       TEXT NOT NULL,
    corporacion     TEXT NOT NULL CHECK (corporacion IN ('CA', 'SE')),
    nivel           TEXT NOT NULL CHECK (nivel IN ('municipio', 'puesto')),
    payload_json    TEXT NOT NULL,           -- JSON municipal o bloque por puesto
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (municipio, codpuesto, corporacion, nivel, payload_json)
);

-- ---------------------------------------------------------------------
-- Tablas normalizadas (pobladas por db/etl.py)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS municipios (
    codmpio     TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS partidos (
    codpar          INTEGER NOT NULL,
    corporacion     TEXT NOT NULL CHECK (corporacion IN ('CA', 'SE')),
    nombre          TEXT NOT NULL,
    color           TEXT,
    codpar_homologo INTEGER,          -- codpar en la otra corporacion (CA<->SE)
    PRIMARY KEY (codpar, corporacion)
);

CREATE TABLE IF NOT EXISTS puestos (
    codpuesto   TEXT PRIMARY KEY,
    codmpio     TEXT NOT NULL,
    nombre      TEXT NOT NULL,
    mesas       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (codmpio) REFERENCES municipios (codmpio)
);

CREATE TABLE IF NOT EXISTS candidatos (
    candidato_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_normalizado TEXT NOT NULL,
    codpar          INTEGER NOT NULL,
    corporacion     TEXT NOT NULL CHECK (corporacion IN ('CA', 'SE')),
    UNIQUE (nombre_normalizado, codpar, corporacion),
    FOREIGN KEY (codpar, corporacion) REFERENCES partidos (codpar, corporacion)
);

CREATE TABLE IF NOT EXISTS votos (
    voto_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    codpuesto       TEXT NOT NULL,
    candidato_id    INTEGER NOT NULL,
    votos           INTEGER NOT NULL CHECK (votos >= 0),
    UNIQUE (codpuesto, candidato_id),
    FOREIGN KEY (codpuesto) REFERENCES puestos (codpuesto),
    FOREIGN KEY (candidato_id) REFERENCES candidatos (candidato_id)
);

-- Log de cargas del ETL: filas insertadas vs omitidas, por corrida
CREATE TABLE IF NOT EXISTS carga_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecutado_at    TEXT NOT NULL DEFAULT (datetime('now')),
    municipio       TEXT,
    filas_leidas    INTEGER NOT NULL DEFAULT 0,
    filas_insertadas INTEGER NOT NULL DEFAULT 0,
    filas_omitidas  INTEGER NOT NULL DEFAULT 0,
    detalle         TEXT
);

-- ---------------------------------------------------------------------
-- Indices (justificacion en README, seccion Bonus)
-- ---------------------------------------------------------------------
-- Acelera JOIN votos->puestos->municipios usado en casi todas las consultas 3.x
CREATE INDEX IF NOT EXISTS idx_puestos_codmpio ON puestos (codmpio);

-- Acelera el filtro por partido+corporacion usado en arrastre CA->SE (3.1)
-- y en la atribucion por partido (3.3)
CREATE INDEX IF NOT EXISTS idx_candidatos_codpar_corp ON candidatos (codpar, corporacion);

-- Acelera el JOIN votos->candidatos, el mas frecuente de las 3 consultas
CREATE INDEX IF NOT EXISTS idx_votos_candidato ON votos (candidato_id);

-- Acelera agrupar/filtrar votos por puesto (dominancia por mesa, 3.2)
CREATE INDEX IF NOT EXISTS idx_votos_codpuesto ON votos (codpuesto);

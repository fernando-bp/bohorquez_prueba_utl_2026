#!/usr/bin/env python3
"""
etl.py — Reto 2.2: Pipeline ETL

Lee raw_resultados (poblada por scraper/scraper.py) y puebla las tablas
normalizadas: municipios, partidos, puestos, candidatos, votos.
Normaliza nombres de candidatos, deduplica partidos y registra en
carga_log cuantas filas se insertaron vs se omitieron (ya existentes).

Uso:
    python db/etl.py
"""
import json
import os
import re
import sqlite3
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "puestos_2026.db")

MUNICIPIOS_CODMPIO = {
    "TUNJA": "15001",
    "PAIPA": "15516",
    "SOGAMOSO": "15759",
    "DUITAMA": "15238",
}

# codpar_CA -> (codpar_SE, nombre, color). Fuente: enunciado de la prueba
# (tabla "Colores de partido obligatorios") + codigos DIVIPOLA-partidos
# tipicos de tarjetones CA/SE.
PARTIDOS_CA = {
    5:  (57, "ALIANZA VERDE", "#007C34"),
    87: (92, "PACTO HISTORICO", "#7B2D8B"),
    10: (10, "CENTRO DEMOCRATICO", "#1E477D"),
    2:  (2,  "PARTIDO CONSERVADOR", "#E07B00"),
    1:  (1,  "PARTIDO LIBERAL", "#D8232A"),
    4:  (4,  "CAMBIO RADICAL", "#8C8C8C"),
    # Coaliciones/listas de Cámara Boyacá 2026, verificadas contra el
    # catálogo/inscripción oficial de Registraduría.
    15:  (17, "DIGNIDAD Y COMPROMISO", "#6B4C9A"),
    120: (9,  "PARTIDO DE LA U - PARTIDO MIRA", "#00A3A3"),
    121: (2,  "PARTIDO CONSERVADOR - MOVIMIENTO SALVACION NACIONAL", "#E07B00"),
    122: (3,  "CR - NUEVO LIBERALISMO", "#E3051C"),
    137: (170, "ALMA - OXIGENO", "#00AEEF"),
}
# Códigos de Senado confirmados. No se infieren desde coaliciones de Cámara:
# una coalición puede reutilizar el código de uno de sus integrantes.
PARTIDOS_SE = {
    57: (5, "ALIANZA VERDE", "#007C34"),
    92: (87, "PACTO HISTORICO", "#7B2D8B"),
    10: (10, "CENTRO DEMOCRATICO", "#1E477D"),
    2:  (2, "PARTIDO CONSERVADOR", "#E07B00"),
    1:  (1, "PARTIDO LIBERAL", "#D8232A"),
    3:  (4, "CAMBIO RADICAL", "#E3051C"),
    17: (15, "DIGNIDAD Y COMPROMISO", "#6B4C9A"),
}


def normalizar_nombre(nombre):
    """Mayusculas, sin tildes, espacios simples — evita duplicados por
    variaciones de tipeo/acentos entre boletines."""
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes.strip().upper())


def get_or_create_municipio(conn, municipio):
    codmpio = MUNICIPIOS_CODMPIO[municipio]
    conn.execute(
        "INSERT OR IGNORE INTO municipios (codmpio, nombre) VALUES (?, ?)",
        (codmpio, municipio),
    )
    return codmpio


def get_or_create_partido(conn, codpar, corporacion):
    codpar = int(codpar)
    if corporacion == "CA" and codpar in PARTIDOS_CA:
        codpar_se, nombre, color = PARTIDOS_CA[codpar]
        homologo = codpar_se
    elif corporacion == "SE" and codpar in PARTIDOS_SE:
        codpar_ca, nombre, color = PARTIDOS_SE[codpar]
        homologo = codpar_ca
    else:
        nombre, color, homologo = f"PARTIDO {codpar}", None, None

    conn.execute(
        """INSERT INTO partidos (codpar, corporacion, nombre, color, codpar_homologo)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(codpar, corporacion) DO UPDATE SET
             nombre = excluded.nombre,
             color = COALESCE(excluded.color, partidos.color),
             codpar_homologo = COALESCE(excluded.codpar_homologo, partidos.codpar_homologo)""",
        (codpar, corporacion, nombre, color, homologo),
    )


def get_or_create_candidato(conn, nombre_normalizado, codpar, corporacion):
    cur = conn.execute(
        """SELECT candidato_id FROM candidatos
           WHERE nombre_normalizado = ? AND codpar = ? AND corporacion = ?""",
        (nombre_normalizado, codpar, corporacion),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    cur = conn.execute(
        """INSERT INTO candidatos (nombre_normalizado, codpar, corporacion)
           VALUES (?, ?, ?)""",
        (nombre_normalizado, codpar, corporacion),
    )
    return cur.lastrowid, True


def run_etl():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    for municipio in MUNICIPIOS_CODMPIO:
        codmpio = get_or_create_municipio(conn, municipio)

        raw_rows = conn.execute(
            """SELECT codpuesto, corporacion, payload_json
               FROM raw_resultados
               WHERE municipio = ? AND nivel = 'puesto'""",
            (municipio,),
        ).fetchall()

        # puestos + mesas: reconstruimos desde sample_data/API original no es
        # necesario aqui porque el nombre/mesas del puesto no viaja en cada
        # bloque de partido; se infieren al primer avistamiento del codpuesto.
        puestos_vistos = set()
        filas_leidas = 0
        filas_insertadas = 0
        filas_omitidas = 0

        for codpuesto, corporacion, payload_json in raw_rows:
            filas_leidas += 1
            bloque = json.loads(payload_json)
            if codpuesto not in puestos_vistos:
                conn.execute(
                    """INSERT OR IGNORE INTO puestos (codpuesto, codmpio, nombre, mesas)
                       VALUES (?, ?, ?, ?)""",
                    (
                        codpuesto,
                        codmpio,
                        bloque.get("nombre_puesto") or f"PUESTO {codpuesto}",
                        int(bloque.get("mesas", 0)),
                    ),
                )
                puestos_vistos.add(codpuesto)
            # Si el puesto ya existía por una corrida anterior, completa los
            # metadatos reales que vienen del scraper oficial.
            conn.execute(
                """UPDATE puestos
                   SET nombre = ?, mesas = MAX(mesas, ?)
                   WHERE codpuesto = ?""",
                (
                    bloque.get("nombre_puesto") or f"PUESTO {codpuesto}",
                    int(bloque.get("mesas", 0)),
                    codpuesto,
                ),
            )

            codpar = bloque["codpar"]
            get_or_create_partido(conn, codpar, corporacion)

            for cand in bloque.get("candidatos", []):
                nombre_norm = normalizar_nombre(cand["nombre"])
                candidato_id, es_nuevo_candidato = get_or_create_candidato(
                    conn, nombre_norm, codpar, corporacion
                )
                existente = conn.execute(
                    "SELECT votos FROM votos WHERE codpuesto = ? AND candidato_id = ?",
                    (codpuesto, candidato_id),
                ).fetchone()
                conn.execute(
                    """INSERT INTO votos (codpuesto, candidato_id, votos)
                       VALUES (?, ?, ?)
                       ON CONFLICT(codpuesto, candidato_id) DO UPDATE SET votos = excluded.votos""",
                    (codpuesto, candidato_id, cand["votos"]),
                )
                if existente is None:
                    filas_insertadas += 1
                else:
                    filas_omitidas += 1

        conn.execute(
            """INSERT INTO carga_log (municipio, filas_leidas, filas_insertadas, filas_omitidas, detalle)
               VALUES (?, ?, ?, ?, ?)""",
            (municipio, filas_leidas, filas_insertadas, filas_omitidas,
             f"{len(puestos_vistos)} puestos procesados"),
        )
        conn.commit()
        print(f"[etl] {municipio}: {filas_leidas} bloques leidos, "
              f"{filas_insertadas} votos insertados, {filas_omitidas} omitidos, "
              f"{len(puestos_vistos)} puestos")

    conn.close()


if __name__ == "__main__":
    run_etl()

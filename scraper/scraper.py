#!/usr/bin/env python3
"""Reto 1: extracción de resultados oficiales de Congreso 2026.

Descarga exclusivamente los JSON publicados por Registraduría. Primero lee el
nomenclador oficial para descubrir los puestos de cada municipio y después
consulta Cámara (CA) y Senado (SE) por puesto.

Uso:
    python scraper/scraper.py
    python scraper/scraper.py --municipios TUNJA PAIPA
    python scraper/scraper.py --preflight
"""
import argparse
import json
import os
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(REPO_DIR, "db", "puestos_2026.db")
SCHEMA_PATH = os.path.join(REPO_DIR, "db", "schema.sql")

BASE_URL = "https://resultadospreccongreso2026.registraduria.gov.co"
NOMENCLATOR_URL = f"{BASE_URL}/json/nomenclator.json"
ACT_URL = f"{BASE_URL}/json/ACT/{{corporacion}}/{{codpuesto}}.json"

# Códigos de ámbito del nomenclador oficial 2026, no códigos DIVIPOLA.
MUNICIPIOS = {
    "TUNJA": {"codmpio": "15001", "scope": "0700001"},
    "PAIPA": {"codmpio": "15516", "scope": "0700181"},
    "SOGAMOSO": {"codmpio": "15759", "scope": "0700277"},
    "DUITAMA": {"codmpio": "15238", "scope": "0700079"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UTL-Boyaca-Scraper/1.0)",
    "Accept": "application/json",
}
MAX_RETRIES = 4
BACKOFF_BASE = 1.5
REQUEST_PAUSE_MIN = 0.5
REQUEST_PAUSE_MAX = 1.0
NIVEL_PUESTO = 6
CAMARA_POR_CORPORACION = {"SE": "0", "CA": "1"}


def log(msg):
    print(f"[scraper] {msg}", flush=True)


def ensure_schema(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    columnas = {row[1] for row in conn.execute("PRAGMA table_info(raw_resultados)")}
    if "nivel" not in columnas:
        conn.execute(
            "ALTER TABLE raw_resultados ADD COLUMN nivel TEXT NOT NULL DEFAULT 'puesto' "
            "CHECK (nivel IN ('municipio', 'puesto'))"
        )
    if "raw_key" not in columnas:
        conn.execute("ALTER TABLE raw_resultados ADD COLUMN raw_key TEXT")
    for row_id, municipio, codpuesto, corporacion, nivel, payload in conn.execute(
        "SELECT id, municipio, codpuesto, corporacion, nivel, payload_json FROM raw_resultados "
        "WHERE raw_key IS NULL"
    ):
        bloque = json.loads(payload)
        clave = raw_key(municipio, codpuesto, corporacion, nivel, bloque.get("codpar"))
        conn.execute("UPDATE raw_resultados SET raw_key = ? WHERE id = ?", (clave, row_id))
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_resultados_identidad "
        "ON raw_resultados (raw_key)"
    )
    conn.commit()


def raw_key(municipio, codpuesto, corporacion, nivel, codpar=None):
    """Clave estable: un agregado municipal o un bloque de partido por puesto."""
    sufijo = "MUNICIPIO" if nivel == "municipio" else f"PARTIDO:{codpar}"
    return f"{municipio}|{codpuesto}|{corporacion}|{nivel}|{sufijo}"


def fetch_json(url):
    """GET JSON oficial con retry, backoff exponencial y jitter."""
    for intento in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    # Evita ráfagas contra un sitio público.
                    time.sleep(random.uniform(REQUEST_PAUSE_MIN, REQUEST_PAUSE_MAX))
                    return data
                log(f"HTTP {response.status} en intento {intento}/{MAX_RETRIES}: {url}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            log(f"Error en intento {intento}/{MAX_RETRIES}: {exc}")
        if intento < MAX_RETRIES:
            time.sleep(BACKOFF_BASE ** intento + random.uniform(0, 0.5))
    raise RuntimeError(f"No fue posible obtener datos oficiales: {url}")


def insertar_resultado_municipal(conn, municipio, corporacion):
    """Guarda la respuesta oficial agregada de un municipio."""
    codigo = MUNICIPIOS[municipio]["scope"]
    url = ACT_URL.format(corporacion=corporacion, codpuesto=codigo)
    response = fetch_json(url)
    payload = json.dumps(response, ensure_ascii=False, sort_keys=True)
    clave = raw_key(municipio, codigo, corporacion, "municipio")
    existente = conn.execute(
        """SELECT 1 FROM raw_resultados
           WHERE raw_key = ?""",
        (clave,),
    ).fetchone()
    conn.execute(
        """INSERT INTO raw_resultados
           (municipio, codmpio, codpuesto, corporacion, nivel, raw_key, payload_json)
           VALUES (?, ?, ?, ?, 'municipio', ?, ?)
           ON CONFLICT(raw_key) DO UPDATE SET
               codmpio = excluded.codmpio,
               payload_json = excluded.payload_json,
               fetched_at = datetime('now')""",
        (municipio, MUNICIPIOS[municipio]["codmpio"], codigo, corporacion, clave, payload),
    )
    estado = "actualizado" if existente else "insertado"
    log(f"{municipio} {corporacion} municipio ({codigo}): {estado}")
    return existente is None


def obtener_puestos_por_municipio():
    """Devuelve los puestos reales de cada municipio desde nomenclator.json."""
    nomenclator = fetch_json(NOMENCLATOR_URL)
    senate_tree = next(item["ambitos"] for item in nomenclator["amb"] if item["elec"] == 1)
    by_id = {item["i"]: item for item in senate_tree}
    by_code = {item["c"]: item for item in senate_tree}

    def hijos(node):
        return [by_id[item_id] for branch in node.get("h", []) for item_id in branch.get("p", [])]

    def puestos_descendientes(node):
        encontrados, pendientes = [], [node]
        while pendientes:
            actual = pendientes.pop()
            if actual["l"] == NIVEL_PUESTO:
                encontrados.append(actual)
            elif actual["l"] < NIVEL_PUESTO:
                pendientes.extend(hijos(actual))
        return sorted(encontrados, key=lambda item: item["c"])

    resultado = {}
    for municipio, config in MUNICIPIOS.items():
        scope = config["scope"]
        if scope not in by_code:
            raise RuntimeError(f"El municipio {municipio} no existe en el nomenclador oficial")
        resultado[municipio] = puestos_descendientes(by_code[scope])
    return resultado


def nombre_candidato(candidato):
    partes = [
        candidato.get("nomcan", ""), candidato.get("nomcan2", ""),
        candidato.get("apecan", ""), candidato.get("apecan2", ""),
    ]
    return " ".join(parte.strip() for parte in partes if parte and parte.strip())


def bloques_oficiales(corporacion, puesto):
    """Convierte la respuesta oficial de un puesto al staging del proyecto."""
    codpuesto = puesto["c"]
    url = ACT_URL.format(corporacion=corporacion, codpuesto=codpuesto)
    response = fetch_json(url)
    camara = next(
        (item for item in response.get("camaras", []) if item.get("cam") == CAMARA_POR_CORPORACION[corporacion]),
        None,
    )
    if camara is None:
        raise RuntimeError(f"No hay cámara {CAMARA_POR_CORPORACION[corporacion]} en {url}")

    mesas = int(response.get("totales", {}).get("act", {}).get("mesesc", 0))
    bloques = []
    for partido in camara.get("partotabla", []):
        act = partido.get("act", {})
        candidatos = []
        for candidato in act.get("cantotabla", []):
            nombre = nombre_candidato(candidato)
            if not nombre:
                continue
            candidatos.append({
                "nombre": nombre,
                "votos": int(candidato.get("vot", 0)),
                "codcan": candidato.get("codcan"),
            })
        bloques.append({
            "codpar": int(act["codpar"]),
            "votos_partido": int(act.get("vot", 0)),
            "candidatos": candidatos,
            "nombre_puesto": puesto["n"],
            "mesas": mesas,
            "fuente_url": url,
            "actualizado_en": response.get("mdhm"),
        })
    return bloques, mesas


def insertar_raw(conn, municipio, puestos):
    cur = conn.cursor()
    insertadas = omitidas = bloques_leidos = mesas = 0
    for puesto in puestos:
        for corporacion in ("CA", "SE"):
            bloques, mesas_puesto = bloques_oficiales(corporacion, puesto)
            mesas = max(mesas, mesas_puesto)
            for bloque in bloques:
                bloques_leidos += 1
                payload = json.dumps(bloque, ensure_ascii=False, sort_keys=True)
                clave = raw_key(municipio, puesto["c"], corporacion, "puesto", bloque["codpar"])
                existente = cur.execute(
                    """SELECT 1 FROM raw_resultados
                       WHERE raw_key = ?""",
                    (clave,),
                ).fetchone()
                cur.execute(
                """INSERT INTO raw_resultados
                   (municipio, codmpio, codpuesto, corporacion, nivel, raw_key, payload_json)
                   VALUES (?, ?, ?, ?, 'puesto', ?, ?)
                   ON CONFLICT(raw_key) DO UPDATE SET
                       codmpio = excluded.codmpio,
                       payload_json = excluded.payload_json,
                       fetched_at = datetime('now')""",
                    (municipio, MUNICIPIOS[municipio]["codmpio"], puesto["c"], corporacion, clave, payload),
                )
                if existente:
                    omitidas += 1
                else:
                    insertadas += 1
    conn.commit()
    return insertadas, omitidas, bloques_leidos


def main():
    parser = argparse.ArgumentParser(description="Scraper oficial de Congreso 2026 para Boyacá")
    parser.add_argument("--municipios", nargs="+", default=list(MUNICIPIOS),
                        help="Municipios a extraer (por defecto: los cuatro del reto)")
    parser.add_argument("--preflight", action="store_true",
                        help="Consulta y cuenta datos oficiales, sin escribir en SQLite")
    parser.add_argument("--solo-municipios", action="store_true",
                        help="Guarda solo los agregados oficiales municipales CA y SE")
    args = parser.parse_args()

    municipios = [municipio.upper() for municipio in args.municipios]
    invalidos = [municipio for municipio in municipios if municipio not in MUNICIPIOS]
    if invalidos:
        parser.error(f"Municipios no reconocidos: {', '.join(invalidos)}")

    log(f"Descargando nomenclador oficial: {NOMENCLATOR_URL}")
    puestos_por_municipio = obtener_puestos_por_municipio()

    if args.preflight:
        for municipio in municipios:
            codigo = MUNICIPIOS[municipio]["scope"]
            for corporacion in ("CA", "SE"):
                fetch_json(ACT_URL.format(corporacion=corporacion, codpuesto=codigo))
                log(f"{municipio} {corporacion} municipio ({codigo}): consultado")
        total_puestos = total_bloques = 0
        for municipio in municipios:
            puestos = puestos_por_municipio[municipio]
            bloques = 0
            for puesto in puestos:
                for corporacion in ("CA", "SE"):
                    resultado, _ = bloques_oficiales(corporacion, puesto)
                    bloques += len(resultado)
            total_puestos += len(puestos)
            total_bloques += bloques
            log(f"{municipio}: {len(puestos)} puestos, {bloques} bloques oficiales CA+SE")
        log(f"TOTAL preflight: {total_puestos} puestos, {total_bloques} bloques oficiales")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        for municipio in municipios:
            for corporacion in ("CA", "SE"):
                insertar_resultado_municipal(conn, municipio, corporacion)
            if args.solo_municipios:
                conn.commit()
                continue
            ins, omit, leidos = insertar_raw(conn, municipio, puestos_por_municipio[municipio])
            log(f"{municipio}: {leidos} bloques oficiales leídos, {ins} insertados, {omit} omitidos")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

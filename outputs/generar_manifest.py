#!/usr/bin/env python3
"""
generar_manifest.py — valida el pipeline completo y genera
outputs/evaluation_manifest.json

Ejecuta:
  - conteo de municipios/filas en la BD (Reto 1.3 / 2.3)
  - las 3 consultas SQL de sql/ y confirma que corren sin error (Reto 3)
  - captura las metricas impresas por viz/scatter.py (r, pendiente, n)

Imprime "4/4 municipios" y "SQL OK" cuando todo esta correcto (usado por
el checklist de entrega).
"""
import json
import os
import re
import sqlite3
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(REPO_DIR, "db", "puestos_2026.db")
OUT_PATH = os.path.join(BASE_DIR, "evaluation_manifest.json")

# ---------------------------------------------------------------------
# EDITAR ANTES DE ENTREGAR
# ---------------------------------------------------------------------
META = {
    "nombre": "FERNANDO BOHORQUEZ PARRA",
    "email": "fernando.bohorquez@uptc.edu.co",
    "url_repo": "https://github.com/fernando-bp/bohorquez_prueba_utl_2026",
}
# ---------------------------------------------------------------------

MUNICIPIOS_ESPERADOS = {"TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"}
CORPORACIONES = {"CA", "SE"}
MESAS_ESPERADAS = {"TUNJA": 424, "PAIPA": 95, "SOGAMOSO": 301, "DUITAMA": 287}
PUESTOS_ESPERADOS = {"TUNJA": 26, "PAIPA": 7, "SOGAMOSO": 18, "DUITAMA": 22}


def validar_municipios(conn):
    filas = conn.execute("SELECT DISTINCT nombre FROM municipios").fetchall()
    presentes = {r[0] for r in filas}
    ok = presentes == MUNICIPIOS_ESPERADOS
    print(f"{len(presentes)}/4 municipios" if not ok else "4/4 municipios")
    return {
        "municipios_presentes": sorted(presentes),
        "ok": ok,
    }


def validar_conteos(conn):
    conteos = {}
    for t in ["municipios", "puestos", "partidos", "candidatos", "votos"]:
        conteos[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return conteos


def validar_lideres_senado(conn):
    """Verifica que cada municipio tenga un partido líder calculado desde SE."""
    filas = conn.execute(
        """WITH votos_partido AS (
               SELECT m.nombre AS municipio, c.codpar, SUM(v.votos) AS votos,
                      ROW_NUMBER() OVER (
                          PARTITION BY m.nombre ORDER BY SUM(v.votos) DESC, c.codpar
                      ) AS posicion
               FROM votos v
               JOIN puestos p ON p.codpuesto = v.codpuesto
               JOIN municipios m ON m.codmpio = p.codmpio
               JOIN candidatos c ON c.candidato_id = v.candidato_id
               WHERE c.corporacion = 'SE'
               GROUP BY m.nombre, c.codpar
           )
           SELECT municipio, codpar, votos FROM votos_partido
           WHERE posicion = 1 ORDER BY municipio"""
    ).fetchall()
    lideres = [{"municipio": m, "codpar": p, "votos": v} for m, p, v in filas]
    ok = {fila["municipio"] for fila in lideres} == MUNICIPIOS_ESPERADOS
    print(f"Reto 2: {len(lideres)}/4 partidos líderes SE verificados")
    return {"lideres_se": lideres, "ok": ok}


def validar_extraccion(conn):
    """Comprueba respuestas, mesas oficiales y ámbitos de puesto extraídos."""
    filas = conn.execute(
        """SELECT municipio, corporacion, payload_json
           FROM raw_resultados WHERE nivel = 'municipio'"""
    ).fetchall()
    esperadas = {(m, c) for m in MUNICIPIOS_ESPERADOS for c in CORPORACIONES}
    encontradas = {(m, c) for m, c, _ in filas}
    mesas = {}
    for municipio, corporacion, payload in filas:
        data = json.loads(payload)
        mesas[f"{municipio}_{corporacion}"] = int(
            data.get("totales", {}).get("act", {}).get("mesesc", 0)
        )
    mesas_por_municipio = {
        municipio: conn.execute(
            """SELECT COALESCE(SUM(mesas), 0) FROM puestos p
               JOIN municipios m ON m.codmpio = p.codmpio WHERE m.nombre = ?""",
            (municipio,),
        ).fetchone()[0]
        for municipio in MUNICIPIOS_ESPERADOS
    }
    puestos_por_municipio = {
        municipio: conn.execute(
            """SELECT COUNT(*) FROM puestos p JOIN municipios m ON m.codmpio = p.codmpio
               WHERE m.nombre = ?""",
            (municipio,),
        ).fetchone()[0]
        for municipio in MUNICIPIOS_ESPERADOS
    }
    bloques_puesto = conn.execute(
        "SELECT COUNT(*) FROM raw_resultados WHERE nivel = 'puesto'"
    ).fetchone()[0]
    mesas_coinciden = all(
        mesas.get(f"{municipio}_CA") == esperadas_mesas
        and mesas.get(f"{municipio}_SE") == esperadas_mesas
        and mesas_por_municipio[municipio] == esperadas_mesas
        for municipio, esperadas_mesas in MESAS_ESPERADAS.items()
    )
    puestos_coinciden = puestos_por_municipio == PUESTOS_ESPERADOS
    ok = (encontradas == esperadas and mesas_coinciden and puestos_coinciden
          and bloques_puesto > 0)
    print(f"Reto 1: {len(encontradas)}/8 respuestas municipales; "
          f"{sum(mesas_por_municipio.values())} mesas únicas; "
          f"{bloques_puesto} bloques por puesto")
    return {
        "respuestas_municipales": len(encontradas),
        "mesas_api": mesas,
        "mesas_por_municipio": mesas_por_municipio,
        "puestos_por_municipio": puestos_por_municipio,
        "bloques_puesto": bloques_puesto,
        "ok": ok,
    }


def ejecutar_sql(conn):
    resultados = {}
    todo_ok = True
    for nombre_archivo in ["tarea_3_1.sql", "tarea_3_2.sql", "tarea_3_3.sql"]:
        path = os.path.join(REPO_DIR, "sql", nombre_archivo)
        sql = open(path, encoding="utf-8").read()
        try:
            filas = conn.execute(sql).fetchall()
            resultados[nombre_archivo] = {"status": "OK", "n_filas": len(filas)}
        except Exception as e:
            resultados[nombre_archivo] = {"status": "ERROR", "error": str(e)}
            todo_ok = False
    print("SQL OK" if todo_ok else "SQL ERROR — revisar archivos .sql")
    return resultados, todo_ok


def ejecutar_scatter():
    """Corre viz/scatter.py y parsea la linea 'r=... | pendiente=... | n_mesas=...'"""
    path = os.path.join(REPO_DIR, "viz", "scatter.py")
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True,
                               cwd=os.path.join(REPO_DIR, "viz"), timeout=60)
        m = re.search(r"r=([\-0-9.]+)\s*\|\s*pendiente=([\-0-9.]+)\s*\|\s*n_mesas=(\d+)", proc.stdout)
        if m:
            return {"r": float(m.group(1)), "pendiente": float(m.group(2)), "n_mesas": int(m.group(3))}
        return {"error": "no se pudo parsear salida de scatter.py", "stdout": proc.stdout, "stderr": proc.stderr}
    except Exception as e:
        return {"error": str(e)}


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: no existe db/puestos_2026.db. Corra primero scraper.py y db/etl.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    reto1 = validar_municipios(conn)
    reto1_extraccion = validar_extraccion(conn)
    reto2 = validar_conteos(conn)
    reto2_lideres = validar_lideres_senado(conn)
    reto3, sql_ok = ejecutar_sql(conn)
    reto5 = ejecutar_scatter()

    manifest = {
        "meta": META,
        "reto1_extraccion": reto1_extraccion,
        "reto2_base_datos": reto2,
        "reto2_lideres_senado": reto2_lideres,
        "reto3_sql": reto3,
        "reto5_scatter_metrics": reto5,
        "resumen": {
            "municipios_ok": reto1["ok"],
            "extraccion_ok": reto1_extraccion["ok"],
            "lideres_se_ok": reto2_lideres["ok"],
            "sql_ok": sql_ok,
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[manifest] guardado en {OUT_PATH}")


if __name__ == "__main__":
    main()

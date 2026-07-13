#!/usr/bin/env python3
"""
export_data.py — genera dashboard/data.json a partir de puestos_2026.db
para que index.html sea autocontenido y no necesite servidor/backend.
"""
import json
import os
import sqlite3
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "db", "puestos_2026.db")
OUT_PATH = os.path.join(BASE_DIR, "data.json")

COLORES = {
    5: "#007C34", 57: "#007C34",       # Alianza Verde
    87: "#7B2D8B", 92: "#7B2D8B",      # Pacto Historico
    10: "#1E477D",                     # Centro Democratico
    2: "#E07B00",                      # Conservador
    1: "#D8232A",                      # Liberal
    4: "#8C8C8C",                      # Cambio Radical
}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    municipios = [r["nombre"] for r in conn.execute("SELECT nombre FROM municipios ORDER BY nombre")]

    # Comparativo: votos CA totales por municipio
    comparativo = {}
    for r in conn.execute("""
        SELECT m.nombre AS municipio, SUM(v.votos) AS total_ca
        FROM votos v
        JOIN candidatos c ON c.candidato_id = v.candidato_id
        JOIN puestos p ON p.codpuesto = v.codpuesto
        JOIN municipios m ON m.codmpio = p.codmpio
        WHERE c.corporacion = 'CA'
        GROUP BY m.nombre
    """):
        comparativo[r["municipio"]] = r["total_ca"]

    # Por municipio: top 10 candidatos CA + partido lider SE
    por_municipio = {}
    for muni in municipios:
        top_ca = [
            {"candidato": r["nombre_normalizado"], "partido": r["partido"],
             "color": r["color"] or COLORES.get(r["codpar"], "#666"), "votos": r["votos"]}
            for r in conn.execute("""
                SELECT c.nombre_normalizado, pa.nombre AS partido, pa.color, c.codpar,
                       SUM(v.votos) AS votos
                FROM votos v
                JOIN candidatos c ON c.candidato_id = v.candidato_id
                JOIN partidos pa ON pa.codpar = c.codpar AND pa.corporacion = c.corporacion
                JOIN puestos p ON p.codpuesto = v.codpuesto
                JOIN municipios m ON m.codmpio = p.codmpio
                WHERE c.corporacion = 'CA'
                  AND c.nombre_normalizado <> 'SOLO POR LA LISTA'
                  AND m.nombre = ?
                GROUP BY c.candidato_id
                ORDER BY votos DESC LIMIT 10
            """, (muni,))
        ]
        lider_se_row = conn.execute("""
            SELECT pa.nombre AS partido, SUM(v.votos) AS votos
            FROM votos v
            JOIN candidatos c ON c.candidato_id = v.candidato_id
            JOIN partidos pa ON pa.codpar = c.codpar AND pa.corporacion = c.corporacion
            JOIN puestos p ON p.codpuesto = v.codpuesto
            JOIN municipios m ON m.codmpio = p.codmpio
            WHERE c.corporacion = 'SE' AND m.nombre = ?
            GROUP BY pa.nombre
            ORDER BY votos DESC LIMIT 1
        """, (muni,)).fetchone()
        por_municipio[muni] = {
            "top_ca": top_ca,
            "lider_se": {"partido": lider_se_row["partido"], "votos": lider_se_row["votos"]} if lider_se_row else None,
        }

    # Arrastre: ratio Verde SE/CA por puesto y municipio
    arrastre = {muni: [] for muni in municipios}
    sql_31 = open(os.path.join(os.path.dirname(BASE_DIR), "sql", "tarea_3_1.sql")).read()
    for r in conn.execute(sql_31):
        arrastre.setdefault(r["municipio"], []).append({
            "puesto": r["nombre_puesto"],
            "ratio": r["ratio_arrastre"],
        })

    data = {
        "municipios": municipios,
        "comparativo_ca": comparativo,
        "por_municipio": por_municipio,
        "arrastre_verde": arrastre,
        "colores_partido": {
            "ALIANZA VERDE": "#007C34",
            "PACTO HISTORICO": "#7B2D8B",
            "CENTRO DEMOCRATICO": "#1E477D",
            "PARTIDO CONSERVADOR": "#E07B00",
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    index_path = os.path.join(BASE_DIR, "index.html")
    html = open(index_path, encoding="utf-8").read()
    bloque = (
        "<!-- DATA_EMBEDDED_START -->\n<script>\nconst EMBEDDED_DATA = "
        + json.dumps(data, ensure_ascii=False)
        + ";\n</script>\n<!-- DATA_EMBEDDED_END -->"
    )
    html, reemplazos = re.subn(
        r"<!-- DATA_EMBEDDED_START -->.*?<!-- DATA_EMBEDDED_END -->",
        bloque, html, flags=re.DOTALL,
    )
    if reemplazos != 1:
        raise RuntimeError("No se encontro el marcador DATA_EMBEDDED en index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[export_data] data.json e index.html actualizados con {len(municipios)} municipios")


if __name__ == "__main__":
    main()

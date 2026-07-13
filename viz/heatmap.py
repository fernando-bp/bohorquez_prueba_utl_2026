#!/usr/bin/env python3
"""
heatmap.py — Reto 5.1
Genera viz/heatmap_municipios.png:
  filas    = top 8 candidatos CA (por votos consolidados en los 4 municipios)
  columnas = los 4 municipios
  valores  = % del total de votos CA de ese municipio que obtuvo el candidato
  con anotaciones numericas en cada celda.
"""
import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "db", "puestos_2026.db")
OUT_PATH = os.path.join(BASE_DIR, "heatmap_municipios.png")


def main():
    conn = sqlite3.connect(DB_PATH)

    top8 = conn.execute("""
        SELECT c.candidato_id, c.nombre_normalizado
        FROM votos v
        JOIN candidatos c ON c.candidato_id = v.candidato_id
        WHERE c.corporacion = 'CA'
          AND c.nombre_normalizado <> 'SOLO POR LA LISTA'
        GROUP BY c.candidato_id
        ORDER BY SUM(v.votos) DESC
        LIMIT 8
    """).fetchall()

    municipios = [r[0] for r in conn.execute("SELECT nombre FROM municipios ORDER BY nombre")]

    total_ca_municipio = dict(conn.execute("""
        SELECT m.nombre, SUM(v.votos)
        FROM votos v
        JOIN candidatos c ON c.candidato_id = v.candidato_id
        JOIN puestos p ON p.codpuesto = v.codpuesto
        JOIN municipios m ON m.codmpio = p.codmpio
        WHERE c.corporacion = 'CA'
        GROUP BY m.nombre
    """))

    matriz = np.zeros((len(top8), len(municipios)))
    for i, (candidato_id, nombre_candidato) in enumerate(top8):
        for j, muni in enumerate(municipios):
            row = conn.execute("""
                SELECT SUM(v.votos)
                FROM votos v
                JOIN candidatos c ON c.candidato_id = v.candidato_id
                JOIN puestos p ON p.codpuesto = v.codpuesto
                JOIN municipios m ON m.codmpio = p.codmpio
                WHERE c.corporacion = 'CA' AND c.candidato_id = ? AND m.nombre = ?
            """, (candidato_id, muni)).fetchone()
            votos_cand = row[0] or 0
            matriz[i, j] = 100.0 * votos_cand / total_ca_municipio[muni]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matriz, cmap="YlGnBu", aspect="auto")

    ax.set_xticks(range(len(municipios)))
    ax.set_xticklabels(municipios)
    ax.set_yticks(range(len(top8)))
    ax.set_yticklabels([nombre for _, nombre in top8], fontsize=8)

    for i in range(len(top8)):
        for j in range(len(municipios)):
            valor = matriz[i, j]
            color = "white" if valor > matriz.max() * 0.6 else "black"
            ax.text(j, i, f"{valor:.1f}%", ha="center", va="center", color=color, fontsize=8)

    ax.set_title("Top 8 candidatos CA — % del total de votos por municipio")
    fig.colorbar(im, ax=ax, label="% del total CA del municipio")
    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)
    print(f"[heatmap] guardado en {OUT_PATH}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scatter.py — Reto 5.2
Genera viz/scatter_ca_se.png: cada punto = un puesto (proxy de mesa
consolidada), votos totales CA (x) vs votos totales SE (y), color por
municipio, con linea de regresion OLS y r de Pearson anotado.

Imprime: r=X.XXX | pendiente=X.XXX | n_mesas=NNN  (el manifest lo captura)
"""
import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "db", "puestos_2026.db")
OUT_PATH = os.path.join(BASE_DIR, "scatter_ca_se.png")

COLORES_MUNICIPIO = {
    "TUNJA": "#1E477D",
    "PAIPA": "#007C34",
    "SOGAMOSO": "#E07B00",
    "DUITAMA": "#7B2D8B",
}


def main():
    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute("""
        SELECT m.nombre AS municipio, p.codpuesto,
               SUM(CASE WHEN c.corporacion = 'CA' THEN v.votos ELSE 0 END) AS votos_ca,
               SUM(CASE WHEN c.corporacion = 'SE' THEN v.votos ELSE 0 END) AS votos_se
        FROM votos v
        JOIN candidatos c ON c.candidato_id = v.candidato_id
        JOIN puestos p ON p.codpuesto = v.codpuesto
        JOIN municipios m ON m.codmpio = p.codmpio
        GROUP BY p.codpuesto
    """).fetchall()

    municipios = [r[0] for r in rows]
    x = np.array([r[2] for r in rows], dtype=float)
    y = np.array([r[3] for r in rows], dtype=float)

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    n_mesas = len(rows)

    fig, ax = plt.subplots(figsize=(8, 6))
    for muni in COLORES_MUNICIPIO:
        mask = np.array([m == muni for m in municipios])
        ax.scatter(x[mask], y[mask], color=COLORES_MUNICIPIO[muni], label=muni, alpha=0.8, edgecolor="white", s=60)

    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color="black", linestyle="--", linewidth=1.5,
            label=f"OLS (r={r_value:.3f})")

    ax.set_xlabel("Votos totales Cámara (CA) por puesto")
    ax.set_ylabel("Votos totales Senado (SE) por puesto")
    ax.set_title("Relación votos Cámara vs Senado por puesto — Boyacá 2026")
    ax.legend(fontsize=8)
    ax.annotate(f"r = {r_value:.3f}\npendiente = {slope:.3f}\nn = {n_mesas}",
                xy=(0.03, 0.95), xycoords="axes fraction", va="top",
                fontsize=9, bbox=dict(boxstyle="round", fc="white", ec="gray"))

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)

    print(f"r={r_value:.3f} | pendiente={slope:.3f} | n_mesas={n_mesas}")
    print(f"[scatter] guardado en {OUT_PATH}")


if __name__ == "__main__":
    main()

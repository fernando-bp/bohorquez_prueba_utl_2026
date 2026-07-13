"""
generar_sample_data.py
-----------------------
Genera datos de muestra (sample_data/) que IMITAN la forma esperada de la
respuesta JSON de la API de la Registraduria para Camara (CA) y Senado (SE).

Se usa como respaldo cuando la API real no responde o para desarrollar/probar
el parser sin depender de la red. El formato de campos (nomenclator, codpuesto,
codpar, candidatos, votos) sigue el patron tipico de boletines PREC de la
Registraduria: lista de puestos -> lista de partidos -> lista de candidatos.

IMPORTANTE (leer README seccion "API"): estos datos son SINTETICOS. Antes de
la entrega final se debe verificar con el navegador (F12 -> Network) el
esquema real de resultadospreccongreso2026.registraduria.gov.co y ajustar
scraper/scraper.py si los nombres de campo difieren.
"""
import json
import os
import random

random.seed(42)

MUNICIPIOS = {
    "TUNJA": "15001",
    "PAIPA": "15516",
    "SOGAMOSO": "15759",
    "DUITAMA": "15238",
}

# codpar_CA -> codpar_SE (homologacion de partido entre Camara y Senado)
PARTIDOS = [
    # (codpar_CA, codpar_SE, nombre, color)
    (5, 57, "ALIANZA VERDE", "#007C34"),
    (87, 92, "PACTO HISTORICO", "#7B2D8B"),
    (10, 10, "CENTRO DEMOCRATICO", "#1E477D"),
    (2, 2, "PARTIDO CONSERVADOR", "#E07B00"),
    (1, 1, "PARTIDO LIBERAL", "#D8232A"),
    (4, 4, "CAMBIO RADICAL", "#8C8C8C"),
]

NOMBRES = ["JUAN", "MARIA", "CARLOS", "ANA", "LUIS", "DIANA", "JORGE", "PAOLA",
           "ANDRES", "CAMILA", "FELIPE", "LAURA", "SANTIAGO", "VALENTINA", "DAVID", "SOFIA"]
APELLIDOS = ["GOMEZ", "RODRIGUEZ", "MARTINEZ", "LOPEZ", "GARCIA", "PEREZ",
             "SANCHEZ", "RAMIREZ", "TORRES", "DIAZ", "MORENO", "CASTRO"]


def nombre_candidato():
    return f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"


def generar_municipio(municipio, codmpio, n_puestos=12):
    # Cada partido tiene 2-5 candidatos por corporacion (CA / SE)
    candidatos_por_partido_ca = {
        p[0]: [nombre_candidato() for _ in range(random.randint(2, 5))] for p in PARTIDOS
    }
    candidatos_por_partido_se = {
        p[1]: [nombre_candidato() for _ in range(random.randint(2, 5))] for p in PARTIDOS
    }

    puestos = []
    for i in range(1, n_puestos + 1):
        codpuesto = f"{codmpio}{i:03d}"
        nombre_puesto = f"PUESTO {i} - {municipio}"
        mesas = random.randint(3, 10)

        def votos_corporacion(codpar_key, candidatos_map):
            partidos_resultado = []
            for codpar, candidatos in candidatos_map.items():
                total_partido = random.randint(50, 900) * mesas // 5
                pesos = [random.random() ** 2 for _ in candidatos]  # genera dominancia ocasional
                suma_pesos = sum(pesos)
                votos_cand = [int(total_partido * (w / suma_pesos)) for w in pesos]
                partidos_resultado.append({
                    "codpar": codpar,
                    "candidatos": [
                        {"nombre": nom, "votos": v} for nom, v in zip(candidatos, votos_cand)
                    ],
                    "votos_partido": sum(votos_cand),
                })
            return partidos_resultado

        puestos.append({
            "codpuesto": codpuesto,
            "nombre_puesto": nombre_puesto,
            "mesas": mesas,
            "CA": votos_corporacion("CA", candidatos_por_partido_ca),
            "SE": votos_corporacion("SE", candidatos_por_partido_se),
        })

    return {
        "municipio": municipio,
        "codmpio": codmpio,
        "puestos": puestos,
    }


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    for municipio, codmpio in MUNICIPIOS.items():
        data = generar_municipio(municipio, codmpio)
        path = os.path.join(out_dir, f"{municipio.lower()}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"OK  {municipio}: {path} ({len(data['puestos'])} puestos)")


if __name__ == "__main__":
    main()

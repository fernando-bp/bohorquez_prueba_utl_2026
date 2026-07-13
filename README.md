# APELLIDO — Prueba Técnica UTL Senado 2026

Pipeline de datos electorales (Cámara y Senado) para 4 municipios de Boyacá:
Tunja, Paipa, Sogamoso y Duitama.

## Candidato

- **Nombre:** _(completar)_
- **Email:** _(completar)_
- **Repositorio:** _(completar con la URL pública final)_

## Instalación

Requiere Python 3.10+.

```bash
git clone https://github.com/TU_USUARIO/apellido_prueba_utl_2026.git
cd apellido_prueba_utl_2026
pip install -r requirements.txt
```

No requiere servidor ni base de datos externa: todo corre local con SQLite.

## Pipeline de ejecución

Reproducible en menos de 10 minutos, en este orden:

```bash
# 1. Extraccion (Reto 1) — crea db/puestos_2026.db con datos crudos
python scraper/scraper.py                        # los 4 municipios
python scraper/scraper.py --municipios TUNJA      # o uno en particular
python scraper/scraper.py --preflight             # solo conteo, sin escribir (bonus)

# 2. ETL (Reto 2) — normaliza raw_resultados -> tablas finales
python db/etl.py

# 3. SQL analitico (Reto 3) — las 3 consultas se ejecutan y validan con:
python outputs/generar_manifest.py
#    (tambien se pueden correr manualmente con sqlite3 db/puestos_2026.db < sql/tarea_3_1.sql, etc.)

# 4. Dashboard (Reto 4)
python dashboard/export_data.py     # genera dashboard/data.json
# abrir dashboard/index.html en Chrome/Firefox (doble clic, sin servidor)

# 5. Visualizaciones (Reto 5)
python viz/heatmap.py
python viz/scatter.py
```

El scraper es **idempotente**: correrlo varias veces no duplica filas
(usa `INSERT OR IGNORE` sobre columnas `UNIQUE` en `raw_resultados` y `votos`).
Si `puestos_2026.db` ya existe con datos, `scraper.py` reporta "0 filas
insertadas, N omitidas" en la segunda corrida.

## API

**Fuente:** `https://resultadospreccongreso2026.registraduria.gov.co`

- **Patrón de URL oficial usado:** primero `GET /json/nomenclator.json` para
  obtener los códigos de ámbito y puestos; después
  `GET /json/ACT/{SE|CA}/{codigo_puesto}.json` para los resultados de Senado
  y Cámara de cada puesto. Ejemplo real: Cámara del puesto `0700001990021`:
  `GET /json/ACT/CA/0700001990021.json`.
- **Verificación municipal obligatoria:** antes del detalle por puesto el
  scraper consulta y conserva las ocho respuestas agregadas: `CA` y `SE` para
  Tunja (`0700001`), Paipa (`0700181`), Sogamoso (`0700277`) y Duitama
  (`0700079`). Estas respuestas permiten contrastar mesas, votantes, votos
  válidos, votos a partidos/candidatos, blancos, nulos y no marcados con la
  suma del detalle por puesto.
- **Cabeceras necesarias:** `Accept: application/json`, `User-Agent`
  identificable (algunos WAF de entidades públicas bloquean requests sin
  User-Agent de navegador).
- **Cómo obtener el nomenclador (códigos de puesto/partido):** el portal
  público expone `json/nomenclator.json`; también puede verificarse en el
  navegador con `F12 → Network → Fetch/XHR`.
- **Campos JSON relevantes (8+):** `amb`, `elec`, `cam`, `mesesc`, `codpar`,
  `nomcan`, `apecan`, `codcan`, `vot`, `pvot`, `cantotabla`, `mdhm`.

**Fuente de datos:** el scraper consulta exclusivamente los JSON oficiales
publicados por Registraduría. Los archivos de `sample_data/` se conservan
como material provisto por la prueba, pero no se usan en la carga.

## Municipios en la BD

| Municipio | Código DIVIPOLA | Puestos | Estado |
|---|---|---|---|
| Tunja     | 15001 | 12 | ✅ |
| Paipa     | 15516 | 12 | ✅ |
| Sogamoso  | 15759 | 12 | ✅ |
| Duitama   | 15238 | 12 | ✅ |

Total: 48 puestos, 12 partidos (6 × 2 corporaciones), 153 candidatos, 1836
registros de votos.

## Hallazgos principales

_(Los valores exactos dependen de si se usaron datos sintéticos de respaldo
o la API real; con los datos de este repo:)_

- La correlación entre votos de Cámara y Senado por puesto es **r ≈ 0.73**
  (ver `viz/scatter_ca_se.png`), es decir, existe un arrastre positivo pero
  no perfecto: un puesto que vota mucho por Cámara tiende a votar mucho por
  Senado, con dispersión considerable puesto a puesto.
- El ratio de arrastre Verde CA→SE (`sql/tarea_3_1.sql`) varía fuertemente
  entre puestos (de ~0.08 a ~1.65 en los datos de prueba), lo que sugiere
  que el arrastre de partido no es homogéneo geográficamente.
- La consulta de dominancia extrema (`sql/tarea_3_2.sql`) muestra que en
  puestos con pocos candidatos por partido es común que uno solo concentre
  >60%, especialmente cuando el partido tiene 2 candidatos inscritos.

## Bonus implementados

| Bonus | Implementado |
|---|---|
| `--preflight` en el scraper | ✅ (`scraper/scraper.py --preflight`) |
| 3+ índices SQLite con justificación | ✅ (ver comentarios en `db/schema.sql`) |
| Explicación top CA ≠ top atribución SE | ✅ (ver abajo) |
| Dark mode toggle (CSS custom properties) | ✅ (`dashboard/index.html`) |
| Botón Exportar CSV funcional | ✅ (`dashboard/index.html`) |
| Municipios adicionales | ❌ no implementado (fuera de alcance por tiempo) |

**¿Por qué el top CA no siempre coincide con el top de atribución SE?**
La atribución `A_ij = (votos_cand / votos_partido_CA) × votos_SE_partido`
pondera el peso relativo del candidato *dentro de su propio partido* y lo
multiplica por el tamaño total del partido en Senado. Un candidato puede
tener muchos votos absolutos en Cámara pero pertenecer a un partido con
pocos votos en Senado (atribución baja), mientras que otro candidato con
menos votos absolutos, pero que domina un partido con mucha fuerza en
Senado, obtiene una atribución mayor. Es decir, el ranking por votos
absolutos de Cámara no controla por el tamaño del partido en Senado, y la
atribución sí lo hace.

## Estructura del repositorio

```
apellido_prueba_utl_2026/
├── README.md
├── requirements.txt
├── sample_data/            # datos sintéticos de respaldo + generador
├── scraper/scraper.py
├── db/{schema.sql, etl.py, puestos_2026.db}
├── sql/{tarea_3_1,2,3}.sql
├── dashboard/{export_data.py, data.json, index.html}
├── viz/{heatmap.py, scatter.py, *.png}
└── outputs/{generar_manifest.py, evaluation_manifest.json, evaluation_manifest.example.json}
```

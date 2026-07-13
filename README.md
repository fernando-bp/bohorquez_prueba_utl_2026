# BOHORQUEZ — Prueba Técnica UTL Senado 2026

## Candidato

- **Nombre:** FERNANDO BOHORQUEZ PARRA
- **Email:** fernando.bohorquez@uptc.edu.co
- **Fecha de entrega:** 13 de julio de 2026

## Instalación

Requiere Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` incluye:
- `requests` para descargar JSON oficiales desde la API de Registraduría.
- `matplotlib` para generar los gráficos PNG de `viz/heatmap.py` y `viz/scatter.py`.
- `numpy` para cálculos numéricos, matrices y agregados en las visualizaciones.
- `scipy` para la regresión lineal / coeficiente de correlación en `viz/scatter.py`.

## Pipeline de ejecución

```bash
python scraper/scraper.py
python db/etl.py
python outputs/generar_manifest.py
python dashboard/export_data.py
python viz/heatmap.py
python viz/scatter.py
```

- `python scraper/scraper.py` descarga el nomenclátor oficial y los JSON de CA/SE, creando o actualizando `db/puestos_2026.db` con `raw_resultados`.
- `python db/etl.py` normaliza `raw_resultados` en las tablas finales `municipios`, `partidos`, `puestos`, `candidatos` y `votos`.
- `python outputs/generar_manifest.py` valida la carga, ejecuta las consultas SQL de `sql/` y captura la salida de `viz/scatter.py`, generando `outputs/evaluation_manifest.json`.
- `python dashboard/export_data.py` exporta los datos finales a `dashboard/data.json` para la interfaz.
- `python viz/heatmap.py` genera `viz/heatmap_municipios.png`.
- `python viz/scatter.py` genera `viz/scatter_ca_se.png` e imprime `r=X.XXX | pendiente=X.XXX | n_mesas=NNN`.

El scraper también permite `--preflight` para verificar el listado de puestos y bloques CA/SE sin escribir en SQLite.

## API

La fuente de datos es el API oficial de Registraduría: `https://resultadospreccongreso2026.registraduria.gov.co`.

El patrón de URL a nivel municipio es:

`https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{CORP}/{codigo}.json`

con `{CORP}` = `SE` o `CA`, y los códigos usados:
- TUNJA = `0700001`
- PAIPA = `0700181`
- SOGAMOSO = `0700277`
- DUITAMA = `0700079`

Estos códigos son el `codigo_registraduria` interno del sistema, distinto del DIVIPOLA oficial de 5 dígitos (`15001`, `15516`, `15759`, `15238`).

El nomenclátor se obtiene desde:

`https://resultadospreccongreso2026.registraduria.gov.co/json/nomenclator.json`

La jerarquía real del nomenclátor incluye 7 niveles:
1. Colombia
2. Departamento
3. Municipio
4. Zona
5. Comuna
6. Puesto
7. Mesa

Cada nodo en `amb` tiene un índice `i`, un código `c` y un arreglo `h` de hijos que referencia índices descendientes (`h[].p`). El método correcto para listar puestos es navegar el árbol por índices y referencias de hijos, no forzar códigos de 2 dígitos por fuerza bruta, que produce conteos inflados e inconsistentes entre CA y SE.

El scraper usa HTTP GET público sin autenticación, sin `Authorization` ni token. Solo envía `User-Agent` y `Accept: application/json`. La respuesta es JSON y no requiere reenviar cookies de sesión para lectura.

Campos confirmados en el JSON municipal:
- `elec`: identificador de elección.
- `amb`: código de ámbito interno.
- `tope`: límite o cantidad de cargos disponibles.
- `numact`: número de actas contabilizadas.
- `numdep`: número de departamentos implicados en la consulta.
- `iscircus`: flag de circunscripción.
- `mdhm`: marca de fecha/hora de la última actualización.
- `totales.act`: contiene totales como `mesesc`, `votval`, `votblan`, `votnul`, `votnma`, `votant`, `absten`, `pvotval`, `pvotblan`, `pvotnul`, `pvotnma`.
- `camaras[].act.codpar`: código del partido.
- `camaras[].act.vot`: votos totales del partido.
- `camaras[].act.pvot`: porcentaje de votos del partido.
- `camaras[].act.cantotabla[]`: detalle de candidatos a nivel municipio.

`cantotabla[]` ya contiene el detalle candidato por candidato en el JSON municipal, incluyendo campos como:
- `codcan`
- `cedula`
- `nomcan`
- `apecan`
- `vot`
- `pvot`
- `pref`

Esto confirma que la descarga municipal incluye el detalle de candidatos sin necesidad de bajar inmediatamente al nivel de puesto para obtener esa información.

### Alcance de la fuente y limitación de granularidad

Este proyecto utiliza únicamente las fuentes autorizadas en el enunciado de la
prueba: la API pública de resultados de Congreso 2026 indicada en este
documento y, si esa API no responde, los archivos entregados en
`sample_data/`. No se incorporan archivos externos, fuentes de terceros ni se
generan datos sintéticos para completar observaciones faltantes.

El enunciado solicita que la consulta 3.2 y el gráfico 5.2 se expresen a nivel
de mesa. Sin embargo, la API suministrada por el propio enunciado y los
archivos de respaldo provistos exponen resultados por **puesto**: contienen
`codpuesto` y el total de `mesesc`, pero no exponen un identificador de mesa
(`codmesa`) ni votos de candidatos desagregados por mesa. El nomenclátor de la
API también llega al nivel de puesto para los municipios analizados.

Por esa razón, no es posible desagregar resultados por mesa de manera
verificable sin introducir una fuente distinta de la autorizada o repartir los
votos de un puesto artificialmente entre mesas. Ambas alternativas violarían el
requisito de trabajar con los datos suministrados y producirían información no
respaldada por la fuente. En consecuencia, las consultas y visualizaciones de
este repositorio usan el puesto como unidad observacional y lo indican de forma
explícita. La etiqueta `n_mesas` que imprime `viz/scatter.py` se conserva solo
porque es el formato requerido por el validador especificado en la prueba; su
valor corresponde a los puestos observados, no a mesas individuales.

## Municipios en la BD

| Municipio | Codigo Registraduria | Puestos (BD) | Mesas totales | Filas de votos |
|---|---|---|---|---|
| TUNJA | 0700001 | 26 | 424 | 29302 |
| PAIPA | 0700181 | 7 | 95 | 7889 |
| SOGAMOSO | 0700277 | 18 | 301 | 20286 |
| DUITAMA | 0700079 | 22 | 287 | 24794 |

## Hallazgos principales

- `outputs/generar_manifest.py` valida el pipeline completo y confirma `4/4 municipios`, `8/8 respuestas municipales`, `4/4 líderes SE verificados` y `SQL OK`.
- `sql/tarea_3_1.sql`, `sql/tarea_3_2.sql` y `sql/tarea_3_3.sql` corren sin error en la base normalizada.
- `viz/scatter.py` produce una correlación muy alta entre votos CA y SE por puesto electoral: `r=0.999`, `pendiente=1.006`, `n_puestos=73`. La API disponible publica el detalle candidato por puesto; no se afirma que sean resultados individuales de mesa.
- `viz/heatmap.py` genera un mapa de calor de los 8 candidatos CA con más votos, mostrando su porcentaje del total de votos CA por municipio.

## Bonus implementados

- `scraper/scraper.py --preflight` permite verificar puestos y bloques CA/SE sin escribir en SQLite.
- `db/schema.sql` incluye índices para acelerar consultas analíticas: `idx_puestos_codmpio`, `idx_candidatos_codpar_corp`, `idx_votos_candidato`, `idx_votos_codpuesto`.
- `outputs/generar_manifest.py` genera `outputs/evaluation_manifest.json` con la validación del pipeline.
- `dashboard/index.html` tiene modo oscuro y botón de exportar CSV funcional.
- El pipeline usa solo datos oficiales de Registraduría; `sample_data/` se mantiene como respaldo de datos sintéticos, no como fuente principal.

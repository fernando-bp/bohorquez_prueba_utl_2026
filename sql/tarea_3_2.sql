-- tarea_3_2.sql — Dominancia extrema
-- Puestos donde un candidato concentra > 60% de los votos de su propio
-- partido en ese puesto (para esa corporacion).

WITH votos_partido_puesto AS (
    -- total de votos del partido (candidato + corporacion) en cada puesto
    SELECT
        v.codpuesto,
        c.codpar,
        c.corporacion,
        SUM(v.votos) AS total_partido_puesto
    FROM votos v
    JOIN candidatos c ON c.candidato_id = v.candidato_id
    GROUP BY v.codpuesto, c.codpar, c.corporacion
),
votos_candidato_puesto AS (
    SELECT
        v.codpuesto,
        v.candidato_id,
        c.nombre_normalizado,
        c.codpar,
        c.corporacion,
        v.votos AS votos_candidato
    FROM votos v
    JOIN candidatos c ON c.candidato_id = v.candidato_id
)
SELECT
    m.nombre                                    AS municipio,
    vcp.codpuesto,
    vcp.corporacion,
    p.nombre                                    AS nombre_partido,
    vcp.nombre_normalizado                      AS candidato,
    vcp.votos_candidato,
    vpp.total_partido_puesto,
    ROUND(100.0 * vcp.votos_candidato / vpp.total_partido_puesto, 1) AS pct_del_partido
FROM votos_candidato_puesto vcp
JOIN votos_partido_puesto vpp
    ON vpp.codpuesto = vcp.codpuesto
   AND vpp.codpar = vcp.codpar
   AND vpp.corporacion = vcp.corporacion
JOIN puestos pu ON pu.codpuesto = vcp.codpuesto
JOIN municipios m ON m.codmpio = pu.codmpio
JOIN partidos p ON p.codpar = vcp.codpar AND p.corporacion = vcp.corporacion
WHERE vpp.total_partido_puesto > 0
  AND vcp.nombre_normalizado <> 'SOLO POR LA LISTA'
  AND vcp.votos_candidato > 0.60 * vpp.total_partido_puesto
ORDER BY pct_del_partido DESC;

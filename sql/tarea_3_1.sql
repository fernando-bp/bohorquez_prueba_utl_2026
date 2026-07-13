-- tarea_3_1.sql — Arrastre Alianza Verde CA -> SE
-- Ratio = votos_SE_Verde / votos_CA_Verde por puesto y municipio.
-- Homologacion: codpar_CA = 5 -> codpar_SE = 57.

SELECT
    m.nombre                                   AS municipio,
    p.codpuesto,
    p.nombre                                   AS nombre_puesto,
    COALESCE(ca.votos_ca, 0)                   AS votos_ca_verde,
    COALESCE(se.votos_se, 0)                   AS votos_se_verde,
    ROUND(
        CAST(COALESCE(se.votos_se, 0) AS REAL) /
        NULLIF(ca.votos_ca, 0),
        3
    )                                           AS ratio_arrastre
FROM puestos p
JOIN municipios m ON m.codmpio = p.codmpio
LEFT JOIN (
    SELECT v.codpuesto, SUM(v.votos) AS votos_ca
    FROM votos v
    JOIN candidatos c ON c.candidato_id = v.candidato_id
    WHERE c.corporacion = 'CA' AND c.codpar = 5      -- Alianza Verde CA
    GROUP BY v.codpuesto
) ca ON ca.codpuesto = p.codpuesto
LEFT JOIN (
    SELECT v.codpuesto, SUM(v.votos) AS votos_se
    FROM votos v
    JOIN candidatos c ON c.candidato_id = v.candidato_id
    WHERE c.corporacion = 'SE' AND c.codpar = 57     -- Alianza Verde SE (homologo de 5)
    GROUP BY v.codpuesto
) se ON se.codpuesto = p.codpuesto
ORDER BY m.nombre, p.codpuesto;

-- tarea_3_3.sql — Atribucion deterministica
-- Para cada candidato de Camara (CA), se le atribuye una porcion de los
-- votos consolidados de Senado (SE) de su mismo partido, proporcional a
-- su propio peso dentro del partido en CA:
--
--   A_ij = (votos_cand_CA / votos_partido_CA) * votos_SE_partido
--
-- donde todo esta consolidado (suma de los 4 municipios). Esto estima
-- la "influencia" de arrastre de cada candidato de Camara sobre la
-- votacion de Senado de su partido, sin depender de que el candidato
-- haya sido tambien candidato a Senado.

WITH votos_ca_candidato AS (
    SELECT
        c.candidato_id,
        c.nombre_normalizado,
        c.codpar,
        SUM(v.votos) AS votos_cand_ca
    FROM votos v
    JOIN candidatos c ON c.candidato_id = v.candidato_id
    WHERE c.corporacion = 'CA'
    GROUP BY c.candidato_id, c.nombre_normalizado, c.codpar
),
votos_ca_partido AS (
    SELECT codpar, SUM(votos_cand_ca) AS votos_partido_ca
    FROM votos_ca_candidato
    GROUP BY codpar
),
votos_se_partido AS (
    SELECT c.codpar AS codpar_se, SUM(v.votos) AS votos_partido_se
    FROM votos v
    JOIN candidatos c ON c.candidato_id = v.candidato_id
    WHERE c.corporacion = 'SE'
    GROUP BY c.codpar
)
SELECT
    vcc.nombre_normalizado                       AS candidato_ca,
    pa.nombre                                     AS partido,
    vcc.votos_cand_ca,
    vcap.votos_partido_ca,
    vsp.votos_partido_se,
    ROUND(
        (CAST(vcc.votos_cand_ca AS REAL) / vcap.votos_partido_ca) * vsp.votos_partido_se,
        1
    )                                              AS atribucion_se  -- A_ij
FROM votos_ca_candidato vcc
JOIN votos_ca_partido vcap ON vcap.codpar = vcc.codpar
JOIN partidos pa ON pa.codpar = vcc.codpar AND pa.corporacion = 'CA'
JOIN votos_se_partido vsp ON vsp.codpar_se = pa.codpar_homologo
WHERE vcc.nombre_normalizado <> 'SOLO POR LA LISTA'
ORDER BY atribucion_se DESC
LIMIT 5;

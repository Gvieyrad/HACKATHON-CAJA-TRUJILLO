# Resultados RIE-02 — semilla 202

Pre-registro v4 sha256 `7576ecdad989de11559a749b4943401e0664a7a2df52a40a2f215f8a712123d5`

## Cola final (presupuesto k=50 casos, 12321 solicitudes)

| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola | cola = grupo legít. |
|---|---|---|---|---|---|
| lgbm_puerta | 27 | 0.44 [0.26, 0.63] | 0.30 | 0.013 | 0.48 |
| lgbm_sin_puerta | 50 | 0.42 [0.30, 0.56] | 0.53 | 0.017 | 0.36 |
| lgbm_solo_relacional | 50 | 0.44 [0.32, 0.58] | 0.55 | 0.019 | 0.40 |
| regla_exacta | 50 | 0.26 [0.16, 0.40] | 0.33 | 0.036 | 0.74 |
| regla_exacta_con_tope | 50 | 0.26 [0.16, 0.39] | 0.33 | 0.035 | 0.74 |

Recall por tipología (cola final):

- lgbm_puerta: colusion_asesor=0.00, identidad_sintetica=0.38, prestanombres=0.50, referencias_cruzadas=0.62, sin_atributos=0.00
- lgbm_sin_puerta: colusion_asesor=0.00, identidad_sintetica=0.62, prestanombres=1.00, referencias_cruzadas=1.00, sin_atributos=0.00
- lgbm_solo_relacional: colusion_asesor=0.00, identidad_sintetica=0.75, prestanombres=1.00, referencias_cruzadas=1.00, sin_atributos=0.00
- regla_exacta: colusion_asesor=0.00, identidad_sintetica=0.75, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00
- regla_exacta_con_tope: colusion_asesor=0.00, identidad_sintetica=0.75, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00

## Criterios pre-registrados

- **C1**: NO CUMPLE — {"diferencia_precision": 0.19252647014748486, "ic_lo": -0.026740740740740742, "ic_hi": 0.4139433551198257}
- **C2**: NO CUMPLE — {"valor": 0.48148148148148145}
- **C3**: CUMPLE — {"valor": 1.3279110299609926}
- **C4**: CUMPLE — {"valor": 0.5}

## Anticipación (lgbm_puerta, todas las instantáneas)

- colusion_asesor: 8 anillos, detectados en alguna instantánea 0.38, solicitudes aún evitables al detectar: 0.16666666666666666
- identidad_sintetica: 8 anillos, detectados en alguna instantánea 0.50, solicitudes aún evitables al detectar: 0.0625
- prestanombres: 8 anillos, detectados en alguna instantánea 0.50, solicitudes aún evitables al detectar: 0.0
- referencias_cruzadas: 8 anillos, detectados en alguna instantánea 0.62, solicitudes aún evitables al detectar: 0.0
- sin_atributos: 8 anillos, detectados en alguna instantánea 0.00, solicitudes aún evitables al detectar: None

Mundo sin anillos: 1.33 alertas por 1000 solicitudes.
Expedientes: 27 (fallas del verificador: 0)


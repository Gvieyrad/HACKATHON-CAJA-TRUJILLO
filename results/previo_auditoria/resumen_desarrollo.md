# Resultados RIE-02 — semilla 202

Pre-registro v5 sha256 `8a238067aeba9eafacf217a6daa42207d453f6a17e774ea5c0cbf7f84beb555c`

## Cola final (presupuesto k=50 casos, 12321 solicitudes)

| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola | cola = grupo legít. |
|---|---|---|---|---|---|
| lgbm_puerta | 22 | 0.64 [0.45, 0.82] | 0.35 | 0.008 | 0.36 |
| lgbm_sin_puerta | 50 | 0.40 [0.28, 0.54] | 0.50 | 0.017 | 0.36 |
| lgbm_solo_relacional | 50 | 0.38 [0.26, 0.52] | 0.47 | 0.017 | 0.36 |
| sorpresa | 50 | 0.22 [0.12, 0.34] | 0.28 | 0.037 | 0.78 |
| regla_exacta | 50 | 0.26 [0.16, 0.39] | 0.33 | 0.035 | 0.74 |
| regla_exacta_con_tope | 50 | 0.26 [0.16, 0.39] | 0.33 | 0.035 | 0.74 |

Recall por tipología (cola final):

- lgbm_puerta: colusion_asesor=0.00, identidad_sintetica=0.38, prestanombres=0.75, referencias_cruzadas=0.62, sin_atributos=0.00
- lgbm_sin_puerta: colusion_asesor=0.00, identidad_sintetica=0.50, prestanombres=1.00, referencias_cruzadas=1.00, sin_atributos=0.00
- lgbm_solo_relacional: colusion_asesor=0.00, identidad_sintetica=0.38, prestanombres=1.00, referencias_cruzadas=1.00, sin_atributos=0.00
- sorpresa: colusion_asesor=0.00, identidad_sintetica=0.38, prestanombres=1.00, referencias_cruzadas=0.00, sin_atributos=0.00
- regla_exacta: colusion_asesor=0.00, identidad_sintetica=0.75, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00
- regla_exacta_con_tope: colusion_asesor=0.00, identidad_sintetica=0.75, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00

## Criterios pre-registrados

- **C1**: CUMPLE — {"diferencia_precision": 0.38794734556836036, "ic_lo": 0.15450834879406308, "ic_hi": 0.6283645276292336}
- **C2**: NO CUMPLE — {"valor": 0.36363636363636365}
- **C3**: CUMPLE — {"valor": 1.1619221512158686}
- **C4**: CUMPLE — {"valor": 0.5833333333333334}

## Anticipación (lgbm_puerta, todas las instantáneas)

- colusion_asesor: 8 anillos, detectados en alguna instantánea 0.38, solicitudes aún evitables al detectar: 0.16666666666666666
- identidad_sintetica: 8 anillos, detectados en alguna instantánea 0.75, solicitudes aún evitables al detectar: 0.041666666666666664
- prestanombres: 8 anillos, detectados en alguna instantánea 0.75, solicitudes aún evitables al detectar: 0.0
- referencias_cruzadas: 8 anillos, detectados en alguna instantánea 0.62, solicitudes aún evitables al detectar: 0.0
- sin_atributos: 8 anillos, detectados en alguna instantánea 0.00, solicitudes aún evitables al detectar: None

Mundo sin anillos: 1.16 alertas por 1000 solicitudes.
Expedientes: 22 (fallas del verificador: 0)


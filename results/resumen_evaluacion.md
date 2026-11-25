# Resultados RIE-02 — semilla 777

Pre-registro v5 sha256 `8a238067aeba9eafacf217a6daa42207d453f6a17e774ea5c0cbf7f84beb555c`

## Cola final (presupuesto k=50 casos, 12261 solicitudes)

| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola | cola = grupo legít. |
|---|---|---|---|---|---|
| lgbm_puerta | 32 | 0.59 [0.44, 0.78] | 0.47 | 0.011 | 0.34 |
| lgbm_sin_puerta | 50 | 0.46 [0.33, 0.60] | 0.57 | 0.019 | 0.42 |
| lgbm_solo_relacional | 50 | 0.44 [0.32, 0.58] | 0.55 | 0.015 | 0.32 |
| sorpresa | 50 | 0.24 [0.14, 0.36] | 0.30 | 0.036 | 0.76 |
| regla_exacta | 50 | 0.28 [0.16, 0.42] | 0.35 | 0.035 | 0.72 |
| regla_exacta_con_tope | 50 | 0.28 [0.16, 0.42] | 0.35 | 0.035 | 0.72 |

Recall por tipología (cola final):

- lgbm_puerta: colusion_asesor=0.00, identidad_sintetica=0.88, prestanombres=0.75, referencias_cruzadas=0.75, sin_atributos=0.00
- lgbm_sin_puerta: colusion_asesor=0.00, identidad_sintetica=0.88, prestanombres=1.00, referencias_cruzadas=1.00, sin_atributos=0.00
- lgbm_solo_relacional: colusion_asesor=0.00, identidad_sintetica=0.75, prestanombres=1.00, referencias_cruzadas=1.00, sin_atributos=0.00
- sorpresa: colusion_asesor=0.00, identidad_sintetica=0.62, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00
- regla_exacta: colusion_asesor=0.00, identidad_sintetica=0.88, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00
- regla_exacta_con_tope: colusion_asesor=0.00, identidad_sintetica=0.88, prestanombres=0.88, referencias_cruzadas=0.00, sin_atributos=0.00

## Criterios pre-registrados

- **C1**: CUMPLE — {"diferencia_precision": 0.324095, "ic_lo": 0.11490625, "ic_hi": 0.5275}
- **C2**: NO CUMPLE — {"valor": 0.34375}
- **C3**: CUMPLE — {"valor": 1.0821609922583868}
- **C4**: CUMPLE — {"valor": 0.7916666666666666}

## Anticipación (lgbm_puerta, todas las instantáneas)

- colusion_asesor: 8 anillos, detectados en alguna instantánea 0.38, solicitudes aún evitables al detectar: 0.0787037037037037
- identidad_sintetica: 8 anillos, detectados en alguna instantánea 0.88, solicitudes aún evitables al detectar: 0.0
- prestanombres: 8 anillos, detectados en alguna instantánea 0.88, solicitudes aún evitables al detectar: 0.0
- referencias_cruzadas: 8 anillos, detectados en alguna instantánea 0.88, solicitudes aún evitables al detectar: 0.0
- sin_atributos: 8 anillos, detectados en alguna instantánea 0.00, solicitudes aún evitables al detectar: None

Mundo sin anillos: 1.08 alertas por 1000 solicitudes.
Expedientes: 32 (fallas del verificador: 0)

## Barrido de parámetros del generador (precisión / recall de anillos / grupos legít. en cola)

| parámetros | lgbm_puerta | lgbm_sin_puerta | regla_exacta_con_tope |
|---|---|---|---|
| {'sutileza': 0.0, 'mult_comparticion': 0.5, 'anillos_chicos': False} | 0.96 / 0.55 / 0.000 | 0.52 / 0.62 / 0.011 | 0.32 / 0.40 / 0.057 |
| {'sutileza': 0.0, 'mult_comparticion': 0.5, 'anillos_chicos': True} | 0.86 / 0.47 / 0.000 | 0.44 / 0.55 / 0.015 | 0.32 / 0.40 / 0.057 |
| {'sutileza': 0.0, 'mult_comparticion': 1.0, 'anillos_chicos': False} | 0.54 / 0.47 / 0.013 | 0.46 / 0.57 / 0.014 | 0.26 / 0.33 / 0.036 |
| {'sutileza': 0.0, 'mult_comparticion': 1.0, 'anillos_chicos': True} | 0.69 / 0.50 / 0.008 | 0.43 / 0.53 / 0.017 | 0.20 / 0.25 / 0.038 |
| {'sutileza': 0.0, 'mult_comparticion': 2.0, 'anillos_chicos': False} | 0.32 / 0.40 / 0.012 | 0.34 / 0.42 / 0.013 | 0.18 / 0.23 / 0.021 |
| {'sutileza': 0.0, 'mult_comparticion': 2.0, 'anillos_chicos': True} | 0.35 / 0.42 / 0.011 | 0.37 / 0.45 / 0.011 | 0.02 / 0.03 / 0.024 |
| {'sutileza': 0.5, 'mult_comparticion': 0.5, 'anillos_chicos': False} | 0.82 / 0.45 / 0.005 | 0.50 / 0.62 / 0.024 | 0.32 / 0.40 / 0.054 |
| {'sutileza': 0.5, 'mult_comparticion': 0.5, 'anillos_chicos': True} | 0.88 / 0.35 / 0.002 | 0.49 / 0.60 / 0.013 | 0.33 / 0.40 / 0.052 |
| {'sutileza': 0.5, 'mult_comparticion': 1.0, 'anillos_chicos': False} | 0.54 / 0.33 / 0.011 | 0.48 / 0.60 / 0.015 | 0.28 / 0.35 / 0.035 |
| {'sutileza': 0.5, 'mult_comparticion': 1.0, 'anillos_chicos': True} | 0.50 / 0.33 / 0.012 | 0.40 / 0.50 / 0.019 | 0.22 / 0.28 / 0.038 |
| {'sutileza': 0.5, 'mult_comparticion': 2.0, 'anillos_chicos': False} | 0.26 / 0.33 / 0.015 | 0.32 / 0.40 / 0.013 | 0.14 / 0.17 / 0.021 |
| {'sutileza': 0.5, 'mult_comparticion': 2.0, 'anillos_chicos': True} | 0.24 / 0.30 / 0.010 | 0.37 / 0.45 / 0.008 | 0.06 / 0.07 / 0.023 |
| {'anillos_por_tipologia': 4} | 0.58 / 0.55 / 0.008 | 0.24 / 0.60 / 0.026 | 0.14 / 0.35 / 0.041 |
| {'anillos_por_tipologia': 16} | 0.78 / 0.50 / 0.008 | 0.88 / 0.56 / 0.005 | 0.51 / 0.33 / 0.024 |

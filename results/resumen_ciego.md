# Conjunto ciego: ciego

Autor: agente de contexto limpio (NO independencia humana). Tipologías: {"cadena_avales": 10, "direccion_escalonada": 8, "rafaga_casi_igual": 9, "rotacion_dispositivos": 11}
Pre-registro sha256 `8a238067aeba9eafacf217a6daa42207d453f6a17e774ea5c0cbf7f84beb555c`; k=41 sobre 10250 solicitudes; 38 anillos.

| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola |
|---|---|---|---|---|
| lgbm_puerta | 41 | 0.07 [0.00, 0.17] | 0.08 | 0.020 |
| lgbm_sin_puerta | 41 | 0.05 [0.00, 0.12] | 0.05 | 0.019 |
| lgbm_solo_relacional | 41 | 0.07 [0.00, 0.17] | 0.08 | 0.026 |
| sorpresa | 41 | 0.12 [0.02, 0.24] | 0.13 | 0.021 |
| regla_exacta | 41 | 0.10 [0.00, 0.24] | 0.05 | 0.028 |
| regla_exacta_con_tope | 41 | 0.10 [0.00, 0.24] | 0.05 | 0.028 |

Recall por tipología:

- lgbm_puerta: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.33, rotacion_dispositivos=0.00
- lgbm_sin_puerta: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.22, rotacion_dispositivos=0.00
- lgbm_solo_relacional: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.33, rotacion_dispositivos=0.00
- sorpresa: cadena_avales=0.00, direccion_escalonada=0.25, rafaga_casi_igual=0.33, rotacion_dispositivos=0.00
- regla_exacta: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.18
- regla_exacta_con_tope: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.18

Diferencia de precisión lgbm_puerta menos regla_exacta_con_tope: {"diferencia_precision": -0.018463080181841875, "ic_lo": -0.2, "ic_hi": 0.12195121951219512}
C5 (límite inferior del IC > 0): NO CUMPLE
Diferencia de precisión sorpresa menos regla_exacta_con_tope: {"diferencia_precision": 0.03146374908645081, "ic_lo": -0.15473473648640496, "ic_hi": 0.1926516572858036}

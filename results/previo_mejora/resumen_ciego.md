# Conjunto ciego

Autor: agente de contexto limpio (NO independencia humana). Tipologías: {"cadena_avales": 10, "direccion_escalonada": 8, "rafaga_casi_igual": 9, "rotacion_dispositivos": 11}
Pre-registro sha256 `7576ecdad989de11559a749b4943401e0664a7a2df52a40a2f215f8a712123d5`; k=41 sobre 10250 solicitudes; 38 anillos.

| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola |
|---|---|---|---|---|
| lgbm_puerta | 41 | 0.00 [0.00, 0.00] | 0.00 | 0.020 |
| lgbm_sin_puerta | 41 | 0.00 [0.00, 0.00] | 0.00 | 0.012 |
| lgbm_solo_relacional | 41 | 0.00 [0.00, 0.00] | 0.00 | 0.020 |
| regla_exacta | 41 | 0.10 [0.00, 0.24] | 0.05 | 0.028 |
| regla_exacta_con_tope | 41 | 0.10 [0.00, 0.24] | 0.05 | 0.028 |

Recall por tipología:

- lgbm_puerta: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.00
- lgbm_sin_puerta: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.00
- lgbm_solo_relacional: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.00
- regla_exacta: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.18
- regla_exacta_con_tope: cadena_avales=0.00, direccion_escalonada=0.00, rafaga_casi_igual=0.00, rotacion_dispositivos=0.18

Diferencia de precisión lgbm_puerta − regla_exacta_con_tope: {"diferencia_precision": -0.09217039725501262, "ic_lo": -0.2553191489361702, "ic_hi": 0.0}

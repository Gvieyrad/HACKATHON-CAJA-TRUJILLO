# RIE-02 — Descubrir redes de riesgo ocultas

Detector de redes de solicitudes de crédito sospechosas sobre datos **sintéticos**. Prioriza casos para revisión humana con evidencia verificable. No decide nada de forma automática.

## Conclusión en tres líneas

1. En datos del **mismo generador** con el que se entrenó (semilla de evaluación 777), el sistema superó a la regla de teléfono/dispositivo exacto: precisión 0,59 frente a 0,28 (IC de la diferencia 0,11 – 0,53). **Esa corrida se hizo con código que después resultó tener dos defectos** (ver «Fe de erratas») y, repetido el desarrollo con el código corregido, esa ventaja deja de ser significativa (0,45 frente a 0,26; IC inferior −0,01). Las cifras oficiales pueden bajar.
2. En datos escritos por **otro autor** con tipologías que el sistema no vio (dos conjuntos ciegos), **no generaliza**: en el ciego 2 el sistema saca 0,00 de precisión y queda por debajo de la regla (0,10).
3. Lo que sí mostró señal en ambos ciegos es la puntuación **sin etiquetas** (`sorpresa`), pero la ventaja sobre la regla no es significativa.

No hay evidencia de desempeño con datos reales de la Caja.

## Estado (24-nov-2026)

| Etapa | Estado |
|---|---|
| Generador, detector, expedientes, panel | Hecho; 52 pruebas pasan |
| Pre-registro v5 sellado (`config/preregistro.sha256`) | Sí |
| Evaluación final (semilla 777) | **Corrida una vez** (`results/EVAL_EJECUTADA`) |
| Ciego 1 (`data/ciego`) | Corrido y **ya visto**: no valida, solo informa |
| Ciego 2 (`data/ciego2`) | **Corrido una vez**, con el detector ya fijado |
| Validación dejando una tipología fuera | Hecha |
| Revisión de bugs posterior a la evaluación | Hecha; dos defectos corregidos (ver «Fe de erratas»). 54 pruebas pasan |
| Versión corregida (v6) | **Sin evaluar.** Pendiente: congelar, pre-registrar de nuevo y evaluar una vez con conjuntos nuevos |

## Cómo funciona

1. **Casos.** Las solicitudes se unen por atributo compartido normalizado (teléfono, dispositivo, direcciones, negocio, referencias) y, desde E5, también por texto **casi igual** (distancia de edición ≤ 1) en teléfono y direcciones, con la mitad del peso. Peso `peso_tipo/sqrt(k-1)`; los valores compartidos por más de 12 se excluyen como concentradores (cibercafés, mercados). Componentes conexos; los de más de 25 se parten con Louvain de forma **recursiva** hasta que ninguna comunidad supere 25.
2. **Puntaje.** LightGBM supervisado sobre rasgos del caso, incluidos cuatro rasgos de **sorpresa estadística** sin etiquetas: qué tan improbable es cada vínculo frente a la frecuencia de compartición de la propia instantánea (familias y mercados son comunes, así que no sorprenden).
3. **Puerta de dos familias.** Un caso solo alerta si tiene señal relacional/organizacional **y** señal conductual, más un puntaje mínimo calibrado en un mundo sin anillos.
4. **Cola.** Presupuesto de 0,4 % de las solicitudes, sin casos solapados más de 80 %.
5. **Expediente.** Resumen determinista ("merece revisión"); cada afirmación cita `app_id` y un verificador la recalcula con los datos. Sin lenguaje de culpa.
6. **Panel** (`src/rie02/panel.py`): solo 127.0.0.1, token por sesión. Un rechazo baja a la mitad la prioridad de casos con el mismo patrón.

## Resultados

### Evaluación final, semilla 777 (mismo generador que el entrenamiento; 12 261 solicitudes, cola k=50)

| método | n cola | precisión [IC95 %] | recall anillos |
|---|---|---|---|
| lgbm_puerta (sistema) | 32 | 0,59 [0,44 – 0,78] | 0,47 |
| lgbm_sin_puerta | 50 | 0,46 [0,33 – 0,60] | 0,57 |
| lgbm_solo_relacional | 50 | 0,44 [0,32 – 0,58] | 0,55 |
| sorpresa (sin etiquetas) | 50 | 0,24 [0,14 – 0,36] | 0,30 |
| regla_exacta | 50 | 0,28 [0,16 – 0,42] | 0,35 |
| regla_exacta_con_tope | 50 | 0,28 [0,16 – 0,42] | 0,35 |

| Criterio | Resultado |
|---|---|
| C1: mejora de precisión sobre la regla, IC > 0 | **Cumple** (+0,32; IC 0,11 – 0,53) |
| C2: cola con ≤ 5 % de grupos legítimos | **No cumple** (34 % de la cola) |
| C3: mundo sin anillos ≤ 2,0 alertas/1000 | **Cumple** (1,08) |
| C4: recall de tipologías 1–3 ≥ 0,5 | **Cumple** (0,79) |

Recall por tipología del sistema: identidad_sintetica 0,88; prestanombres 0,75; referencias_cruzadas 0,75; **colusion_asesor 0,00; sin_atributos 0,00**. 32 expedientes, 0 fallas del verificador.

### Conjuntos ciegos (otro autor, tipologías no vistas)

| | lgbm_puerta | lgbm_sin_puerta | sorpresa | regla_exacta_con_tope |
|---|---|---|---|---|
| Ciego 1 (ya visto; 10 250 solicitudes, 38 anillos) | 0,07 | 0,05 | 0,12 | 0,10 |
| **Ciego 2 (una sola vez; 10 000 solicitudes, 34 anillos)** | **0,00** | 0,07 | **0,20** | 0,10 |

Precisión de la cola. En el ciego 2:
- **C5 no se cumple**: sistema menos regla = −0,10, IC [−0,21; −0,02]. La regla gana.
- `sorpresa` menos regla = +0,10, IC [−0,05; 0,26]: ventaja no significativa.
- `sorpresa` encontró 0,88 de las `fraccionamiento_multiagencia`; la regla encontró 0,44 de `enlace_heterogeneo`. Ningún método encontró `domicilio_como_negocio` ni `sim_secuencial`.

### Validación dejando una tipología fuera (mundo de desarrollo)

Recall medio de la tipología retenida: lgbm_sin_puerta 0,38; sorpresa 0,28; regla 0,33. **C6 cumple, por poco.** Dos de las cinco tipologías dan 0 con todos los métodos. El modelo pierde mucho al no verlas (referencias_cruzadas baja de 1,00 a 0,62; identidad_sintetica de 0,50 a 0,25).

**Repetido con el código v6 congelado (25-nov, informativo, no oficial):** recall medio de la tipología retenida: lgbm_sin_puerta 0,40; lgbm_puerta 0,30; sorpresa 0,25; regla 0,33. C6 sigue cumpliendo para `lgbm_sin_puerta`, y `lgbm_puerta` sigue perdiendo contra la regla. En `identidad_sintetica` la regla (0,75) supera al modelo sin verla (0,25). En el desarrollo (semilla 202) con v6 las cifras reproducen exactamente las de la auditoría (lgbm_puerta 0,45 frente a regla 0,26; IC inferior de la diferencia −0,0097; C1 no cumple), lo que confirma el determinismo del código corregido. Archivos: `results/resumen_desarrollo.md`, `results/resumen_loto.md`.

## Historia de enmiendas (lo que se decidió antes y después de ver resultados)

- E1–E4: antes del ciego 1 y de la semilla 777.
- **E5 se decidió DESPUÉS del ciego 1.** El ciego 1 dio 0,00 de precisión del sistema. El diagnóstico posterior mostró casos demasiado grandes y un modelo entrenado solo con el generador propio. E5 añade aristas aproximadas, rasgos y método de sorpresa, Louvain recursivo, redondeo de pesos (networkx 3.7 ciclaba para siempre en el corte 165 del ciego) y los criterios C5 y C6. Los parámetros de E5 no se ajustaron contra ningún ciego. Los resultados de desarrollo anteriores a E5 están en `results/previo_mejora/`.
- Los criterios C5 y C6 se escribieron **antes** de correr el ciego 2 y la semilla 777.
- Al validar el formato del ciego 2 se vieron los **nombres** de sus tipologías, no sus detalles.

## Fe de erratas posterior a la evaluación (auditoría independiente)

**Las corridas oficiales (semilla 777, ciego 2) se declaran tal como se hicieron.** No se repitieron con el código corregido: cada una se corre una sola vez y repetirlas a la vista del resultado sería ajustar.

Defectos encontrados en el código con que se corrieron, ya corregidos:

1. **No determinismo entre procesos.** El orden de un `set` de claves dependía de `PYTHONHASHSEED` y cambiaba el desempate de Louvain. Con la misma entrada salían 251, 263, 270 o 273 casos según el proceso. Las cifras oficiales corresponden a una sola de esas realizaciones y no son exactamente reproducibles.
2. **Unión a distancia de edición 2 y aristas duplicadas.** El borrado de un carácter agrupaba textos que podían estar a distancia 2 (dos dígitos adyacentes cambiados, rotaciones) y podía crear dos aristas del mismo tipo para un par. Esto contradecía E5 («distancia ≤ 1») y duplicaba peso y señales.

**Efecto medido.** Desarrollo (semilla 202, que no es evaluación), antes y después de corregir:

| | precisión del sistema | regla exacta | C1 (IC inferior) |
|---|---|---|---|
| Con el código defectuoso | 0,64 | 0,26 | cumple (+0,15) |
| Con el código corregido | 0,45 | 0,26 | **no cumple (−0,01)** |

La validación por tipología **no se repitió con el código corregido** (la repetición agotó el tiempo); su tabla es la de antes de la auditoría.

**Otros puntos de la auditoría sobre el pre-registro (v5 sellado, que cubre el YAML y no el código):**
- El motivo de E5 dice que los parámetros no se ajustaron contra ningún ciego. Es demasiado fuerte: el ciego 1 se vio con Louvain recursivo (precisión 0,02) antes de fijar las aristas aproximadas y la sorpresa.
- C6 se fijó sobre `lgbm_sin_puerta` y no sobre el sistema principal (`lgbm_puerta`). Con `lgbm_puerta` el recall medio es 0,28 y pierde contra la regla (0,33). La media incluye dos tipologías en 0 para todos los métodos, y el cumplimiento depende de una fila (`referencias_cruzadas`, 0,62 frente a 0).
- Antes no había guarda para que un ciego se corriera una sola vez; ahora `run_all.py` se niega salvo `--repetir-ciego`.
- La cuenta de «concentradores» de los tipos aproximados cuenta claves y no valores; no afecta resultados porque ese dato no se usa.

**Siguiente paso previsto (v6).** Congelar el código corregido con su sha, pre-registrarlo de nuevo y evaluarlo **una sola vez** con conjuntos **nuevos** generados por otra persona o sesión sin que el autor los vea, y reportarlo junto a v5 sin presentarlo como el mismo resultado.

**Huellas SHA-256** (16 primeros caracteres) de los archivos de la corrida oficial v5, medidas el 24-nov-2026:

| archivo | sha256 |
|---|---|
| `config/preregistro.yaml` (v5; sello completo en `config/preregistro.sha256`) | `8a238067aeba9eaf` |
| `results/resultados_evaluacion.json` | `9efd05afb4d6f0de` |
| `results/resumen_evaluacion.md` | `0244c0e862f155ad` |
| `results/cola_evaluacion.json` | `2af78489aafb01c2` |
| `results/resultados_ciego2.json` | `5aba6c2da5fecc08` |
| `results/resumen_ciego2.md` | `0d516a3728a7dd3a` |
| `results/resultados_ciego.json` (ciego 1, corrida con código de E5 antes de la auditoría) | `b44a4835f6bdba33` |
| `results/previo_auditoria/resultados_desarrollo.json` (desarrollo antes de corregir) | `9a4f6a2cd936b324` |
| `results/previo_auditoria/resultados_loto.json` | `a46da3132f4bf811` |
| `data/ciego2/apps.csv` / `etiquetas.csv` | `3da2e3c42ae09696` / `614c8bd4ec7f9931` |

Código **corregido** (no es el que produjo los resultados oficiales; esa versión no se archivó): `grafo.py` `62c83b5994857d0c`, `rasgos.py` `80467a8a53c0bd8b`, `corrida.py` `f5f92b785286047c`, `expediente.py` `ac45d5271dd2e386`, `run_all.py` `a48e52b91cc01a5c`.

## Límites

- Datos sintéticos: el generador y el detector comparten supuestos. El resultado de la semilla 777 no mide generalización; los ciegos sí, y salió mal.
- Ambos ciegos los escribió un agente de contexto limpio, no una persona independiente.
- La puerta cuesta recall (0,47 frente a 0,57 sin ella) a cambio de menos alertas.
- `colusion_asesor` y `sin_atributos` no se detectan.
- Anticipación casi nula: las instantáneas están separadas 15 días.
- Sustituciones: Louvain en lugar de Leiden, panel con stdlib, resumen por plantilla (sin LLM ni agente Dify), sin GNN, sin calibración con ENAHO, sin reproducir el benchmark IBM, sin auditoría de tasa de alertas por zona.
- La validación dejando una tipología fuera solo quita los casos positivos de esa tipología del ajuste.

## Ejecutar

```
pip install -e .
pytest -q
python scripts/sellar.py                       # verifica el sello del pre-registro
python scripts/run_all.py --semilla desarrollo [--barrido]
python scripts/run_all.py --loto               # validación dejando una tipología fuera
python scripts/run_all.py --ciego data/ciego2  # una carpeta con apps.csv y etiquetas.csv
```

La evaluación final ya se corrió; `run_all.py` se niega a repetirla. Todo cambio de código posterior a la evaluación debe declararse como posterior.

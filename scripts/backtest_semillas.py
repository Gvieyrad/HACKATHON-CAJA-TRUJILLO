"""Backtest informativo con VARIAS semillas nuevas del generador propio (v6 congelado, no oficial).

Semillas 1001-1005: distintas de 101/202/303/777. Se reportan TODAS, sin elegir. No toca el codigo ni el pre-registro.
  python scripts/backtest_semillas.py
"""
from __future__ import annotations

import json
import sys

import yaml

import run_all as R  # noqa: E402  (agrega src/ al path)
from rie02.corrida import entrenar_sistema, evaluar  # noqa: E402
from rie02.generador import Params, generar  # noqa: E402

SEMILLAS = (1001, 1002, 1003, 1004, 1005)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    h = R.verificar_sello()
    cfg = yaml.safe_load((R.RAIZ / "config" / "preregistro.yaml").read_text(encoding="utf-8"))
    c = cfg["corte_final"]
    sistema = entrenar_sistema(generar(Params(seed=cfg["semillas"]["entrenamiento"])), cfg)
    filas = []
    for s in SEMILLAS:
        print(f"semilla {s}...", flush=True)
        res = evaluar(sistema, generar(Params(seed=s)), cfg, cfg["cortes_dias"])
        tabla, dif = R.tabla_final(res, cfg)
        r0 = evaluar(sistema, generar(Params(seed=s, anillos_por_tipologia=0)), cfg, [c])
        c3 = len(r0["colas"]["lgbm_puerta"][c]) / (r0["n_apps"][c] / 1000)
        por = {t["metodo"]: t for t in tabla}
        f = dict(semilla=s, prec_puerta=por["lgbm_puerta"]["precision"], prec_regla=por["regla_exacta_con_tope"]["precision"],
                 dif=dif["diferencia_precision"], ic_lo=dif["ic_lo"], ic_hi=dif["ic_hi"],
                 c1=bool(dif["ic_lo"] > 0), c2_cola_legit=por["lgbm_puerta"]["cola_legit_grupo"], c3=c3,
                 c4=R.recall_tipologias_1a3(res["colas"]["lgbm_puerta"][c], res["et"][c]),
                 prec_sin_puerta=por["lgbm_sin_puerta"]["precision"], prec_sorpresa=por["sorpresa"]["precision"])
        filas.append(f)
        print(json.dumps(f, default=R._py), flush=True)
    n = len(filas)
    resumen = dict(prereg_sha=h, semillas=list(SEMILLAS), filas=filas,
                   dif_media=sum(f["dif"] for f in filas) / n, seeds_c1=sum(f["c1"] for f in filas),
                   seeds_dif_positiva=sum(f["dif"] > 0 for f in filas),
                   seeds_c2=sum(f["c2_cola_legit"] <= 0.05 for f in filas), seeds_c3=sum(f["c3"] <= 2.0 for f in filas),
                   seeds_c4=sum(f["c4"] >= 0.5 for f in filas))
    (R.RAIZ / "results" / "backtest_semillas.json").write_text(json.dumps(resumen, indent=1, default=R._py), encoding="utf-8")
    print(json.dumps({k: v for k, v in resumen.items() if k != "filas"}, default=R._py))


if __name__ == "__main__":
    main()

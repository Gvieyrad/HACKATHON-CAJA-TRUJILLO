"""Corrida completa de RIE-02.

  python scripts/run_all.py --semilla desarrollo [--barrido]
  python scripts/run_all.py --semilla evaluacion --confirmar-evaluacion [--barrido]

La semilla de evaluación solo se corre UNA vez (deja results/EVAL_EJECUTADA).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd
import yaml

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from rie02 import expediente as exp_mod  # noqa: E402
from rie02.ciego import cargar_ciego  # noqa: E402
from rie02.corrida import METODOS, entrenar_sistema, evaluar, instantanea  # noqa: E402
from rie02.evaluacion import (anillos_presentes, anticipacion, boot_precision, ic95, ic_diferencia,  # noqa: E402
                              metricas_cola)
from rie02.generador import Params, generar  # noqa: E402
from sellar import SELLO, hash_actual  # noqa: E402

TIPOS_REL = ("identidad_sintetica", "referencias_cruzadas", "prestanombres")


def _py(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


def verificar_sello() -> str:
    if not SELLO.exists():
        sys.exit("Falta sellar el pre-registro (python scripts/sellar.py).")
    h = hash_actual()
    if h != SELLO.read_text().strip():
        sys.exit("El pre-registro cambió después de sellarse: corrida abortada.")
    return h


def recall_tipologias_1a3(Q: pd.DataFrame, et: pd.DataFrame) -> float:
    ani = anillos_presentes(et)
    ani = ani[ani["tipologia"].isin(TIPOS_REL)]
    det = set(Q.loc[Q["y"] == 1, "anillo_dom"])
    return len(det & set(ani.index)) / max(1, len(ani))


def tabla_final(res: dict, cfg: dict) -> tuple[list[dict], dict]:
    c, rep, sem = cfg["corte_final"], cfg["bootstrap"]["repeticiones"], cfg["bootstrap"]["semilla"]
    filas = []
    for m in METODOS:
        Q = res["colas"][m][c]
        x = metricas_cola(Q, res["et"][c])
        lo, hi = ic95(boot_precision(Q, rep, sem))
        filas.append(dict(metodo=m, n_cola=x["n_cola"], precision=x["precision"], prec_ic_lo=lo, prec_ic_hi=hi,
                          recall_anillos=x["recall_total"], fp_grupos_legit=x["fp_grupos_legit"],
                          cola_legit_grupo=x["cola_legit_grupo"], recall_por_tipologia=x["recall_por_tipologia"],
                          fp_por_tipo_grupo=x["fp_por_tipo_grupo"]))
    dif = ic_diferencia(res["colas"]["lgbm_puerta"][c], res["colas"]["regla_exacta_con_tope"][c], rep, sem)
    return filas, dict(diferencia_precision=dif[0], ic_lo=dif[1], ic_hi=dif[2])


def anticipacion_tabla(res: dict, mundo) -> list[dict]:
    ani = mundo.etiquetas.merge(mundo.apps[["app_id", "dia"]], on="app_id")
    ani = ani[ani["anillo_id"] >= 0]
    a = anticipacion(res["colas"]["lgbm_puerta"], ani)
    return [dict(tipologia=t, anillos=len(g), detectados_en_alguna_instantanea=float(g["detectado"].mean()),
                 evitables_medios=float(g["evitables"].mean()) if g["detectado"].any() else None)
            for t, g in a.groupby("tipologia")]


def barrido(sistema, cfg: dict, base_seed: int) -> list[dict]:
    rejillas = [dict(sutileza=s, mult_comparticion=m, anillos_chicos=ch)
                for s in (0.0, 0.5) for m in (0.5, 1.0, 2.0) for ch in (False, True)]
    rejillas += [dict(anillos_por_tipologia=4), dict(anillos_por_tipologia=16)]
    filas = []
    for i, kw in enumerate(rejillas):
        mundo = generar(Params(seed=base_seed + 1000 + i, **kw))
        res = evaluar(sistema, mundo, cfg, [cfg["corte_final"]])
        c = cfg["corte_final"]
        fila = dict(parametros=kw)
        for m in ("lgbm_puerta", "lgbm_sin_puerta", "regla_exacta_con_tope"):
            x = metricas_cola(res["colas"][m][c], res["et"][c])
            fila[m] = dict(precision=x["precision"], recall=x["recall_total"], fp_grupos=x["fp_grupos_legit"])
        filas.append(fila)
        print("  barrido", i + 1, "/", len(rejillas), kw, flush=True)
    return filas


def exportar_cola(sistema, mundo, res: dict, cfg: dict, ruta: pathlib.Path) -> dict:
    c = cfg["corte_final"]
    snap = instantanea(mundo, c, cfg)
    Q = res["colas"]["lgbm_puerta"][c]
    por_id = {caso.caso_id: i for i, caso in enumerate(snap.casos)}
    fams = sistema.puerta.familias(snap.X)
    cola, fallas = [], 0
    for _, fila in Q.iterrows():
        i = por_id[fila["caso_id"]]
        e = exp_mod.construir(snap.casos[i], snap.d, snap.X.iloc[i], fams.iloc[i].to_dict(), fila["score"],
                              c, cfg["caso_asesor"])
        f = exp_mod.verificar(e, snap.d, c, cfg["caso_asesor"])
        fallas += len(f)
        e["resumen"], e["fallas_verificador"] = exp_mod.resumen(e), f
        cola.append({k: v for k, v in e.items() if k != "senales"} | {"senales": [{k: v for k, v in s.items() if k != "pos"} for s in e["senales"]]})
    ruta.write_text(json.dumps(cola, ensure_ascii=False, indent=1, default=_py), encoding="utf-8")
    return dict(expedientes=len(cola), fallas_verificador=fallas)


def veredicto(filas, dif, c3_alertas) -> dict:
    por = {f["metodo"]: f for f in filas}
    lg = por["lgbm_puerta"]
    return dict(
        C1=dict(cumple=bool(dif["ic_lo"] > 0), **dif),
        C2=dict(cumple=bool(lg["cola_legit_grupo"] <= 0.05), valor=lg["cola_legit_grupo"]),  # E3: fracción de la COLA
        C3=dict(cumple=bool(c3_alertas <= 2.0), valor=c3_alertas),
        C4=dict(cumple=None, valor=None),  # se completa fuera (necesita el mundo)
    )


def md(res_json: dict) -> str:
    L = [f"# Resultados RIE-02 — semilla {res_json['semilla']}", "",
         f"Pre-registro v{res_json['version_prereg']} sha256 `{res_json['sha256_prereg']}`", ""]
    L += ["## Cola final (presupuesto k=%d casos, %d solicitudes)" % (res_json["k_final"], res_json["n_apps_final"]), "",
          "| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola | cola = grupo legít. |", "|---|---|---|---|---|---|"]
    for f in res_json["tabla"]:
        L.append(f"| {f['metodo']} | {f['n_cola']} | {f['precision']:.2f} [{f['prec_ic_lo']:.2f}, {f['prec_ic_hi']:.2f}] | "
                 f"{f['recall_anillos']:.2f} | {f['fp_grupos_legit']:.3f} | {f['cola_legit_grupo']:.2f} |")
    L += ["", "Recall por tipología (cola final):", ""]
    for f in res_json["tabla"]:
        L.append(f"- {f['metodo']}: " + ", ".join(f"{t}={v:.2f}" for t, v in sorted(f["recall_por_tipologia"].items())))
    L += ["", "## Criterios pre-registrados", ""]
    for k, v in res_json["veredicto"].items():
        L.append(f"- **{k}**: {'CUMPLE' if v['cumple'] else ('NO CUMPLE' if v['cumple'] is False else 'n/d')} — {json.dumps({a: b for a, b in v.items() if a != 'cumple'}, default=_py)}")
    L += ["", "## Anticipación (lgbm_puerta, todas las instantáneas)", ""]
    L += [f"- {a['tipologia']}: {a['anillos']} anillos, detectados en alguna instantánea {a['detectados_en_alguna_instantanea']:.2f}, "
          f"solicitudes aún evitables al detectar: {a['evitables_medios']}" for a in res_json["anticipacion"]]
    L += ["", f"Mundo sin anillos: {res_json['c3_alertas_por_1000']:.2f} alertas por 1000 solicitudes.",
          f"Expedientes: {res_json['expedientes']} (fallas del verificador: {res_json['fallas_verificador']})", ""]
    if res_json.get("barrido"):
        L += ["## Barrido de parámetros del generador (precisión / recall de anillos / grupos legít. en cola)", "",
              "| parámetros | lgbm_puerta | lgbm_sin_puerta | regla_exacta_con_tope |", "|---|---|---|---|"]
        for b in res_json["barrido"]:
            cel = lambda m: f"{b[m]['precision']:.2f} / {b[m]['recall']:.2f} / {b[m]['fp_grupos']:.3f}"  # noqa: E731
            L.append(f"| {b['parametros']} | {cel('lgbm_puerta')} | {cel('lgbm_sin_puerta')} | {cel('regla_exacta_con_tope')} |")
    return "\n".join(L) + "\n"


def correr_ciego(sistema, cfg: dict, carpeta: str, h: str, out: pathlib.Path, repetir: bool = False) -> None:
    """Evalúa el sistema ya entrenado en un mundo escrito por OTRO autor (tipologías desconocidas)."""
    nombre = pathlib.Path(carpeta).resolve().name
    if (out / f"resultados_{nombre}.json").exists() and not repetir:
        sys.exit(f"El ciego '{nombre}' ya se corrió (results/resultados_{nombre}.json). Un ciego se corre una sola vez; --repetir-ciego lo fuerza.")
    mundo = cargar_ciego(carpeta)
    res = evaluar(sistema, mundo, cfg, cfg["cortes_dias"])
    filas, dif = tabla_final(res, cfg)
    c = cfg["corte_final"]
    ani = anillos_presentes(res["et"][c])
    d_sorp = ic_diferencia(res["colas"]["sorpresa"][c], res["colas"]["regla_exacta_con_tope"][c],
                           cfg["bootstrap"]["repeticiones"], cfg["bootstrap"]["semilla"])
    resultado = dict(carpeta=carpeta, sha256_prereg=h, k_final=res["k"][c], n_apps_final=res["n_apps"][c], tabla=filas,
                     diferencia_vs_regla_con_tope=dif, C5_cumple=bool(dif["ic_lo"] > 0),
                     sorpresa_vs_regla_con_tope=dict(diferencia_precision=d_sorp[0], ic_lo=d_sorp[1], ic_hi=d_sorp[2]),
                     anillos=int(len(ani)),
                     tipologias={t: int(n) for t, n in ani.groupby("tipologia").size().items()},
                     anticipacion=anticipacion_tabla(res, mundo))
    (out / f"resultados_{nombre}.json").write_text(json.dumps(resultado, indent=1, default=_py), encoding="utf-8")
    L = [f"# Conjunto ciego: {nombre}", "",
         "Autor: agente de contexto limpio (NO independencia humana). Tipologías: " + json.dumps(resultado["tipologias"]),
         f"Pre-registro sha256 `{h}`; k={res['k'][c]} sobre {res['n_apps'][c]} solicitudes; {len(ani)} anillos.", "",
         "| método | n cola | precisión [IC95%] | recall anillos | grupos legít. en cola |", "|---|---|---|---|---|"]
    for f in filas:
        L.append(f"| {f['metodo']} | {f['n_cola']} | {f['precision']:.2f} [{f['prec_ic_lo']:.2f}, {f['prec_ic_hi']:.2f}] | "
                 f"{f['recall_anillos']:.2f} | {f['fp_grupos_legit']:.3f} |")
    L += ["", "Recall por tipología:", ""]
    for f in filas:
        L.append(f"- {f['metodo']}: " + ", ".join(f"{t}={v:.2f}" for t, v in sorted(f["recall_por_tipologia"].items())))
    L += ["", f"Diferencia de precisión lgbm_puerta menos regla_exacta_con_tope: {json.dumps(dif)}",
          f"C5 (límite inferior del IC > 0): {'CUMPLE' if resultado['C5_cumple'] else 'NO CUMPLE'}",
          f"Diferencia de precisión sorpresa menos regla_exacta_con_tope: {json.dumps(resultado['sorpresa_vs_regla_con_tope'])}", ""]
    (out / f"resumen_{nombre}.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


def correr_loto(cfg: dict, h: str, out: pathlib.Path) -> None:
    """Validación dejando una tipología fuera (mundo de desarrollo, corte final). Criterio C6."""
    c = cfg["corte_final"]
    entreno = generar(Params(seed=cfg["semillas"]["entrenamiento"]))
    mundo = generar(Params(seed=cfg["semillas"]["desarrollo"]))
    base = evaluar(entrenar_sistema(entreno, cfg), mundo, cfg, [c])  # referencia: sin excluir nada
    tipologias = sorted(anillos_presentes(base["et"][c])["tipologia"].unique())
    metodos = ("lgbm_puerta", "lgbm_sin_puerta", "sorpresa", "regla_exacta_con_tope")
    filas = []
    for t in tipologias:
        print("  LOTO sin", t, flush=True)
        res = evaluar(entrenar_sistema(entreno, cfg, excluir_tipologia=t), mundo, cfg, [c])
        fila = dict(tipologia_retenida=t)
        for m in metodos:
            fila[m] = metricas_cola(res["colas"][m][c], res["et"][c])["recall_por_tipologia"].get(t, 0.0)
            fila[m + "_con_entrenamiento_completo"] = metricas_cola(base["colas"][m][c], base["et"][c])["recall_por_tipologia"].get(t, 0.0)
        filas.append(fila)
    media = {m: float(np.mean([f[m] for f in filas])) for m in metodos}
    resultado = dict(sha256_prereg=h, corte=c, filas=filas, recall_medio_retenida=media,
                     C6_cumple=bool(media["lgbm_sin_puerta"] >= media["regla_exacta_con_tope"]))
    (out / "resultados_loto.json").write_text(json.dumps(resultado, indent=1, default=_py), encoding="utf-8")
    L = ["# Validación dejando una tipología fuera (mundo de desarrollo, corte final)", "",
         "Recall de la tipología retenida (el modelo NO vio positivos de esa tipología al entrenar).", "",
         "| tipología retenida | " + " | ".join(metodos) + " | lgbm_sin_puerta (entrenamiento completo) |", "|---|" + "---|" * (len(metodos) + 1)]
    for f in filas:
        L.append(f"| {f['tipologia_retenida']} | " + " | ".join(f"{f[m]:.2f}" for m in metodos)
                 + f" | {f['lgbm_sin_puerta_con_entrenamiento_completo']:.2f} |")
    L += ["| **media** | " + " | ".join(f"{media[m]:.2f}" for m in metodos) + " | |", "",
          f"C6 (lgbm_sin_puerta >= regla_exacta_con_tope en recall medio de la tipología retenida): "
          f"{'CUMPLE' if resultado['C6_cumple'] else 'NO CUMPLE'}", ""]
    (out / "resumen_loto.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--loto", action="store_true", help="validación dejando una tipología fuera (C6)")
    ap.add_argument("--semilla", choices=("desarrollo", "evaluacion"))
    ap.add_argument("--ciego", help="carpeta con apps.csv y etiquetas.csv escritos por otra persona")
    ap.add_argument("--repetir-ciego", action="store_true", help="vuelve a correr un ciego que ya se corrió (se declara como repetición)")
    ap.add_argument("--confirmar-evaluacion", action="store_true")
    ap.add_argument("--barrido", action="store_true")
    a = ap.parse_args()
    h = verificar_sello()
    cfg = yaml.safe_load((RAIZ / "config" / "preregistro.yaml").read_text(encoding="utf-8"))
    out = RAIZ / "results"
    out.mkdir(exist_ok=True)
    if a.loto:
        correr_loto(cfg, h, out)
        return
    if a.ciego:
        sistema = entrenar_sistema(generar(Params(seed=cfg["semillas"]["entrenamiento"])), cfg)
        correr_ciego(sistema, cfg, a.ciego, h, out, repetir=a.repetir_ciego)
        return
    if not a.semilla:
        sys.exit("Indica --semilla o --ciego.")
    marca = out / "EVAL_EJECUTADA"
    if a.semilla == "evaluacion":
        if not a.confirmar_evaluacion:
            sys.exit("La semilla de evaluación exige --confirmar-evaluacion (se corre una sola vez).")
        if marca.exists():
            sys.exit("La evaluación ya se ejecutó (results/EVAL_EJECUTADA). No se repite.")
    semilla = cfg["semillas"][a.semilla]
    print("entrenando (semilla %d)..." % cfg["semillas"]["entrenamiento"], flush=True)
    sistema = entrenar_sistema(generar(Params(seed=cfg["semillas"]["entrenamiento"])), cfg)
    mundo = generar(Params(seed=semilla))
    print("evaluando (semilla %d)..." % semilla, flush=True)
    res = evaluar(sistema, mundo, cfg, cfg["cortes_dias"])
    c = cfg["corte_final"]
    filas, dif = tabla_final(res, cfg)
    sin_anillos = generar(Params(seed=semilla, anillos_por_tipologia=0))
    r0 = evaluar(sistema, sin_anillos, cfg, [c])
    c3 = len(r0["colas"]["lgbm_puerta"][c]) / (r0["n_apps"][c] / 1000)
    ver = veredicto(filas, dif, c3)
    rec14 = recall_tipologias_1a3(res["colas"]["lgbm_puerta"][c], res["et"][c])
    ver["C4"] = dict(cumple=bool(rec14 >= 0.5), valor=rec14)
    info = exportar_cola(sistema, mundo, res, cfg, out / f"cola_{a.semilla}.json")
    resultado = dict(semilla=semilla, version_prereg=cfg["version"], sha256_prereg=h, k_final=res["k"][c],
                     n_apps_final=res["n_apps"][c], tabla=filas, veredicto=ver, anticipacion=anticipacion_tabla(res, mundo),
                     c3_alertas_por_1000=c3, **info)
    if a.barrido:
        print("barrido de parámetros...", flush=True)
        resultado["barrido"] = barrido(sistema, cfg, semilla)
    (out / f"resultados_{a.semilla}.json").write_text(json.dumps(resultado, indent=1, default=_py), encoding="utf-8")
    (out / f"resumen_{a.semilla}.md").write_text(md(resultado), encoding="utf-8")
    if a.semilla == "evaluacion":
        marca.write_text(f"ejecutada con prereg {h}\n")
    print(md(resultado))


if __name__ == "__main__":
    main()

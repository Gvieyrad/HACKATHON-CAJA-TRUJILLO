"""Métricas pre-registradas: precisión@presupuesto, recall de anillos, falsos positivos de grupos
legítimos, anticipación y bootstrap por clúster (anillo o grupo legítimo dominante)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def anillos_presentes(et: pd.DataFrame, minimo: int = 3) -> pd.DataFrame:
    a = et[et["anillo_id"] >= 0].groupby("anillo_id").agg(tipologia=("tipologia", "first"), n=("app_id", "size"))
    return a[a["n"] >= minimo]


def grupos_legit_presentes(et: pd.DataFrame) -> pd.DataFrame:
    g = et[et["grupo_id"] >= 0].groupby("grupo_id").agg(tipo=("grupo_tipo", "first"), n=("app_id", "size"))
    return g[g["n"] >= 2]


def metricas_cola(Q: pd.DataFrame, et: pd.DataFrame) -> dict:
    """Q = filas de la cola (con columnas de etiqueta de caso); et = etiquetas de las solicitudes presentes."""
    ani, grp = anillos_presentes(et), grupos_legit_presentes(et)
    detectados = set(Q.loc[Q["y"] == 1, "anillo_dom"])
    recall = {t: len(detectados & set(s.index)) / len(s) for t, s in ani.groupby("tipologia")}
    en_cola = set(Q.loc[Q["es_grupo_legit"] == 1, "grupo_dom"])
    fp_tipo = {t: len(en_cola & set(s.index)) / len(s) for t, s in grp.groupby("tipo")}
    return dict(
        n_cola=len(Q),
        precision=float(Q["y"].mean()) if len(Q) else float("nan"),
        recall_total=len(detectados & set(ani.index)) / max(1, len(ani)),
        recall_por_tipologia=recall,
        fp_grupos_legit=len(en_cola & set(grp.index)) / max(1, len(grp)),
        fp_por_tipo_grupo=fp_tipo,
        cola_legit_grupo=float(Q["es_grupo_legit"].mean()) if len(Q) else float("nan"),
    )


def boot_precision(Q: pd.DataFrame, repeticiones: int, semilla: int) -> np.ndarray:
    """Precisión remuestreando CLÚSTERES (anillo/grupo dominante), no casos sueltos."""
    if len(Q) == 0:
        return np.full(repeticiones, np.nan)
    g = Q.groupby("clave")["y"].agg(["sum", "count"]).to_numpy()
    idx = np.random.default_rng(semilla).integers(0, len(g), (repeticiones, len(g)))
    return g[idx, 0].sum(axis=1) / g[idx, 1].sum(axis=1)


def ic95(x: np.ndarray) -> tuple[float, float]:
    return float(np.nanpercentile(x, 2.5)), float(np.nanpercentile(x, 97.5))


def ic_diferencia(Qa: pd.DataFrame, Qb: pd.DataFrame, repeticiones: int, semilla: int) -> tuple[float, float, float]:
    """IC95% de precision(A) - precision(B); remuestreos independientes (conservador)."""
    diff = boot_precision(Qa, repeticiones, semilla) - boot_precision(Qb, repeticiones, semilla + 1)
    lo, hi = ic95(diff)
    return float(np.nanmean(diff)), lo, hi


def anticipacion(colas: dict[int, pd.DataFrame], ani_apps: pd.DataFrame) -> pd.DataFrame:
    """Por anillo: primer corte en que aparece en la cola y fracción de sus solicitudes llegadas DESPUÉS.

    colas: {corte: cola con columnas y/anillo_dom}; ani_apps: columnas anillo_id, tipologia, dia (una fila por solicitud).
    """
    filas = []
    cortes = sorted(colas)
    for r, g in ani_apps.groupby("anillo_id"):
        if len(g) < 3:
            continue
        corte_det = next((c for c in cortes if r in set(colas[c].loc[colas[c]["y"] == 1, "anillo_dom"])), None)
        evitables = float((g["dia"] > corte_det).mean()) if corte_det is not None else float("nan")
        filas.append(dict(anillo_id=r, tipologia=g["tipologia"].iloc[0], detectado=corte_det is not None,
                          corte_deteccion=corte_det, evitables=evitables))
    return pd.DataFrame(filas)

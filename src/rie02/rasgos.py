"""Rasgos por caso (familias relacional y conductual), casos de asesor y etiquetas de evaluación.

El detector NUNCA lee `etiquetas`; solo `etiquetar` lo hace, y solo para evaluar/entrenar.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from .grafo import TIPOS, Caso

FEATURES = (
    ["n_apps", "n_tipos", "peso_medio", "densidad", "cob_max", "frac_ref", "es_asesor"]
    + [f"tiene_{t}" for t in TIPOS]
    + ["n_asesores", "asesor_top_share", "asesor_z", "zona_top_share", "span_dias", "rafaga",
       "z_t_med", "z_r_med", "frac_noche", "frac_redondo", "frac_fallo_dom", "cv_monto", "cv_tiempo", "compuesto"]
    + ["sorp_pares", "sorp_valores", "sorp_total", "sorp_media"]  # E5: sorpresa frente a la compartición de base
)


def base_sorpresa(casos: list[Caso]) -> dict:
    """Frecuencias de base de la PROPIA instantánea, sin etiquetas (E5).

    `tam[tipo]`: tamaños de los valores compartidos; `mult`: cuántos tipos distintos unen a cada par vinculado.
    Se asume que los anillos son raros frente a la compartición legítima (familias, mercados).
    """
    tam: dict = defaultdict(list)
    mult: list = []
    for c in casos:
        por_par: dict = defaultdict(set)
        por_valor: dict = defaultdict(set)
        for i, j, t, v, _w in c.aristas:
            por_par[(i, j)].add(t)
            por_valor[(t, v)].update((i, j))
        mult += [len(x) for x in por_par.values()]
        for (t, _v), s in por_valor.items():
            tam[t].append(len(s))
    return dict(mult=np.sort(np.array(mult, dtype=float)), tam={t: np.sort(np.array(x, dtype=float)) for t, x in tam.items()})


def _sorpresa(ordenado: np.ndarray, x: float) -> float:
    """-log P(X >= x) empírica con suavizado de +1; 0 para el valor más común."""
    n = len(ordenado)
    n_ge = n - int(np.searchsorted(ordenado, x, side="left"))
    return -math.log((n_ge + 1) / (n + 1))


def agregar_conducta(d: pd.DataFrame, umbral_z: float) -> pd.DataFrame:
    """z-scores NO supervisados (media/desvío de la propia instantánea) y marca de anomalía."""
    d = d.copy()
    lt = np.log(d["tiempo_llenado_seg"].to_numpy())
    d["z_t"] = (lt - lt.mean()) / (lt.std() + 1e-9)
    r = d["ratio_monto"].to_numpy()
    d["z_r"] = (r - r.mean()) / (r.std() + 1e-9)
    d["noche"] = ((d["hora"] < 8) | (d["hora"] >= 20)).astype(int)
    d["redondo"] = (d["monto"] % 500 == 0).astype(int)
    d["fallo_dom"] = 1 - d["verif_domicilio_ok"]
    d["marca"] = ((d["fallo_dom"] == 1) | (d["z_r"] > umbral_z) | (d["z_t"] < -umbral_z)).astype(int)
    return d


def asesor_volumen(d: pd.DataFrame, corte: int, cfg: dict, asesor: str) -> tuple[int, float, float]:
    """(solicitudes en la ventana, esperadas según SU historia, z). Señal de VOLUMEN, no de conducta (E4).

    Esperado = tasa diaria suavizada (historia propia + `prior_fuerza` días a la tasa global) × ventana.
    """
    v, f = cfg["ventana_dias"], cfg["prior_fuerza"]
    dias_h = max(1, corte - v + 1)
    tasa_global = (d["dia"] <= corte - v).sum() / max(1, d["asesor_id"].nunique()) / dias_h
    g = d[d["asesor_id"] == asesor]
    n_w, h = int((g["dia"] > corte - v).sum()), int((g["dia"] <= corte - v).sum())
    mu = max((h + f * tasa_global) / (dias_h + f) * v, 1e-6)
    return n_w, mu, (n_w - mu) / math.sqrt(mu)


def asesor_z(d: pd.DataFrame, corte: int, cfg: dict) -> dict:
    """z de volumen de cada asesor en la ventana reciente frente a su propia historia."""
    return {a: asesor_volumen(d, corte, cfg, a)[2] for a in d["asesor_id"].unique()}


def casos_asesor(d: pd.DataFrame, corte: int, cfg: dict) -> list[Caso]:
    sel = d[(d["dia"] > corte - cfg["ventana_dias"]) & (d["marca"] == 1)]
    casos = []
    for a, g in sel.groupby("asesor_id"):
        if len(g) >= cfg["min_solicitudes_marcadas"]:
            casos.append(Caso(f"S_{a}", "asesor", g.index.tolist(), [], asesor=a))
    return casos


def _estructura(caso: Caso, n: int) -> dict:
    f = {f"tiene_{t}": 0 for t in TIPOS}
    f.update(n_tipos=0, peso_medio=0.0, densidad=0.0, cob_max=0.0, frac_ref=0.0)
    if not caso.aristas:
        return f
    pares = {(i, j) for i, j, *_ in caso.aristas}
    por_valor: dict = defaultdict(set)
    en_ref: set = set()
    for i, j, t, v, _w in caso.aristas:
        f[f"tiene_{t}"] = 1
        por_valor[(t, v)].update((i, j))
        if t == "referencia":
            en_ref.update((i, j))
    f["n_tipos"] = sum(f[f"tiene_{t}"] for t in TIPOS)
    f["peso_medio"] = sum(w for *_x, w in caso.aristas) / n
    f["densidad"] = len(pares) / (n * (n - 1) / 2)
    f["cob_max"] = max(len(s) for s in por_valor.values()) / n
    f["frac_ref"] = len(en_ref) / n
    return f


def _cv(x: np.ndarray) -> float:
    return float(x.std() / x.mean()) if x.mean() else 0.0


def _sorpresas_caso(caso: Caso, base: dict | None) -> dict:
    f = dict(sorp_pares=0.0, sorp_valores=0.0)
    if base is None or not caso.aristas:
        return f | dict(sorp_total=0.0, sorp_media=0.0)
    por_par: dict = defaultdict(set)
    por_valor: dict = defaultdict(set)
    for i, j, t, v, _w in caso.aristas:
        por_par[(i, j)].add(t)
        por_valor[(t, v)].update((i, j))
    if len(base["mult"]):
        f["sorp_pares"] = sum(_sorpresa(base["mult"], len(x)) for x in por_par.values())
    f["sorp_valores"] = sum(_sorpresa(base["tam"][t], len(s)) for (t, _v), s in por_valor.items() if len(base["tam"].get(t, ())))
    total = f["sorp_pares"] + f["sorp_valores"]
    return f | dict(sorp_total=total, sorp_media=total / len(caso.apps))


def vector(caso: Caso, d: pd.DataFrame, az: dict, base: dict | None = None) -> dict:
    idx = np.array(caso.apps)
    n = len(idx)
    sub = d.iloc[idx]
    f = _estructura(caso, n) | _sorpresas_caso(caso, base)
    ases = Counter(sub["asesor_id"])
    top_asesor, top_n = ases.most_common(1)[0]
    dias = sub["dia"].to_numpy()
    f.update(
        n_apps=n, es_asesor=int(caso.tipo == "asesor"), n_asesores=len(ases), asesor_top_share=top_n / n,
        asesor_z=az.get(top_asesor, 0.0), zona_top_share=Counter(sub["zona"]).most_common(1)[0][1] / n,
        span_dias=int(dias.max() - dias.min()), rafaga=n / (int(dias.max() - dias.min()) + 1),
        z_t_med=float(sub["z_t"].mean()), z_r_med=float(sub["z_r"].mean()),
        frac_noche=float(sub["noche"].mean()), frac_redondo=float(sub["redondo"].mean()),
        frac_fallo_dom=float(sub["fallo_dom"].mean()),
        cv_monto=_cv(sub["monto"].to_numpy()), cv_tiempo=_cv(sub["tiempo_llenado_seg"].to_numpy()),
    )
    f["compuesto"] = -f["z_t_med"] + f["z_r_med"] + 3 * f["frac_fallo_dom"] + 2 * f["frac_noche"]
    return f


def tabla_casos(d: pd.DataFrame, casos: list[Caso], az: dict) -> pd.DataFrame:
    base = base_sorpresa(casos)
    filas = [{"caso_id": c.caso_id, "tipo": c.tipo, **vector(c, d, az, base)} for c in casos]
    cols = ["caso_id", "tipo"] + FEATURES
    return pd.DataFrame(filas, columns=cols)


def etiquetar(casos: list[Caso], d: pd.DataFrame, etiquetas: pd.DataFrame, cfg_et: dict) -> pd.DataFrame:
    """Etiqueta de caso para EVALUAR (nunca como entrada del detector)."""
    m = etiquetas.set_index("app_id").loc[d["app_id"]]
    anillo, grupo = m["anillo_id"].to_numpy(), m["grupo_id"].to_numpy()
    tipolog, gtipo = m["tipologia"].to_numpy(), m["grupo_tipo"].to_numpy()
    filas = []
    for c in casos:
        idx = np.array(c.apps)
        n = len(idx)
        a = Counter(int(x) for x in anillo[idx] if x >= 0)
        g = Counter(int(x) for x in grupo[idx] if x >= 0)
        a_id, a_n = a.most_common(1)[0] if a else (-1, 0)
        g_id, g_n = g.most_common(1)[0] if g else (-1, 0)
        y = int(a_n >= cfg_et["min_solicitudes_anillo"] and a_n / n >= cfg_et["pureza_minima"])
        es_grupo = int(not y and g_n / n >= cfg_et["pureza_minima"] and g_n >= 2)
        clave = f"anillo:{a_id}" if y else (f"grupo:{g_id}" if es_grupo else f"caso:{c.caso_id}")
        filas.append(dict(
            y=y, anillo_dom=a_id if y else -1, anillo_n=a_n,
            tipologia_dom=str(tipolog[idx][anillo[idx] == a_id][0]) if y else "",
            es_grupo_legit=es_grupo, grupo_dom=g_id if es_grupo else -1,
            grupo_tipo_dom=str(gtipo[idx][grupo[idx] == g_id][0]) if es_grupo else "", clave=clave,
        ))
    cols = ["y", "anillo_dom", "anillo_n", "tipologia_dom", "es_grupo_legit", "grupo_dom", "grupo_tipo_dom", "clave"]
    return pd.DataFrame(filas, columns=cols)

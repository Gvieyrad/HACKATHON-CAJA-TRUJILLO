"""Modelos: puerta de dos familias de señal, LightGBM, reglas exactas y construcción de la cola."""
from __future__ import annotations

import math

import lightgbm as lgb
import numpy as np
import pandas as pd

from .grafo import casos_relacionales
from .rasgos import FEATURES

CONDUCTUALES = ["z_t_med", "z_r_med", "frac_noche", "frac_redondo", "frac_fallo_dom", "cv_monto", "cv_tiempo", "compuesto"]
SOLO_RELACIONALES = [f for f in FEATURES if f not in CONDUCTUALES]


class Puerta:
    """Una alerta exige DOS familias independientes: relacional/organizacional y conductual.

    Los umbrales salen de percentiles de la tabla de casos de ENTRENAMIENTO, sin usar etiquetas.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.tau_rel: float | None = None
        self.tau_cond: float | None = None
        self.score_minimo: float = 0.0  # piso absoluto de puntaje; lo fija corrida.calibrar_piso

    def ajustar(self, X: pd.DataFrame) -> "Puerta":
        rel = X[X["es_asesor"] == 0]
        self.tau_rel = float(np.percentile(rel["peso_medio"], self.cfg["percentil_relacional"]))
        self.tau_cond = float(np.percentile(X["compuesto"], self.cfg["percentil_conductual"]))
        return self

    def familias(self, X: pd.DataFrame) -> pd.DataFrame:
        assert self.tau_rel is not None, "Puerta sin ajustar"
        rel_ok = np.where(X["es_asesor"] == 1, X["asesor_z"] >= self.cfg["asesor_z_minimo"], X["peso_medio"] >= self.tau_rel)
        return pd.DataFrame({"fam_relacional": rel_ok.astype(bool), "fam_conductual": (X["compuesto"] >= self.tau_cond).to_numpy()},
                            index=X.index)

    def pasa(self, X: pd.DataFrame) -> np.ndarray:
        f = self.familias(X)
        return (f["fam_relacional"] & f["fam_conductual"]).to_numpy()


def entrenar(X: pd.DataFrame, y: np.ndarray, cfg_modelo: dict, columnas: list[str], semilla: int) -> lgb.LGBMClassifier:
    m = lgb.LGBMClassifier(**cfg_modelo["lightgbm"], random_state=semilla, verbose=-1)
    m.fit(X[columnas].astype(float), y)
    return m


def puntuar(modelo: lgb.LGBMClassifier, X: pd.DataFrame, columnas: list[str]) -> np.ndarray:
    return modelo.predict_proba(X[columnas].astype(float))[:, 1]


def presupuesto(n_apps: int, fraccion: float) -> int:
    return max(1, math.ceil(fraccion * n_apps))


def cola(casos: list, score: np.ndarray, pasa: np.ndarray, k: int, solape: float) -> list[int]:
    """Índices de los casos de la cola: mejores primero, solo los que pasan, sin duplicar solapados."""
    orden = np.argsort(-np.asarray(score, dtype=float), kind="stable")
    elegidos: list[int] = []
    vistos: list[set] = []
    for i in orden:
        if not pasa[i]:
            continue
        s = set(casos[i].apps)
        if any(len(s & t) / len(s) >= solape for t in vistos):
            continue
        elegidos.append(int(i))
        vistos.append(s)
        if len(elegidos) == k:
            break
    return elegidos


def casos_regla(d: pd.DataFrame, cfg_grafo: dict, con_tope: bool) -> list:
    """Regla convencional: componentes por teléfono o dispositivo EXACTO; puntaje = tamaño."""
    tope = cfg_grafo["tope_compartido"] if con_tope else None
    casos, _ = casos_relacionales(d, cfg_grafo, tipos=("telefono", "dispositivo"), tope=tope)
    return casos

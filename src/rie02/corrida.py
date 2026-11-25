"""Pipeline: instantáneas "a la fecha" (solo solicitudes con dia <= corte), entrenamiento y colas por método."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .grafo import casos_relacionales, preparar
from .modelos import SOLO_RELACIONALES, Puerta, casos_regla, cola, entrenar, presupuesto, puntuar
from .rasgos import FEATURES, agregar_conducta, asesor_z, casos_asesor, etiquetar, tabla_casos

METODOS = ("lgbm_puerta", "lgbm_sin_puerta", "lgbm_solo_relacional", "sorpresa", "regla_exacta", "regla_exacta_con_tope")


@dataclass
class Instantanea:
    corte: int
    d: pd.DataFrame
    casos: list
    X: pd.DataFrame
    L: pd.DataFrame


@dataclass
class Sistema:
    puerta: Puerta
    m_full: object
    m_rel: object


def instantanea(mundo, corte: int, cfg: dict, semilla: int = 0) -> Instantanea:
    apps = mundo.apps[mundo.apps["dia"] <= corte]  # as-of: nada posterior al corte
    d = agregar_conducta(preparar(apps), cfg["caso_asesor"]["umbral_z_marca"])
    cr, _ = casos_relacionales(d, cfg["grafo"], semilla=semilla)
    az = asesor_z(d, corte, cfg["caso_asesor"])
    casos = cr + casos_asesor(d, corte, cfg["caso_asesor"])
    return Instantanea(corte, d, casos, tabla_casos(d, casos, az),
                       etiquetar(casos, d, mundo.etiquetas, cfg["etiqueta_caso"]))


def calibrar_piso(sistema: Sistema, mundo_cal, cfg: dict) -> float:
    """Piso de puntaje: en un mundo SIN anillos, tras la puerta, solo caben `alertas_max_por_1000` alertas."""
    snap = instantanea(mundo_cal, cfg["corte_final"], cfg)
    if not len(snap.X):
        return 0.0
    s = puntuar(sistema.m_full, snap.X, FEATURES)[sistema.puerta.pasa(snap.X)]
    permitidas = int(cfg["puerta"]["alertas_max_por_1000"] * len(snap.d) / 1000)
    s = np.sort(s)[::-1]
    return float(s[permitidas]) if len(s) > permitidas else 0.0


def entrenar_sistema(mundo, cfg: dict, excluir_tipologia: str | None = None) -> Sistema:
    """`excluir_tipologia`: validación dejando una tipología fuera; se quitan del ajuste los casos positivos de esa tipología."""
    from .generador import generar  # import local: el mundo de calibración comparte los parámetros del de entrenamiento
    snaps = [instantanea(mundo, c, cfg) for c in cfg["cortes_dias"]]
    X = pd.concat([s.X for s in snaps], ignore_index=True)
    L = pd.concat([s.L for s in snaps], ignore_index=True)
    y = L["y"].to_numpy()
    if excluir_tipologia is not None:
        quedan = (L["tipologia_dom"] != excluir_tipologia).to_numpy()
        X, y = X[quedan].reset_index(drop=True), y[quedan]
    sem = cfg["semillas"]["entrenamiento"]
    sis = Sistema(Puerta(cfg["puerta"]).ajustar(X), entrenar(X, y, cfg["modelo"], FEATURES, sem),
                  entrenar(X, y, cfg["modelo"], SOLO_RELACIONALES, sem))
    cal = generar(mundo.params.con(seed=cfg["semillas"]["calibracion"], anillos_por_tipologia=0))
    sis.puerta.score_minimo = calibrar_piso(sis, cal, cfg)
    return sis


def colas_de(sistema: Sistema, mundo, snap: Instantanea, cfg: dict) -> tuple[dict, int]:
    """Cola de revisión de cada método en una instantánea. Devuelve ({método: DataFrame}, presupuesto)."""
    k = presupuesto(len(snap.d), cfg["presupuesto"]["fraccion_solicitudes"])
    solape = cfg["presupuesto"]["solapamiento_dedupe"]

    def armar(casos, L, score, pasa):
        idx = cola(casos, score, pasa, k, solape)
        Q = L.iloc[idx].copy()
        Q.insert(0, "caso_id", [casos[i].caso_id for i in idx])
        Q["score"] = np.asarray(score, dtype=float)[idx]
        return Q

    X, n = snap.X, len(snap.X)
    todos = np.ones(n, dtype=bool)
    s_full = puntuar(sistema.m_full, X, FEATURES) if n else np.array([])
    s_rel = puntuar(sistema.m_rel, X, SOLO_RELACIONALES) if n else np.array([])
    out = {
        "lgbm_puerta": armar(snap.casos, snap.L, s_full,
                             (sistema.puerta.pasa(X) & (s_full > sistema.puerta.score_minimo)) if n else todos),
        "lgbm_sin_puerta": armar(snap.casos, snap.L, s_full, todos),
        "lgbm_solo_relacional": armar(snap.casos, snap.L, s_rel, todos),
        # E5: sin etiquetas ni modelo; ordena por sorpresa media por solicitud frente a la compartición de base
        "sorpresa": armar(snap.casos, snap.L, X["sorp_media"].to_numpy() if n else np.array([]), todos),
    }
    for nombre, con_tope in (("regla_exacta", False), ("regla_exacta_con_tope", True)):
        cr = casos_regla(snap.d, cfg["grafo"], con_tope)
        Lr = etiquetar(cr, snap.d, mundo.etiquetas, cfg["etiqueta_caso"])
        out[nombre] = armar(cr, Lr, np.array([len(c.apps) for c in cr], dtype=float), np.ones(len(cr), dtype=bool))
    return out, k


def evaluar(sistema: Sistema, mundo, cfg: dict, cortes: list[int]) -> dict:
    """{'colas': {método: {corte: Q}}, 'et': {corte: etiquetas presentes}, 'k': {corte: presupuesto}, 'n_apps': {...}}."""
    res = {"colas": {m: {} for m in METODOS}, "et": {}, "k": {}, "n_apps": {}}
    for c in cortes:
        snap = instantanea(mundo, c, cfg)
        colas, k = colas_de(sistema, mundo, snap, cfg)
        for m, Q in colas.items():
            res["colas"][m][c] = Q
        res["et"][c] = mundo.etiquetas[mundo.etiquetas["app_id"].isin(snap.d["app_id"])]
        res["k"][c], res["n_apps"][c] = k, len(snap.d)
    return res

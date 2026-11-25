"""Carga y valida un conjunto CIEGO escrito por otra persona (mismo esquema que el generador).

El autor del detector no debe conocer las tipologías del conjunto ciego. Este módulo solo lee y valida.
"""
from __future__ import annotations

import pathlib

import pandas as pd

from .generador import Mundo

COLUMNAS_APPS = [
    "app_id", "dia", "persona_id", "telefono_raw", "dispositivo", "direccion_hogar_raw", "direccion_negocio_raw",
    "negocio_id", "ref1_id", "ref2_id", "asesor_id", "agencia_id", "zona", "tiempo_llenado_seg", "hora",
    "ratio_monto", "monto", "verif_domicilio_ok",
]
COLUMNAS_ETIQUETAS = ["app_id", "anillo_id", "tipologia", "grupo_id", "grupo_tipo"]


def cargar_ciego(carpeta: str | pathlib.Path, dias: int = 180) -> Mundo:
    c = pathlib.Path(carpeta)
    apps = pd.read_csv(c / "apps.csv", dtype=str, keep_default_na=True).copy()
    etiquetas = pd.read_csv(c / "etiquetas.csv", dtype={"app_id": str, "tipologia": str, "grupo_tipo": str})
    faltan = [x for x in COLUMNAS_APPS if x not in apps.columns] + [x for x in COLUMNAS_ETIQUETAS if x not in etiquetas.columns]
    if faltan:
        raise ValueError(f"faltan columnas: {faltan}")
    for col in ("dia", "zona", "hora", "verif_domicilio_ok"):
        apps[col] = pd.to_numeric(apps[col], errors="raise").astype(int)
    for col in ("tiempo_llenado_seg", "ratio_monto", "monto"):
        apps[col] = pd.to_numeric(apps[col], errors="raise").astype(float)
    if apps[["tiempo_llenado_seg", "ratio_monto", "monto"]].isna().any().any():
        raise ValueError("hay valores vacíos en tiempo_llenado_seg, ratio_monto o monto")
    if (apps["tiempo_llenado_seg"] <= 0).any() or (apps["monto"] <= 0).any():
        raise ValueError("tiempo_llenado_seg y monto deben ser > 0")
    if not apps["app_id"].is_unique:
        raise ValueError("app_id repetido en apps.csv")
    if set(apps["app_id"]) != set(etiquetas["app_id"]) or not etiquetas["app_id"].is_unique:
        raise ValueError("apps.csv y etiquetas.csv no tienen los mismos app_id (o hay repetidos)")
    if not apps["dia"].between(0, dias - 1).all():
        raise ValueError(f"dia fuera de 0..{dias - 1}")
    if not apps["verif_domicilio_ok"].isin([0, 1]).all():
        raise ValueError("verif_domicilio_ok debe ser 0 o 1")
    tam = etiquetas[etiquetas["anillo_id"] >= 0].groupby("anillo_id").size()
    if len(tam) == 0 or (tam < 3).any():
        raise ValueError("cada anillo debe tener al menos 3 solicitudes y debe haber al menos un anillo")
    return Mundo(apps=apps[COLUMNAS_APPS], etiquetas=etiquetas[COLUMNAS_ETIQUETAS], params=None)  # type: ignore[arg-type]

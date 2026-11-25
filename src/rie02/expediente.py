"""Expediente de evidencia por caso.

Reglas de las bases, aplicadas en código:
- Una alerta exige al menos dos familias de señal independientes (relacional y conductual).
- El lenguaje es "merece revisión": nunca se afirma fraude ni se asigna culpa.
- Cada afirmación remite a solicitudes concretas (app_id) y un verificador la recalcula con los datos.
- Sin veredictos automáticos: el expediente termina siempre en revisión humana.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

import numpy as np
import pandas as pd

from .grafo import APROX, COLUMNA_DE, LARGO_MIN_APROX, Caso, claves_aprox
from .rasgos import asesor_volumen

PALABRAS_PROHIBIDAS = ("fraude", "fraudulent", "culpable", "delincuente", "estafa", "criminal")
LEGIBLE = {
    "telefono": "el mismo teléfono", "dispositivo": "el mismo dispositivo", "direccion_hogar": "la misma dirección de domicilio",
    "direccion_negocio": "la misma dirección de negocio", "negocio": "el mismo negocio", "referencia": "la misma persona de referencia",
    "telefono_aprox": "un teléfono casi igual", "direccion_hogar_aprox": "una dirección de domicilio casi igual",
    "direccion_negocio_aprox": "una dirección de negocio casi igual",
}
EXPLICACIONES_LEGITIMAS = {
    "telefono": "Familias y puestos de un mismo comercio suelen compartir un teléfono.",
    "dispositivo": "Un celular familiar o un cibercafé puede usarse para varias solicitudes.",
    "direccion_hogar": "Los miembros de un hogar comparten domicilio.",
    "direccion_negocio": "Los puestos de un mismo mercado comparten dirección comercial.",
    "negocio": "Un negocio familiar puede figurar en más de una solicitud.",
    "referencia": "Un empleador o familiar común puede ser referencia de varias personas.",
    "telefono_aprox": "Un error de digitación o dos líneas de una misma familia pueden dar números casi iguales.",
    "direccion_hogar_aprox": "Una misma vivienda puede escribirse de formas ligeramente distintas, o ser viviendas contiguas.",
    "direccion_negocio_aprox": "Un mismo local puede escribirse de formas ligeramente distintas, o ser puestos contiguos.",
}
TIPOS_VERIFICABLES = set(COLUMNA_DE) | {"referencia"} | set(APROX)


def _mascara(tipo: str, valor: str) -> str:
    if tipo == "telefono":
        return f"…{valor[-3:]}"
    return f"[{tipo}:{int(hashlib.md5(valor.encode()).hexdigest(), 16) % 10000:04d}]"  # estable entre ejecuciones


def _pertenece(d: pd.DataFrame, pos: int, tipo: str, valor: str) -> bool:
    if tipo == "referencia":
        return valor in (d["ref1_id"].iat[pos], d["ref2_id"].iat[pos], d["persona_id"].iat[pos])
    if tipo in APROX:
        s = d[APROX[tipo]].iat[pos]
        return isinstance(s, str) and len(s) >= LARGO_MIN_APROX and valor in claves_aprox(s)
    return d[COLUMNA_DE[tipo]].iat[pos] == valor


def _agregado(sub: pd.DataFrame) -> dict:
    return dict(z_tiempo=round(float(sub["z_t"].mean()), 3), z_ratio=round(float(sub["z_r"].mean()), 3),
                fallo_dom=int(sub["fallo_dom"].sum()), noche=int(sub["noche"].sum()), n=int(len(sub)))


def construir(caso: Caso, d: pd.DataFrame, fila: pd.Series, fam: dict, score: float,
              corte: int, cfg_asesor: dict) -> dict:
    """fila: rasgos del caso; fam: {'fam_relacional': bool, 'fam_conductual': bool}.

    Cada familia marcada como verdadera lleva al menos una señal con sus solicitudes citadas.
    """
    app = d["app_id"].to_numpy()
    senales: list[dict] = []
    por_valor: dict = defaultdict(set)
    for i, j, t, v, _w in caso.aristas:
        por_valor[(t, v)].update((i, j))
    for n, ((t, v), pos) in enumerate(sorted(por_valor.items(), key=lambda kv: (kv[0][0], -len(kv[1])))):
        senales.append(dict(id=f"R{n}", familia="relacional", tipo=t, valor=v, pos=sorted(pos),
                            valor_visible=_mascara(t, v), refs=[str(app[p]) for p in sorted(pos)],
                            texto=f"{len(pos)} solicitudes comparten {LEGIBLE[t]} ({_mascara(t, v)})."))
    if caso.tipo == "asesor":
        n_w, mu, z = asesor_volumen(d, corte, cfg_asesor, caso.asesor)
        senales.append(dict(id="O0", familia="relacional", tipo="asesor_anomalo", valor=caso.asesor, pos=sorted(caso.apps),
                            valor_visible=str(caso.asesor), refs=[str(app[p]) for p in sorted(caso.apps)],
                            numeros=dict(n_ventana=n_w, esperado=round(mu, 3), z=round(z, 3)),
                            texto=(f"El asesor {caso.asesor} recibió {n_w} solicitudes en los últimos {cfg_asesor['ventana_dias']} días "
                                   f"(esperado ≈ {mu:.1f} según su propia historia; z={z:.1f}); "
                                   f"{len(caso.apps)} de ellas con marcas de comportamiento.")))
    sub = d.iloc[sorted(caso.apps)]
    n = len(sub)
    cond = [
        ("fallo_dom", sub["fallo_dom"].to_numpy() == 1, "con domicilio NO verificado"),
        ("noche", sub["noche"].to_numpy() == 1, "ingresadas fuera de horario"),
        ("ratio_alto", sub["z_r"].to_numpy() > 1.0, "con monto alto respecto del ingreso típico del rubro"),
        ("llenado_rapido", sub["z_t"].to_numpy() < -1.0, "llenadas más rápido de lo habitual"),
    ]
    for nombre, mascara, desc in cond:
        k = int(mascara.sum())
        if k >= max(2, int(np.ceil(0.4 * n))):
            refs = [str(x) for x in sub["app_id"].to_numpy()[mascara]]
            senales.append(dict(id=f"C_{nombre}", familia="conductual", tipo=nombre, valor=None,
                                pos=[int(p) for p in sub.index.to_numpy()[mascara]], valor_visible="", refs=refs,
                                texto=f"{k} de {n} solicitudes {desc}."))
    if fam["fam_conductual"]:  # la puerta usó el compuesto medio: se muestra con sus cifras, verificables
        nums = _agregado(sub)
        senales.append(dict(id="C_agregado", familia="conductual", tipo="agregado", valor=None,
                            pos=[int(p) for p in sub.index.to_numpy()], valor_visible="", numeros=nums,
                            refs=[str(x) for x in sub["app_id"]],
                            texto=(f"Promedio de las {n} solicitudes: z del tiempo de llenado {nums['z_tiempo']:+.2f}, "
                                   f"z de monto/ingreso {nums['z_ratio']:+.2f}; {nums['fallo_dom']} con domicilio no verificado; "
                                   f"{nums['noche']} fuera de horario.")))
    tipos_rel = sorted({s["tipo"] for s in senales if s["familia"] == "relacional" and s["tipo"] in TIPOS_VERIFICABLES})
    return dict(
        caso_id=caso.caso_id, tipo_caso=caso.tipo, n_solicitudes=n, score=float(score),
        familias=dict(relacional=bool(fam["fam_relacional"]), conductual=bool(fam["fam_conductual"])),
        solicitudes=[str(x) for x in sub["app_id"]], senales=senales,
        posibles_explicaciones_legitimas=[EXPLICACIONES_LEGITIMAS[t] for t in tipos_rel],
        patron=caso.tipo + "|" + "+".join(tipos_rel),
        recomendacion="Merece revisión por un especialista. Verificar los datos señalados antes de cualquier decisión sobre los clientes.",
        decision_automatica=False,
    )


def puede_alertar(exp: dict) -> bool:
    return exp["familias"]["relacional"] and exp["familias"]["conductual"]


def resumen(exp: dict) -> str:
    """Resumen determinista (sin LLM): lista las señales tal cual, sin adjetivos ni veredictos."""
    lineas = [f"El caso {exp['caso_id']} ({exp['n_solicitudes']} solicitudes) merece revisión."]
    lineas += [f"- {s['texto']}" for s in exp["senales"]]
    if exp["posibles_explicaciones_legitimas"]:
        lineas.append("Posibles explicaciones legítimas: " + " ".join(exp["posibles_explicaciones_legitimas"]))
    lineas.append(exp["recomendacion"])
    return "\n".join(lineas)


def _cerca(a: float, b: float, tol: float = 0.011) -> bool:
    return abs(float(a) - float(b)) <= tol


def _verificar_agregado(s: dict, pos: list[int], d: pd.DataFrame) -> list[str]:
    nums, real = s.get("numeros") or {}, _agregado(d.iloc[pos])
    malas = [k for k in ("z_tiempo", "z_ratio") if not _cerca(nums.get(k, 1e9), real[k])]
    malas += [k for k in ("fallo_dom", "noche", "n") if nums.get(k) != real[k]]
    return [f"{s['id']}: cifra(s) no coinciden con los datos: {malas}"] if malas else []


def _verificar_asesor(s: dict, pos: list[int], d: pd.DataFrame, corte: int | None, cfg: dict | None) -> list[str]:
    fallas = []
    sub = d.iloc[pos]
    if not (sub["asesor_id"] == s["valor"]).all():
        fallas.append(f"{s['id']}: alguna solicitud citada no es del asesor afirmado")
    if not (sub["marca"] == 1).all():
        fallas.append(f"{s['id']}: alguna solicitud citada no tiene marca de comportamiento")
    if corte is None or cfg is None:
        fallas.append(f"{s['id']}: no se puede recalcular el volumen sin corte y configuración")
        return fallas
    n_w, mu, z = asesor_volumen(d, corte, cfg, s["valor"])
    nums = s.get("numeros") or {}
    if nums.get("n_ventana") != n_w or not _cerca(nums.get("esperado", 1e9), mu) or not _cerca(nums.get("z", 1e9), z):
        fallas.append(f"{s['id']}: el volumen afirmado no coincide con el recalculado")
    return fallas


def verificar(exp: dict, d: pd.DataFrame, corte: int | None = None, cfg_asesor: dict | None = None) -> list[str]:
    """Recalcula cada afirmación con los datos. Devuelve la lista de fallas (vacía = expediente válido)."""
    fallas: list[str] = []
    index = {a: i for i, a in enumerate(d["app_id"].to_numpy())}
    caso_apps = set(exp["solicitudes"])
    if exp["decision_automatica"]:
        fallas.append("el expediente declara una decisión automática")
    if not puede_alertar(exp):
        fallas.append("alerta con menos de dos familias de señal")
    for familia, activa in (("relacional", exp["familias"]["relacional"]), ("conductual", exp["familias"]["conductual"])):
        if activa and not any(s["familia"] == familia for s in exp["senales"]):
            fallas.append(f"la familia {familia} está marcada pero el expediente no trae ninguna señal de esa familia")
    texto = resumen(exp).lower()
    fallas += [f"palabra prohibida en el resumen: {p}" for p in PALABRAS_PROHIBIDAS if re.search(p, texto)]
    for s in exp["senales"]:
        if not s["refs"] or not set(s["refs"]) <= caso_apps:
            fallas.append(f"{s['id']}: refs vacías o fuera del caso")
            continue
        pos = [index.get(a) for a in s["refs"]]
        if None in pos:
            fallas.append(f"{s['id']}: app_id inexistente")
            continue
        if s["tipo"] == "asesor_anomalo":
            fallas += _verificar_asesor(s, pos, d, corte, cfg_asesor)
            continue
        if s["tipo"] == "agregado":
            fallas += _verificar_agregado(s, pos, d)
            continue
        if s["familia"] == "relacional" and s["tipo"] in TIPOS_VERIFICABLES:
            malas = [a for a, p in zip(s["refs"], pos) if not _pertenece(d, p, s["tipo"], s["valor"])]
            if malas:
                fallas.append(f"{s['id']}: {len(malas)} solicitud(es) no comparten el valor afirmado")
        elif s["familia"] == "conductual":
            ok = {
                "fallo_dom": lambda p: d["fallo_dom"].iat[p] == 1,
                "noche": lambda p: d["noche"].iat[p] == 1,
                "ratio_alto": lambda p: d["z_r"].iat[p] > 1.0,
                "llenado_rapido": lambda p: d["z_t"].iat[p] < -1.0,
            }.get(s["tipo"])
            if ok is None or not all(ok(p) for p in pos):
                fallas.append(f"{s['id']}: alguna solicitud citada no cumple la condición")
    return fallas

"""Generador sintético RIE-02: mundo legítimo primero, anillos de fraude después.

Principios (ver README):
- Los grupos legítimos (familias, mercados, cibercafés) comparten atributos a propósito.
- Los anillos toman todos sus atributos NO anillo de las mismas distribuciones legítimas.
- Los identificadores se asignan DESPUÉS de barajar, para que ni el id ni el orden filtren la etiqueta.
- Las etiquetas viven en una tabla aparte (`etiquetas`); el detector nunca la lee.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

TIPOLOGIAS = (
    "identidad_sintetica",
    "referencias_cruzadas",
    "prestanombres",
    "colusion_asesor",
    "sin_atributos",
)
N_AGENCIAS = 8
URBANIZACIONES = (
    "los jardines", "santa maria", "el porvenir", "las palmeras", "san andres", "la merced",
    "buenos aires", "alto trujillo", "huanchaco", "la esperanza", "victor larco", "el milagro",
)
# Desplazamiento de la conducta (en desviaciones estándar) por tipología.
# t: menos tiempo de llenado, r: mayor ratio monto/ingreso, noche: prob. fuera de horario,
# red: prob. de monto redondo, v: prob. extra de domicilio no verificado.
DELTAS = {
    "identidad_sintetica": dict(t=0.8, r=0.6, noche=0.15, red=0.30, v=0.08),
    "referencias_cruzadas": dict(t=0.6, r=0.5, noche=0.10, red=0.20, v=0.05),
    "prestanombres": dict(t=0.5, r=0.8, noche=0.05, red=0.30, v=0.05),
    "colusion_asesor": dict(t=1.0, r=1.0, noche=0.02, red=0.20, v=0.45),
    "sin_atributos": dict(t=0.15, r=0.15, noche=0.25, red=0.35, v=0.03),
}
TAMANO = {  # (min, max) de solicitudes por anillo; mínimo 3 para solapar con familias (2-5)
    "identidad_sintetica": (3, 8), "referencias_cruzadas": (3, 10), "prestanombres": (3, 8),
    "colusion_asesor": (8, 14), "sin_atributos": (3, 8),
}
TAMANO_CHICO = {  # anillos del tamaño de una familia, para el barrido de parámetros
    "identidad_sintetica": (3, 5), "referencias_cruzadas": (3, 5), "prestanombres": (3, 5),
    "colusion_asesor": (6, 8), "sin_atributos": (3, 5),
}
VENTANA = {  # (min, max) de días en que llegan las solicitudes del anillo
    "identidad_sintetica": (3, 10), "referencias_cruzadas": (5, 14), "prestanombres": (5, 14),
    "colusion_asesor": (14, 21), "sin_atributos": (3, 7),
}


@dataclass(frozen=True)
class Params:
    seed: int
    n_apps_legit: int = 12000
    dias: int = 180
    anillos_por_tipologia: int = 8
    mult_comparticion: float = 1.0  # escala la compartición legítima (familias, teléfonos, refs)
    sutileza: float = 0.0  # 0 = señal conductual completa; 1 = sin señal conductual
    anillos_chicos: bool = False  # anillos del tamaño de una familia (quita el atajo del tamaño)
    n_asesores: int = 60
    n_zonas: int = 12

    def con(self, **cambios) -> "Params":
        return replace(self, **cambios)


@dataclass
class Mundo:
    apps: pd.DataFrame  # observable por el detector
    etiquetas: pd.DataFrame  # oculta: app_id, anillo_id, tipologia, grupo_id, grupo_tipo
    params: Params


class _Recursos:
    """Reparte teléfonos, dispositivos, direcciones y claves de persona sin repetir."""

    def __init__(self, rng: np.random.Generator, n_zonas: int):
        self.rng, self.n_zonas = rng, n_zonas
        self._tel: set[str] = set()
        self._dir: set[tuple] = set()
        self._disp: set[str] = set()
        self._n = 0  # contador de claves (personas, negocios)

    def clave(self) -> int:
        self._n += 1
        return self._n

    def telefono(self) -> str:
        while True:
            t = "9" + "".join(map(str, self.rng.integers(0, 10, 8)))
            if t not in self._tel:
                self._tel.add(t)
                return t

    def dispositivo(self) -> str:
        while True:
            d = f"D{int(self.rng.integers(0, 2**40)):010x}"
            if d not in self._disp:
                self._disp.add(d)
                return d

    def direccion(self, zona: int) -> tuple:
        while True:
            base = (URBANIZACIONES[zona % len(URBANIZACIONES)],
                    chr(65 + int(self.rng.integers(0, 26))), int(self.rng.integers(1, 80)))
            if base not in self._dir:
                self._dir.add(base)
                return base


def _render_dir(base: tuple, rng: np.random.Generator) -> str:
    urb, mz, lt = base
    estilo = int(rng.integers(0, 4))
    if estilo == 0:
        return f"Mz. {mz} Lt. {lt} Urb. {urb.title()}"
    if estilo == 1:
        return f"MZ {mz} LT {lt} URB {urb.upper()}"
    if estilo == 2:
        return f"Manzana {mz} Lote {lt} Urbanización {urb.title()}"
    return f"MZ.{mz} LT.{lt} URB. {urb.upper()}"


def _render_tel(t: str | None, rng: np.random.Generator) -> str:
    if t is None:
        return ""
    estilo = int(rng.integers(0, 4))
    if estilo == 0:
        return f"+51 {t[:3]} {t[3:6]} {t[6:]}"
    if estilo == 1:
        return t
    if estilo == 2:
        return f"{t[:3]}-{t[3:6]}-{t[6:]}"
    return f"(51) {t}"


def _conducta(rng: np.random.Generator, n: int, delta: dict | None, sutileza: float) -> dict:
    """Variables de comportamiento de n solicitudes; delta=None => legítimas."""
    d = {k: v * (1 - sutileza) for k, v in (delta or dict(t=0, r=0, noche=0, red=0, v=0)).items()}
    tiempo = np.exp(np.log(600.0) + 0.5 * rng.normal(-d["t"], 1.0, n))
    ratio = np.clip(1.0 + 0.25 * rng.normal(d["r"], 1.0, n), 0.3, 3.0)
    noche = rng.random(n) < (0.08 + d["noche"])
    hora_dia = np.clip(np.round(rng.normal(14, 3, n)), 8, 19).astype(int)
    hora_noche = np.where(rng.random(n) < 0.5, rng.integers(20, 24, n), rng.integers(0, 7, n))
    hora = np.where(noche, hora_noche, hora_dia)
    monto = np.round(np.exp(rng.normal(np.log(6000), 0.6, n)) / 50) * 50
    redondo = rng.random(n) < (0.20 + d["red"])
    monto = np.where(redondo, np.round(monto / 500) * 500, monto).clip(min=500)
    verif = (rng.random(n) >= (0.03 + d["v"])).astype(int)
    return dict(tiempo_llenado_seg=tiempo, hora=hora, ratio_monto=ratio, monto=monto, verif_domicilio_ok=verif)


class _Constructor:
    def __init__(self, p: Params):
        self.p = p
        self.rng = np.random.default_rng(p.seed)
        self.rec = _Recursos(self.rng, p.n_zonas)
        self.filas: list[dict] = []
        self._grupo = 0
        self._anillo = 0
        n_pop = max(10, p.n_apps_legit // 40)
        self.refs_populares = [self.rec.clave() for _ in range(n_pop)]
        self.asesores_de = {a: [x for x in range(p.n_asesores) if x % N_AGENCIAS == a] for a in range(N_AGENCIAS)}

    # ---------- utilidades ----------
    def _asesor(self, zona: int) -> int:
        return int(self.rng.choice(self.asesores_de[zona % N_AGENCIAS]))

    def _ref_externa(self) -> int:
        if self.rng.random() < 0.03:
            return int(self.rng.choice(self.refs_populares))
        return self.rec.clave()

    def _agregar(self, **campos) -> None:
        self.filas.append(campos)

    def _fila_base(self, zona: int, dia: int, cond: dict, i: int, **sobre) -> dict:
        base = dict(
            persona=self.rec.clave(), tel=self.rec.telefono(), disp=self.rec.dispositivo(),
            dir_h=self.rec.direccion(zona), dir_n=None, negocio=self.rec.clave(),
            ref1=self._ref_externa(), ref2=self._ref_externa(), asesor=self._asesor(zona),
            zona=zona, dia=dia, anillo=-1, tipologia="legit", grupo=-1, grupo_tipo="ninguno",
            **{k: v[i] for k, v in cond.items()},
        )
        base.update(sobre)
        if self.rng.random() < 0.03:
            base["tel"] = None  # dato faltante
        return base

    def _dia(self) -> int:
        return int(self.rng.integers(0, self.p.dias))

    # ---------- mundo legítimo ----------
    def legitimos(self) -> None:
        p, rng, m = self.p, self.rng, self.p.mult_comparticion
        n = p.n_apps_legit
        n_fam = int(n * min(0.6, 0.25 * m))
        n_merc, n_ciber = int(n * 0.15), int(n * 0.05)
        n_ind = max(0, n - n_fam - n_merc - n_ciber)
        for _ in range(n_ind):
            zona = int(rng.integers(0, p.n_zonas))
            self._agregar(**self._fila_base(zona, self._dia(), _conducta(rng, 1, None, 0), 0))
        hechos = 0
        while hechos < n_fam:
            hechos += self._familia(min(int(rng.choice([2, 3, 4, 5], p=[.35, .35, .2, .1])), n_fam - hechos + 1))
        hechos = 0
        while hechos < n_merc:
            hechos += self._mercado(int(rng.integers(6, 81)))
        hechos = 0
        while hechos < n_ciber:
            hechos += self._cibercafe(int(rng.integers(30, 101)))

    def _familia(self, k: int) -> int:
        rng, m = self.rng, self.p.mult_comparticion
        self._grupo += 1
        zona = int(rng.integers(0, self.p.n_zonas))
        casa, tel_f, disp_f = self.rec.direccion(zona), self.rec.telefono(), self.rec.dispositivo()
        asesor_f = self._asesor(zona)
        negocio_f = self.rec.clave()
        cond = _conducta(rng, k, None, 0)
        miembros = [self.rec.clave() for _ in range(k)]
        for i in range(k):
            comparte_tel = rng.random() < min(0.9, 0.35 * m)
            comparte_disp = rng.random() < min(0.9, 0.30 * m)
            ref1 = miembros[(i + 1) % k] if rng.random() < min(0.9, 0.40 * m) else self._ref_externa()
            self._agregar(**self._fila_base(
                zona, self._dia(), cond, i, persona=miembros[i], dir_h=casa,
                tel=tel_f if comparte_tel else self.rec.telefono(),
                disp=disp_f if comparte_disp else self.rec.dispositivo(),
                negocio=negocio_f if rng.random() < 0.15 else self.rec.clave(),
                ref1=ref1, asesor=asesor_f if rng.random() < 0.5 else self._asesor(zona),
                grupo=self._grupo, grupo_tipo="familia"))
        return k

    def _mercado(self, k: int) -> int:
        rng = self.rng
        self._grupo += 1
        zona = int(rng.integers(0, self.p.n_zonas))
        puesto_dir = self.rec.direccion(zona)
        asesores = [self._asesor(zona), self._asesor(zona)]
        cond = _conducta(rng, k, None, 0)
        miembros = [self.rec.clave() for _ in range(k)]
        tel_pareja: dict[int, str] = {}
        for i in range(k):
            tel = self.rec.telefono()
            if i > 0 and rng.random() < 0.10 * self.p.mult_comparticion:
                tel = tel_pareja.get(i - 1, tel)  # puesto de la misma familia
            tel_pareja[i] = tel
            ref1 = miembros[int(rng.integers(0, k))] if rng.random() < 0.05 else self._ref_externa()
            self._agregar(**self._fila_base(
                zona, self._dia(), cond, i, persona=miembros[i], tel=tel, dir_n=puesto_dir,
                ref1=ref1, asesor=int(rng.choice(asesores)), grupo=self._grupo, grupo_tipo="mercado"))
        return k

    def _cibercafe(self, k: int) -> int:
        rng = self.rng
        self._grupo += 1
        zona = int(rng.integers(0, self.p.n_zonas))
        disp = self.rec.dispositivo()
        cond = _conducta(rng, k, None, 0)
        for i in range(k):
            self._agregar(**self._fila_base(zona, self._dia(), cond, i, disp=disp,
                                            grupo=self._grupo, grupo_tipo="ciber"))
        return k

    # ---------- anillos ----------
    def anillos(self) -> None:
        for tip in TIPOLOGIAS:
            for _ in range(self.p.anillos_por_tipologia):
                self._anillo_de(tip)

    def _anillo_de(self, tip: str) -> None:
        p, rng = self.p, self.rng
        self._anillo += 1
        lo, hi = (TAMANO_CHICO if p.anillos_chicos else TAMANO)[tip]
        k = int(rng.integers(lo, hi + 1))
        w = int(rng.integers(VENTANA[tip][0], VENTANA[tip][1] + 1))
        inicio = int(rng.integers(0, p.dias - w))
        zona_c = int(rng.integers(0, p.n_zonas))
        cond = _conducta(rng, k, DELTAS[tip], p.sutileza)
        miembros = [self.rec.clave() for _ in range(k)]
        comun: dict = {}
        if tip == "identidad_sintetica":
            comun = dict(tel=self.rec.telefono(), disp=self.rec.dispositivo(), dir_h=self.rec.direccion(zona_c))
        elif tip == "prestanombres":
            comun = dict(disp=self.rec.dispositivo(), negocio=self.rec.clave(), asesor=self._asesor(zona_c))
        elif tip == "colusion_asesor":
            comun = dict(asesor=self._asesor(zona_c))
        for i in range(k):
            zona = zona_c if tip in ("identidad_sintetica", "colusion_asesor") else int(rng.integers(0, p.n_zonas))
            sobre: dict = dict(persona=miembros[i], anillo=self._anillo, tipologia=tip)
            if tip == "identidad_sintetica":
                sobre["tel"] = comun["tel"]
                if rng.random() < 0.7:
                    sobre["disp"] = comun["disp"]
                if rng.random() < 0.5:
                    base = comun["dir_h"]
                    if rng.random() < 0.3:  # variante no normalizable: lote distinto
                        base = (base[0], base[1], base[2] + int(rng.choice([-1, 1])))
                    sobre["dir_h"] = base
            elif tip == "referencias_cruzadas":
                sobre["ref1"], sobre["ref2"] = miembros[(i + 1) % k], miembros[(i - 1) % k]
            elif tip == "prestanombres":
                sobre.update(disp=comun["disp"], negocio=comun["negocio"], asesor=comun["asesor"])
            elif tip == "colusion_asesor":
                sobre["asesor"] = comun["asesor"]
            self._agregar(**self._fila_base(zona, inicio + int(rng.integers(0, w + 1)), cond, i, **sobre))

    # ---------- salida ----------
    def construir(self) -> Mundo:
        self.legitimos()
        self.anillos()
        rng = self.rng
        df = pd.DataFrame(self.filas)
        df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)  # barajar ANTES de asignar ids
        df.insert(0, "app_id", [f"A{i:06d}" for i in range(len(df))])

        def mapa(valores, prefijo, ancho):
            unicos = pd.unique(valores.dropna())
            codigos = rng.permutation(len(unicos) * 3)[: len(unicos)]
            return dict(zip(unicos, [f"{prefijo}{int(c):0{ancho}d}" for c in codigos]))

        claves = pd.concat([df["persona"], df["ref1"], df["ref2"]])
        m_per = mapa(claves, "P", 7)
        m_neg = mapa(df["negocio"], "N", 7)
        m_ase = mapa(df["asesor"], "S", 3)
        apps = pd.DataFrame({
            "app_id": df["app_id"], "dia": df["dia"].astype(int),
            "persona_id": df["persona"].map(m_per),
            "telefono_raw": [_render_tel(t if isinstance(t, str) else None, rng) for t in df["tel"]],
            "dispositivo": df["disp"],
            "direccion_hogar_raw": [_render_dir(b, rng) for b in df["dir_h"]],
            "direccion_negocio_raw": [_render_dir(b, rng) if isinstance(b, tuple) else "" for b in df["dir_n"]],
            "negocio_id": df["negocio"].map(m_neg),
            "ref1_id": df["ref1"].map(m_per), "ref2_id": df["ref2"].map(m_per),
            "asesor_id": df["asesor"].map(m_ase), "agencia_id": ("G" + (df["asesor"] % N_AGENCIAS).astype(str)),
            "zona": df["zona"].astype(int),
            "tiempo_llenado_seg": df["tiempo_llenado_seg"].round(1), "hora": df["hora"].astype(int),
            "ratio_monto": df["ratio_monto"].round(3), "monto": df["monto"].astype(float),
            "verif_domicilio_ok": df["verif_domicilio_ok"].astype(int),
        })
        etiquetas = pd.DataFrame({
            "app_id": df["app_id"], "anillo_id": df["anillo"].astype(int), "tipologia": df["tipologia"],
            "grupo_id": df["grupo"].astype(int), "grupo_tipo": df["grupo_tipo"],
        })
        return Mundo(apps=apps, etiquetas=etiquetas, params=self.p)


def generar(params: Params) -> Mundo:
    return _Constructor(params).construir()


def guardar(mundo: Mundo, carpeta: str) -> None:
    import os
    os.makedirs(carpeta, exist_ok=True)
    mundo.apps.to_csv(os.path.join(carpeta, "apps.csv"), index=False)
    mundo.etiquetas.to_csv(os.path.join(carpeta, "etiquetas.csv"), index=False)

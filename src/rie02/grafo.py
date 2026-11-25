"""Grafo de solicitudes: aristas por atributo compartido, ponderadas, con tope de concentradores.

Unidad de la cola = CASO (grupo de solicitudes), no solicitud individual.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .normalizar import normalizar_direccion, normalizar_telefono

COLUMNA_DE = {
    "telefono": "tel", "dispositivo": "dispositivo", "direccion_hogar": "dir_h",
    "direccion_negocio": "dir_n", "negocio": "negocio_id",
}
APROX = {"telefono_aprox": "tel", "direccion_hogar_aprox": "dir_h", "direccion_negocio_aprox": "dir_n"}  # E5
TIPOS = tuple(COLUMNA_DE) + ("referencia",) + tuple(APROX)
LARGO_MIN_APROX = 6  # textos más cortos darían coincidencias espurias


def claves_aprox(s: str) -> set[str]:
    """El texto y el texto con un carácter borrado: dos textos casi iguales comparten alguna clave."""
    return {s} | {s[:i] + s[i + 1:] for i in range(len(s))}


@dataclass
class Caso:
    caso_id: str
    tipo: str  # "relacional" | "asesor"
    apps: list[int]  # posiciones (0..n-1) en la tabla preparada
    aristas: list[tuple] = field(default_factory=list)  # (i, j, tipo, valor, peso)
    asesor: str | None = None


def preparar(apps: pd.DataFrame) -> pd.DataFrame:
    """Copia con claves normalizadas; las posiciones 0..n-1 son los nodos del grafo."""
    d = apps.reset_index(drop=True).copy()
    d["tel"] = d["telefono_raw"].map(normalizar_telefono)
    d["dir_h"] = d["direccion_hogar_raw"].map(normalizar_direccion)
    d["dir_n"] = d["direccion_negocio_raw"].map(normalizar_direccion)
    return d


def _a_distancia_uno(a: str, b: str) -> bool:
    """Distancia de edición exactamente 1 (sustitución, inserción o borrado). Las claves de borrado solo agrupan candidatos."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    corto, largo = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(corto) and corto[i] == largo[i]:
        i += 1
    return corto[i:] == largo[i + 1:]


def _grupos_por_tipo(d: pd.DataFrame, tipos) -> dict[str, dict]:
    salida: dict[str, dict] = {}
    for t in tipos:
        if t == "referencia":
            g: dict[str, set] = defaultdict(set)
            for col in ("ref1_id", "ref2_id", "persona_id"):  # persona_id: "A cita a la persona de B"
                for pos, v in enumerate(d[col].to_numpy()):
                    if isinstance(v, str):
                        g[v].add(pos)
            salida[t] = {k: sorted(v) for k, v in g.items()}
        elif t in APROX:
            ga: dict[str, list] = defaultdict(list)
            for pos, s in enumerate(d[APROX[t]].to_numpy()):
                if isinstance(s, str) and len(s) >= LARGO_MIN_APROX:
                    for clave in sorted(claves_aprox(s)):  # sorted: el orden de un set depende de PYTHONHASHSEED
                        ga[clave].append(pos)
            salida[t] = ga
        else:
            salida[t] = {k: v.tolist() for k, v in d.groupby(COLUMNA_DE[t], sort=False).indices.items()}
    return salida


def aristas(d: pd.DataFrame, pesos: dict, tope: int | None, tipos=TIPOS):
    """Devuelve ({(i,j): [(tipo, valor, peso)]}, {tipo: n_valores_concentradores_excluidos})."""
    pares: dict[tuple, list] = defaultdict(list)
    concentradores = {t: 0 for t in tipos}
    for t, grupos in _grupos_por_tipo(d, tipos).items():
        textos = d[APROX[t]].to_numpy() if t in APROX else None
        for valor, miembros in grupos.items():
            k = len(miembros)
            if k < 2:
                continue
            if tope is not None and k > tope:
                concentradores[t] += 1
                continue
            w = pesos[t] / math.sqrt(k - 1)
            for i, j in combinations(sorted(miembros), 2):
                if textos is not None and (not _a_distancia_uno(textos[i], textos[j])  # igual: lo cubre el tipo exacto
                                           or any(x[0] == t for x in pares.get((i, j), ()))):  # una arista por par y tipo
                    continue
                pares[(i, j)].append((t, valor, w))
    return pares, concentradores


def _componentes(n: int, pares) -> np.ndarray:
    if not pares:
        return np.arange(n)
    ij = np.array(list(pares.keys()))
    m = coo_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    return connected_components(m, directed=False)[1]


def _partir(g: nx.Graph, limite: int, semilla: int) -> list[list[int]]:
    """Louvain recursivo: ninguna comunidad supera `limite` si se puede partir (resolución creciente)."""
    if g.number_of_nodes() <= limite:
        return [sorted(g)]
    for res in (1.0, 2.0, 4.0, 8.0, 16.0):
        coms = nx.community.louvain_communities(g, weight="w", resolution=res, seed=semilla)
        if len(coms) > 1:  # cada llamada reduce el tamaño, así que la recursión termina
            return [x for c in coms for x in _partir(g.subgraph(c), limite, semilla)]
    return [sorted(g)]  # ponytail: no se pudo partir (grafo casi completo); queda un caso grande


def casos_relacionales(d: pd.DataFrame, cfg_grafo: dict, tipos=TIPOS, tope="cfg", semilla: int = 0):
    """Casos = componentes conexos (>=2 solicitudes); los muy grandes se parten con Louvain."""
    tope = cfg_grafo["tope_compartido"] if tope == "cfg" else tope
    pares, concentradores = aristas(d, cfg_grafo["pesos"], tope, tipos)
    etiqueta = _componentes(len(d), pares)
    miembros: dict[int, list] = defaultdict(list)
    for pos, c in enumerate(etiqueta):
        miembros[int(c)].append(pos)
    limite = cfg_grafo["dividir_componentes_mayores_a"]
    grupos: list[list[int]] = []
    for nodos in miembros.values():
        if len(nodos) < 2:
            continue
        if len(nodos) <= limite:
            grupos.append(nodos)
            continue
        g = nx.Graph()
        g.add_nodes_from(nodos)
        en = set(nodos)
        for (i, j), lst in pares.items():
            if i in en and j in en:
                # redondeo: sin él, networkx 3.7 puede ciclar para siempre por empates en coma flotante
                g.add_edge(i, j, w=round(sum(x[2] for x in lst), 6))
        for com in _partir(g, limite, semilla):
            if len(com) >= 2:
                grupos.append(com)
    dueno = {}
    for gi, nodos in enumerate(grupos):
        for pos in nodos:
            dueno[pos] = gi
    aristas_de: dict[int, list] = defaultdict(list)
    for (i, j), lst in pares.items():
        if i in dueno and dueno.get(j) == dueno[i]:
            aristas_de[dueno[i]].extend((i, j, t, v, w) for t, v, w in lst)
    casos = [Caso(f"R{gi:05d}", "relacional", nodos, aristas_de.get(gi, [])) for gi, nodos in enumerate(grupos)]
    return casos, concentradores

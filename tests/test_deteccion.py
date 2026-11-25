import numpy as np
import pandas as pd

from rie02.corrida import instantanea
from rie02.generador import Params, generar
from rie02.grafo import Caso, aristas, casos_relacionales, preparar
from rie02.modelos import Puerta, cola, presupuesto
from rie02.rasgos import etiquetar


def test_peso_decrece_con_el_tamano_del_grupo():
    d = pd.DataFrame({"tel": ["A"] * 2 + ["B"] * 5 + ["C"] * 12})
    pares, _ = aristas(d, {"telefono": 1.0}, tope=12, tipos=("telefono",))
    w2, w5, w12 = pares[(0, 1)][0][2], pares[(2, 3)][0][2], pares[(7, 8)][0][2]
    assert w2 > w5 > w12 > 0
    assert w2 == 1.0 and abs(w5 - 0.5) < 1e-9


def test_tope_excluye_concentradores():
    d = pd.DataFrame({"tel": ["X"] * 13 + ["Y"] * 3})
    pares, conc = aristas(d, {"telefono": 1.0}, tope=12, tipos=("telefono",))
    assert conc["telefono"] == 1
    assert all(i >= 13 and j >= 13 for i, j in pares)  # solo el grupo Y (3 solicitudes)


def test_sin_tope_el_concentrador_si_conecta():
    d = pd.DataFrame({"tel": ["X"] * 13})
    pares, conc = aristas(d, {"telefono": 1.0}, tope=None, tipos=("telefono",))
    assert conc["telefono"] == 0 and len(pares) == 13 * 12 // 2


def test_mundo_legitimo_no_forma_componentes_gigantes(cfg):
    m = generar(Params(seed=9, n_apps_legit=2500, anillos_por_tipologia=0))
    casos, conc = casos_relacionales(preparar(m.apps), cfg["grafo"])
    assert max(len(c.apps) for c in casos) <= cfg["grafo"]["dividir_componentes_mayores_a"]
    assert conc["dispositivo"] > 0 and conc["direccion_negocio"] > 0  # cibercafés y mercados quedaron como concentradores


def test_instantanea_no_ve_el_futuro(mundo_chico, cfg):
    s = instantanea(mundo_chico, 60, cfg)
    assert s.d["dia"].max() <= 60 and len(s.d) < len(mundo_chico.apps)


def test_etiqueta_de_caso_por_pureza(mundo_chico, cfg):
    d = preparar(mundo_chico.apps)
    e = mundo_chico.etiquetas.set_index("app_id").loc[d["app_id"]]
    anillo = e["anillo_id"].to_numpy()
    r = anillo[anillo >= 0][0]
    en_anillo = np.flatnonzero(anillo == r).tolist()
    legit = np.flatnonzero(anillo == -1)[:6].tolist()
    mezcla = en_anillo[:3] + legit[:4]  # 3 del anillo (cumple el mínimo) pero pureza 3/7 < 0.5
    L = etiquetar([Caso("puro", "relacional", en_anillo), Caso("mezcla", "relacional", mezcla)],
                  d, mundo_chico.etiquetas, cfg["etiqueta_caso"])
    assert L["y"].tolist() == [1, 0] and L["anillo_dom"].iat[0] == r
    assert L["anillo_n"].iat[1] == 3  # el 0 viene de la pureza, no de tener pocas solicitudes


def test_puerta_exige_dos_familias(cfg):
    X = pd.DataFrame({"es_asesor": [0] * 100, "peso_medio": np.linspace(0, 2, 100),
                      "compuesto": np.linspace(-1, 3, 100), "asesor_z": 0.0})
    p = Puerta(cfg["puerta"]).ajustar(X)
    assert not p.pasa(X.assign(compuesto=-5.0)).any()  # solo relacional
    assert not p.pasa(X.assign(peso_medio=-5.0)).any()  # solo conductual
    assert p.pasa(X.assign(peso_medio=9.0, compuesto=9.0)).all()
    asesor = X.assign(es_asesor=1, asesor_z=9.0, compuesto=9.0, peso_medio=-5.0)
    assert p.pasa(asesor).all()  # en casos de asesor la familia relacional es su z propio
    assert not p.pasa(asesor.assign(asesor_z=0.0)).any()


def test_cola_respeta_puerta_solape_y_presupuesto():
    casos = [Caso("c0", "relacional", [0, 1, 2, 3]), Caso("c1", "relacional", [0, 1, 2]),
             Caso("c2", "relacional", [10, 11]), Caso("c3", "relacional", [20, 21]),
             Caso("c4", "relacional", [30, 31])]
    score = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
    pasa = np.array([True, True, False, True, True])
    assert cola(casos, score, pasa, k=5, solape=0.8) == [0, 3, 4]  # c1 duplica a c0; c2 no pasa la puerta
    assert cola(casos, score, pasa, k=2, solape=0.8) == [0, 3]


def test_ciego_ida_y_vuelta_y_validacion(mundo_chico, tmp_path):
    import pytest

    from rie02.ciego import cargar_ciego
    from rie02.generador import guardar
    guardar(mundo_chico, str(tmp_path))
    m = cargar_ciego(tmp_path)
    assert len(m.apps) == len(mundo_chico.apps) and set(m.etiquetas["app_id"]) == set(mundo_chico.apps["app_id"])
    pd.read_csv(tmp_path / "apps.csv").drop(columns=["monto"]).to_csv(tmp_path / "apps.csv", index=False)
    with pytest.raises(ValueError, match="faltan columnas"):
        cargar_ciego(tmp_path)


def test_metricas_cola_a_mano():
    from rie02.evaluacion import metricas_cola
    et = pd.DataFrame({"app_id": [f"a{i}" for i in range(10)], "anillo_id": [1, 1, 1, 2, 2, 2, -1, -1, -1, -1],
                       "tipologia": ["t1"] * 3 + ["t2"] * 3 + ["legit"] * 4, "grupo_id": [-1] * 6 + [7, 7, 8, 8],
                       "grupo_tipo": ["ninguno"] * 6 + ["familia"] * 4})
    Q = pd.DataFrame({"y": [1, 0, 0], "anillo_dom": [1, -1, -1], "es_grupo_legit": [0, 1, 0], "grupo_dom": [-1, 7, -1],
                      "clave": ["anillo:1", "grupo:7", "caso:x"]})
    m = metricas_cola(Q, et)
    assert abs(m["precision"] - 1 / 3) < 1e-9 and m["recall_total"] == 0.5
    assert m["recall_por_tipologia"] == {"t1": 1.0, "t2": 0.0}
    assert m["fp_grupos_legit"] == 0.5 and abs(m["cola_legit_grupo"] - 1 / 3) < 1e-9


def test_bootstrap_remuestrea_clusteres_no_casos():
    from rie02.evaluacion import boot_precision
    Q = pd.DataFrame({"y": [1, 1, 1, 0], "clave": ["anillo:1"] * 3 + ["caso:x"]})
    assert set(np.round(boot_precision(Q, 2000, 0), 2)) <= {1.0, 0.75, 0.0}  # solo 2 clústeres: 3 resultados posibles


def test_anticipacion_a_mano():
    from rie02.evaluacion import anticipacion
    colas = {45: pd.DataFrame({"y": [0], "anillo_dom": [-1]}), 60: pd.DataFrame({"y": [1], "anillo_dom": [5]})}
    ani = pd.DataFrame({"anillo_id": [5] * 4 + [6] * 3, "tipologia": ["t"] * 7, "dia": [50, 55, 62, 70, 10, 11, 12]})
    r = anticipacion(colas, ani).set_index("anillo_id")
    assert r.loc[5, "corte_deteccion"] == 60 and abs(r.loc[5, "evitables"] - 0.5) < 1e-9 and not r.loc[6, "detectado"]


def test_asesor_volumen_detecta_el_salto_y_no_el_ruido(cfg):
    from rie02.rasgos import asesor_volumen
    rng = np.random.default_rng(0)
    d = pd.concat([pd.DataFrame({"asesor_id": rng.choice(list("ABCDE"), 1000), "dia": rng.integers(0, 150, 1000)}),
                   pd.DataFrame({"asesor_id": ["A"] * 40, "dia": rng.integers(130, 150, 40)})], ignore_index=True)
    n_a, _, z_a = asesor_volumen(d, 149, cfg["caso_asesor"], "A")
    _, _, z_b = asesor_volumen(d, 149, cfg["caso_asesor"], "B")
    assert z_a > 5 and abs(z_b) < 3 and n_a >= 40


def test_calibrar_piso_limita_las_alertas_en_un_mundo_sin_anillos(cfg):
    from rie02.corrida import colas_de, entrenar_sistema
    p = Params(seed=11, n_apps_legit=2500, anillos_por_tipologia=3)
    sis = entrenar_sistema(generar(p), cfg)
    cal = generar(p.con(seed=cfg["semillas"]["calibracion"], anillos_por_tipologia=0))
    snap = instantanea(cal, cfg["corte_final"], cfg)
    colas, _ = colas_de(sis, cal, snap, cfg)
    assert len(colas["lgbm_puerta"]) <= int(cfg["puerta"]["alertas_max_por_1000"] * len(snap.d) / 1000)


def test_ciego_rechaza_tiempo_cero(mundo_chico, tmp_path):
    import pytest

    from rie02.ciego import cargar_ciego
    from rie02.generador import guardar
    guardar(mundo_chico, str(tmp_path))
    a = pd.read_csv(tmp_path / "apps.csv")
    a.loc[0, "tiempo_llenado_seg"] = 0
    a.to_csv(tmp_path / "apps.csv", index=False)
    with pytest.raises(ValueError, match="deben ser > 0"):
        cargar_ciego(tmp_path)


def test_louvain_no_cicla_en_el_componente_gigante_del_ciego(cfg):
    """Regresión: sin redondear pesos, Louvain se colgaba en la instantánea 165 del ciego (networkx 3.7)."""
    import pathlib

    import pytest

    carpeta = pathlib.Path(__file__).resolve().parent.parent / "data" / "ciego"
    if not (carpeta / "apps.csv").exists():
        pytest.skip("sin conjunto ciego")
    apps = pd.read_csv(carpeta / "apps.csv", dtype=str)  # solo apps: no se abren las etiquetas del ciego
    apps = apps[apps["dia"].astype(int) <= 165]
    casos, _ = casos_relacionales(preparar(apps), cfg["grafo"])
    assert max(len(c.apps) for c in casos) <= cfg["grafo"]["dividir_componentes_mayores_a"]


def test_aristas_aproximadas_exigen_distancia_uno_y_una_sola_arista_por_par():
    d = pd.DataFrame({"tel": ["987654321", "987654312", "987654322", "123456789", "234567891"]})
    pares, _ = aristas(d, {"telefono_aprox": 0.5}, tope=12, tipos=("telefono_aprox",))
    assert (0, 1) not in pares  # dos dígitos adyacentes cambiados = distancia 2
    assert len(pares[(0, 2)]) == 1 and len(pares[(1, 2)]) == 1  # un dígito de diferencia, una sola arista
    assert not any(3 in k and 4 in k for k in pares)  # una rotación (distancia 2) no une


def test_casos_no_dependen_del_orden_de_hash_de_python(tmp_path):
    """Regresión: el orden de un set de claves cambiaba el desempate de Louvain entre procesos (PYTHONHASHSEED)."""
    import os
    import pathlib
    import subprocess
    import sys
    guion = ("import pathlib,sys,yaml,hashlib;R=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(R/'src'))\n"
             "from rie02.generador import Params,generar\nfrom rie02.grafo import casos_relacionales,preparar\n"
             "cfg=yaml.safe_load((R/'config'/'preregistro.yaml').read_text(encoding='utf-8'))\n"
             "m=generar(Params(seed=7,n_apps_legit=2500,anillos_por_tipologia=3))\n"
             "c,_=casos_relacionales(preparar(m.apps[m.apps['dia']<=179]),cfg['grafo'])\n"
             "print(hashlib.md5(repr(sorted(tuple(sorted(x.apps)) for x in c)).encode()).hexdigest())\n")
    raiz = pathlib.Path(__file__).resolve().parent.parent
    salidas = {subprocess.run([sys.executable, "-c", guion, str(raiz)], capture_output=True, text=True, timeout=120,
                              env={**os.environ, "PYTHONHASHSEED": s}).stdout.strip() for s in ("1", "2", "3")}
    assert len(salidas) == 1 and "" not in salidas


def test_aristas_aproximadas_unen_textos_casi_iguales_no_iguales_ni_distintos():
    d = pd.DataFrame({"tel": ["987654321", "987654322", "987654321", "123456789", "98765"],
                      "dir_h": ["av grau 101", "av grau 102", "av grau 101", "jr lima 55 b", "av g"]})
    pares, _ = aristas(d, {"telefono_aprox": 0.5, "direccion_hogar_aprox": 0.35}, tope=12,
                       tipos=("telefono_aprox", "direccion_hogar_aprox"))
    tipos = {k: {t for t, _v, _w in v} for k, v in pares.items()}
    assert tipos[(0, 1)] == {"telefono_aprox", "direccion_hogar_aprox"}  # un dígito de diferencia
    assert tipos[(1, 2)] == {"telefono_aprox", "direccion_hogar_aprox"}
    assert (0, 2) not in pares  # iguales: los cubre el tipo exacto, no se duplican
    assert not any(3 in k or 4 in k for k in pares)  # distinto y demasiado corto (largo < 6)


def test_clave_aproximada_es_verificable_por_el_expediente():
    from rie02.expediente import _pertenece
    from rie02.grafo import claves_aprox
    d = pd.DataFrame({"tel": ["987654321", "987654322"], "dir_h": ["av grau 101", "av grau 102"], "dir_n": [None, None]})
    pares, _ = aristas(d, {"telefono_aprox": 0.5}, tope=12, tipos=("telefono_aprox",))
    valor = pares[(0, 1)][0][1]
    assert _pertenece(d, 0, "telefono_aprox", valor) and _pertenece(d, 1, "telefono_aprox", valor)
    assert valor in claves_aprox("987654321") and not _pertenece(d, 0, "telefono_aprox", "000")


def test_sorpresa_sube_con_lo_raro_y_es_cero_con_lo_comun():
    from rie02.rasgos import _sorpresa, base_sorpresa
    aristas_ = lambda *tt: [(0, 1, t, "v", 1.0) for t in tt]  # noqa: E731
    comunes = [Caso(f"c{i}", "relacional", [0, 1], aristas_("telefono")) for i in range(40)]
    raro = Caso("raro", "relacional", [0, 1], aristas_("telefono", "dispositivo", "direccion_hogar"))
    base = base_sorpresa(comunes + [raro])
    assert _sorpresa(base["mult"], 1) < 0.05  # un solo vínculo es lo común
    assert _sorpresa(base["mult"], 3) > 3.0  # tres tipos entre el mismo par es raro


def test_entrenar_sistema_con_tipologia_excluida_quita_sus_positivos(cfg, monkeypatch):
    import rie02.corrida as corrida
    vistos = []
    real = corrida.entrenar
    monkeypatch.setattr(corrida, "entrenar", lambda X, y, *a, **k: (vistos.append((len(y), int(y.sum()))), real(X, y, *a, **k))[1])
    p = Params(seed=11, n_apps_legit=2500, anillos_por_tipologia=3)
    corrida.entrenar_sistema(generar(p), cfg)
    corrida.entrenar_sistema(generar(p), cfg, excluir_tipologia="prestanombres")
    (n0, pos0), (n1, pos1) = vistos[0], vistos[2]
    assert n1 < n0 and pos1 < pos0  # se quitaron filas, y eran positivas


def test_louvain_recursivo_respeta_el_limite(cfg):
    from rie02.grafo import _partir
    import networkx as nx
    g = nx.connected_caveman_graph(6, 20)  # 120 nodos en 6 cliques unidos en anillo
    nx.set_edge_attributes(g, 1.0, "w")
    partes = _partir(g, 25, 0)
    assert sum(len(p) for p in partes) == 120 and max(len(p) for p in partes) <= 25


def test_presupuesto():
    assert presupuesto(12321, 0.004) == 50
    assert presupuesto(10, 0.004) == 1

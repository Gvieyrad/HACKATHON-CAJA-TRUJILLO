import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

from rie02.generador import TIPOLOGIAS, Params, generar
from rie02.normalizar import normalizar_direccion, normalizar_telefono


def test_telefono_formatos_equivalentes():
    esperado = "987654321"
    for raw in ("+51 987 654 321", "987654321", "987-654-321", "(51) 987654321"):
        assert normalizar_telefono(raw) == esperado


def test_telefono_invalido_es_none():
    for raw in ("", None, "12345", "187654321", float("nan"), "+51 12"):
        assert normalizar_telefono(raw) is None


def test_direccion_estilos_equivalentes():
    estilos = ["Mz. A Lt. 5 Urb. Los Jardines", "MZ A LT 5 URB LOS JARDINES",
               "Manzana A Lote 5 Urbanización Los Jardines", "MZ.A LT.5 URB. LOS JARDINES"]
    assert {normalizar_direccion(s) for s in estilos} == {"los jardines|a|5"}


def test_direccion_incompleta_es_none():
    assert normalizar_direccion("") is None
    assert normalizar_direccion("Av. Larco 123") is None


def test_determinismo_por_semilla():
    a = generar(Params(seed=3, n_apps_legit=800, anillos_por_tipologia=2))
    b = generar(Params(seed=3, n_apps_legit=800, anillos_por_tipologia=2))
    pd.testing.assert_frame_equal(a.apps, b.apps)
    pd.testing.assert_frame_equal(a.etiquetas, b.etiquetas)


def test_estructura_y_conteo_de_anillos(mundo_chico):
    a, e = mundo_chico.apps, mundo_chico.etiquetas
    assert a["app_id"].is_unique and set(a["app_id"]) == set(e["app_id"])
    por_tip = e[e["anillo_id"] >= 0].groupby("tipologia")["anillo_id"].nunique()
    assert {t: int(por_tip[t]) for t in TIPOLOGIAS} == {t: 3 for t in TIPOLOGIAS}
    assert (e[e["anillo_id"] >= 0].groupby("anillo_id").size() >= 3).all()
    assert a["dia"].between(0, 179).all()


def test_mundo_sin_anillos():
    m = generar(Params(seed=5, n_apps_legit=600, anillos_por_tipologia=0))
    assert (m.etiquetas["anillo_id"] == -1).all()


def test_identificadores_y_orden_no_filtran_la_etiqueta(mundo_chico):
    """Un modelo que solo ve ids numéricos y la posición de fila debe rendir como el azar."""
    a, e = mundo_chico.apps, mundo_chico.etiquetas
    num = lambda s: s.str[1:].astype(float)  # noqa: E731
    X = pd.DataFrame({"app": num(a["app_id"]), "persona": num(a["persona_id"]), "negocio": num(a["negocio_id"]),
                      "fila": np.arange(len(a))})
    y = (e["anillo_id"] >= 0).to_numpy()
    idx = np.random.default_rng(0).permutation(len(a))
    tr, te = idx[: len(a) // 2], idx[len(a) // 2:]
    m = LGBMClassifier(n_estimators=60, verbose=-1, random_state=0).fit(X.iloc[tr], y[tr])
    auc = roc_auc_score(y[te], m.predict_proba(X.iloc[te])[:, 1])
    assert 0.35 < auc < 0.65, f"posible fuga por id/orden: AUC={auc:.2f}"


def _anillo(mundo, tip):
    e = mundo.etiquetas[mundo.etiquetas["tipologia"] == tip]
    r = e["anillo_id"].iloc[0]
    ids = e.loc[e["anillo_id"] == r, "app_id"]
    return mundo.apps[mundo.apps["app_id"].isin(ids)]


def test_colusion_comparte_asesor_y_nada_mas(mundo_chico):
    g = _anillo(mundo_chico, "colusion_asesor")
    assert g["asesor_id"].nunique() == 1
    tel = g["telefono_raw"].map(normalizar_telefono).dropna()
    assert tel.is_unique and g["dispositivo"].is_unique


def test_referencias_cruzadas_forman_ciclo(mundo_chico):
    g = _anillo(mundo_chico, "referencias_cruzadas")
    personas = set(g["persona_id"])
    assert set(g["ref1_id"]) <= personas and set(g["ref2_id"]) <= personas


def test_prestanombres_comparten_dispositivo_y_negocio(mundo_chico):
    g = _anillo(mundo_chico, "prestanombres")
    assert g["dispositivo"].nunique() == 1 and g["negocio_id"].nunique() == 1


def test_sin_atributos_no_comparten_nada(mundo_chico):
    g = _anillo(mundo_chico, "sin_atributos")
    assert g["dispositivo"].is_unique and g["negocio_id"].is_unique
    assert g["telefono_raw"].map(normalizar_telefono).dropna().is_unique
    assert g["direccion_hogar_raw"].map(normalizar_direccion).is_unique


def test_hay_compartir_legitimo(mundo_chico):
    """El mundo legítimo debe contener teléfonos y dispositivos compartidos (si no, el reto sería trivial)."""
    a = mundo_chico.apps
    tel = a["telefono_raw"].map(normalizar_telefono).dropna()
    assert (tel.value_counts() >= 2).sum() > 20
    assert (a["dispositivo"].value_counts() >= 30).sum() >= 1  # cibercafé

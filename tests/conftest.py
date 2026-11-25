import pathlib

import pytest
import yaml

from rie02.generador import Params, generar

RAIZ = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def cfg():
    return yaml.safe_load((RAIZ / "config" / "preregistro.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def mundo_chico():
    return generar(Params(seed=7, n_apps_legit=2500, anillos_por_tipologia=3))

import http.client
import json
import pathlib
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest
import yaml

from rie02.corrida import instantanea
from rie02.expediente import PALABRAS_PROHIBIDAS, TIPOS_VERIFICABLES, construir, resumen, verificar
from rie02.grafo import Caso
from rie02.modelos import Puerta
from rie02.panel import aplicar_revisiones, leer_revisiones, servidor, tasa_acuerdo, validar_revision

AMBAS = {"fam_relacional": True, "fam_conductual": True}
CFG = yaml.safe_load((pathlib.Path(__file__).resolve().parent.parent / "config" / "preregistro.yaml").read_text(encoding="utf-8"))
CORTE = 179


@pytest.fixture(scope="module")
def snap(mundo_chico, cfg):
    return instantanea(mundo_chico, 179, cfg)


def _casos_positivos(snap):
    return [i for i in range(len(snap.casos)) if snap.L["y"].iat[i] == 1 and snap.casos[i].tipo == "relacional"]


def _exp(snap, i):
    return construir(snap.casos[i], snap.d, snap.X.iloc[i], AMBAS, 0.9, CORTE, CFG["caso_asesor"])


def test_expediente_valido_y_con_lenguaje_correcto(snap):
    positivos = _casos_positivos(snap)
    assert positivos
    for i in positivos[:10]:
        e = _exp(snap, i)
        assert verificar(e, snap.d) == []
        assert all(s["refs"] for s in e["senales"])
        txt = resumen(e).lower()
        assert "merece revisión" in txt and not any(p in txt for p in PALABRAS_PROHIBIDAS)
        assert e["decision_automatica"] is False


def test_verificador_detecta_valor_alterado(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    s = next(s for s in e["senales"] if s["familia"] == "relacional" and s["tipo"] in TIPOS_VERIFICABLES)
    s["valor"] = "VALOR-FALSO"
    assert any("no comparten el valor" in f for f in verificar(e, snap.d))


def test_verificador_detecta_referencia_ajena(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    e["senales"][0]["refs"] = e["senales"][0]["refs"] + ["A999999"]
    assert any("fuera del caso" in f for f in verificar(e, snap.d))


def test_verificador_detecta_palabra_prohibida(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    e["senales"][0]["texto"] += " Esto es un fraude."
    assert any("palabra prohibida" in f for f in verificar(e, snap.d))


def test_una_sola_familia_no_alerta(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    e["familias"]["conductual"] = False
    assert any("menos de dos familias" in f for f in verificar(e, snap.d))


def test_decision_automatica_se_rechaza(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    e["decision_automatica"] = True
    assert any("decisión automática" in f for f in verificar(e, snap.d))


def test_todo_caso_que_pasa_la_puerta_tiene_expediente_verificable(snap):
    """Con las familias REALES de la puerta (no forzadas): cada familia activa trae su señal verificada."""
    p = Puerta(CFG["puerta"]).ajustar(snap.X)
    fams, pasa = p.familias(snap.X), p.pasa(snap.X)
    idx = np.flatnonzero(pasa)
    assert len(idx) > 5
    for i in idx:
        e = construir(snap.casos[i], snap.d, snap.X.iloc[i], fams.iloc[i].to_dict(), 0.5, CORTE, CFG["caso_asesor"])
        assert verificar(e, snap.d, CORTE, CFG["caso_asesor"]) == [], snap.casos[i].caso_id
        assert any(s["familia"] == "conductual" for s in e["senales"])
        assert any(s["familia"] == "relacional" for s in e["senales"])


def test_familia_activa_sin_senal_es_falla(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    e["senales"] = [s for s in e["senales"] if s["familia"] != "conductual"]
    assert any("ninguna señal de esa familia" in f for f in verificar(e, snap.d, CORTE, CFG["caso_asesor"]))


def test_cifra_agregada_alterada_es_falla(snap):
    e = _exp(snap, _casos_positivos(snap)[0])
    next(s for s in e["senales"] if s["tipo"] == "agregado")["numeros"]["z_tiempo"] += 1.0
    assert any("no coinciden con los datos" in f for f in verificar(e, snap.d, CORTE, CFG["caso_asesor"]))


def test_senal_de_asesor_se_recalcula(snap):
    d = snap.d.copy()
    ventana = d[d["dia"] > CORTE - CFG["caso_asesor"]["ventana_dias"]]
    a = ventana["asesor_id"].value_counts().index[0]
    idx = ventana.index[ventana["asesor_id"] == a].tolist()
    assert len(idx) >= 3
    d.loc[idx, "marca"] = 1
    e = construir(Caso("S_x", "asesor", idx, [], asesor=a), d, snap.X.iloc[0], AMBAS, 0.5, CORTE, CFG["caso_asesor"])
    assert verificar(e, d, CORTE, CFG["caso_asesor"]) == []
    next(s for s in e["senales"] if s["tipo"] == "asesor_anomalo")["numeros"]["n_ventana"] += 3
    assert any("volumen afirmado" in f for f in verificar(e, d, CORTE, CFG["caso_asesor"]))


def test_revision_duplicada_cuenta_una_vez():
    cola_ = [dict(caso_id="R1", score=0.9, patron="p|a"), dict(caso_id="R2", score=0.8, patron="p|a")]
    doble = [dict(caso_id="R1", decision="rechazar", patron="p|a")] * 2
    assert aplicar_revisiones(cola_, doble)[0]["factor_revision"] == 0.5  # no 0.25
    revs = [dict(caso_id="R1", decision="aprobar"), dict(caso_id="R1", decision="aprobar"),
            dict(caso_id="R1", decision="aprobar"), dict(caso_id="R2", decision="rechazar")]
    assert tasa_acuerdo(revs) == 0.5


def test_leer_revisiones_ignora_lineas_corruptas(tmp_path):
    ruta = tmp_path / "r.jsonl"
    ok = json.dumps(dict(caso_id="R1", decision="aprobar", patron="p|a"))
    ruta.write_text(f'{ok}\n{{"caso_id": "R2", "deci\n\n[1,2]\n{ok}\n', encoding="utf-8")
    assert len(leer_revisiones(ruta)) == 2


def test_validar_revision():
    ok = {"R1": "relacional|telefono"}
    r = validar_revision({"caso_id": "R1", "decision": "rechazar", "motivo": " es una familia "}, {"R1"}, ok)
    assert r["motivo"] == "es una familia" and r["patron"] == "relacional|telefono"
    for malo in ({"caso_id": "R9", "decision": "aprobar"}, {"caso_id": "R1", "decision": "borrar"},
                 {"caso_id": "R1", "decision": "rechazar", "motivo": "  "}, {"caso_id": "R1", "decision": "aprobar", "motivo": "x" * 501},
                 [], None):
        with pytest.raises(ValueError):
            validar_revision(malo, {"R1"}, ok)


def test_rechazos_bajan_la_prioridad_del_mismo_patron():
    cola_ = [dict(caso_id=f"R{i}", score=0.9 - 0.1 * i, patron="p|a" if i < 3 else "p|b") for i in range(4)]
    revs = [dict(caso_id="R0", decision="rechazar", patron="p|a")]
    nueva = aplicar_revisiones(cola_, revs)
    assert "R0" not in [e["caso_id"] for e in nueva]  # ya revisado
    por = {e["caso_id"]: e for e in nueva}
    assert por["R1"]["factor_revision"] == 0.5 and por["R3"]["factor_revision"] == 1.0
    muchos = [dict(caso_id=f"X{i}", decision="rechazar", patron="p|a") for i in range(10)]
    assert min(e["factor_revision"] for e in aplicar_revisiones(cola_, muchos)) == 0.1  # piso


def test_tasa_acuerdo():
    assert tasa_acuerdo([]) is None
    assert tasa_acuerdo([dict(caso_id="R1", decision="aprobar"), dict(caso_id="R2", decision="rechazar")]) == 0.5


def _http(url, cuerpo=None, token=None, tipo="application/json"):
    headers = {"Content-Type": tipo} if cuerpo is not None else {}
    if token:
        headers["X-Panel-Token"] = token
    req = urllib.request.Request(url, data=cuerpo, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_panel_http(tmp_path):
    cola_ = [dict(caso_id="R1", n_solicitudes=3, score=0.9, patron="relacional|telefono", resumen="x"),
             dict(caso_id="R2", n_solicitudes=3, score=0.8, patron="relacional|telefono", resumen="y")]
    ruta = tmp_path / "rev.jsonl"
    srv = servidor(cola_, ruta, puerto=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    post = lambda body, **kw: _http(base + "/api/revision", json.dumps(body).encode(), **kw)  # noqa: E731
    try:
        assert _http(base + "/")[0] == 200
        assert json.loads(_http(base + "/api/cola")[1])["acuerdo"] is None
        ok = {"caso_id": "R1", "decision": "rechazar", "motivo": "familia del mismo hogar"}
        assert post(ok)[0] == 403  # sin token
        assert post(ok, token="falso")[0] == 403
        assert post(ok, token=srv.token, tipo="text/plain")[0] == 415
        assert post({**ok, "motivo": ""}, token=srv.token)[0] == 400
        assert post({**ok, "caso_id": "R9"}, token=srv.token)[0] == 400
        assert _http(base + "/api/revision", b"x" * 5000, token=srv.token)[0] == 413
        assert not ruta.exists()
        assert post(ok, token=srv.token)[0] == 200
        assert len(ruta.read_text().splitlines()) == 1
        j = json.loads(_http(base + "/api/cola")[1])
        assert [e["caso_id"] for e in j["cola"]] == ["R2"] and j["cola"][0]["factor_revision"] == 0.5
        assert j["acuerdo"] == 0.0
    finally:
        srv.shutdown()
        srv.server_close()


def test_panel_robusto_ante_entradas_hostiles(tmp_path):
    cola_ = [dict(caso_id="R1", n_solicitudes=3, score=0.9, patron="relacional|telefono", resumen="x")]
    srv = servidor(cola_, tmp_path / "rev.jsonl", puerto=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    puerto = srv.server_address[1]
    base = f"http://127.0.0.1:{puerto}"
    try:
        for host in ("evil.example", f"evil.example:{puerto}"):  # DNS rebinding
            con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
            con.request("GET", "/api/cola", headers={"Host": host})
            assert con.getresponse().status == 403
            con.close()
        for cuerpo in (b'{"caso_id": ["x"], "decision": "aprobar"}', b"[" * 3000, b"no es json", b'{"caso_id": {}}'):
            codigo, _ = _http(base + "/api/revision", cuerpo, token=srv.token)
            assert codigo == 400, cuerpo[:20]  # siempre una respuesta, nunca un traceback con la conexión cerrada
        assert _http(base + "/api/cola")[0] == 200  # el servidor sigue vivo
    finally:
        srv.shutdown()
        srv.server_close()

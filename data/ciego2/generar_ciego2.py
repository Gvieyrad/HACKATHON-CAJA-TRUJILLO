"""Generador del conjunto ciego 2 (semilla fija). Uso: python -I generar_ciego2.py"""
import os
import random

import numpy as np
import pandas as pd

SEED = 20261124
N_TARGET = 10000
DIAS = 180
OUT = os.path.dirname(os.path.abspath(__file__))
R = random.Random(SEED)
RNG = np.random.default_rng(SEED)

PRE = ["Los", "Las", "La", "Santa", "San", "Alto", "Bello", "Nuevo", "Villa", "El"]
NOU = ["Mirador", "Palmeras", "Olivos", "Jardines", "Esperanza", "Rosa", "Horizonte", "Sol",
       "Pinos", "Alamos", "Cerezos", "Lomas", "Valle", "Brisas", "Cumbres", "Naranjos",
       "Molino", "Trigal", "Campina", "Arenales"]
URBS = [f"{a} {b}" for a in PRE for b in NOU]
MZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
N_ASESOR, N_AGENCIA = 80, 12
ASESOR_AG = {i: R.randrange(N_AGENCIA) for i in range(N_ASESOR)}
ASESOR_W = RNG.lognormal(0, 0.5, N_ASESOR)
ASESOR_W = ASESOR_W / ASESOR_W.sum()

_used = set()


def uniq(fn):
    while True:
        v = fn()
        if v not in _used:
            _used.add(v)
            return v


def new_id(prefix):
    return uniq(lambda: f"{prefix}{R.randrange(10**7):07d}")


def new_loc():
    return uniq(lambda: (R.randrange(len(URBS)), R.choice(MZ), R.randint(1, 120)))


def new_phone():
    return uniq(lambda: 900000000 + R.randrange(10**8))


def new_dev():
    return uniq(lambda: "D" + "".join(R.choice("0123456789abcdef") for _ in range(10)))


def fmt_addr(loc, style=None):
    u, mz, lt = loc
    t = URBS[u]
    s = R.randrange(4) if style is None else style
    return [f"Mz. {mz} Lt. {lt} Urb. {t}", f"MZ.{mz} LT.{lt} URB. {t.upper()}",
            f"Manzana {mz} Lote {lt} Urbanizacion {t}", f"MZ {mz} LT {lt} URB {t.upper()}"][s]


def fmt_phone(n):
    s = str(n)
    return [s, f"{s[:3]}-{s[3:6]}-{s[6:]}", f"+51 {s[:3]} {s[3:6]} {s[6:]}",
            f"{s[:3]} {s[3:6]} {s[6:]}"][R.randrange(4)]


POP_REF = [new_id("P") for _ in range(250)]  # referentes populares (legitimos)


def new_ref():
    return R.choice(POP_REF) if R.random() < 0.05 else new_id("P")


def new_person(home_biz=0.25):
    h = new_loc()
    return dict(pid=new_id("P"), tel=new_phone(), dev=new_dev(), hog=h,
                neg=h if R.random() < home_biz else new_loc(), nid=new_id("N"),
                r1=new_ref(), r2=new_ref())


def make_row(p, dia, verif=0.88, mscale=1.0, asesor=None, ratio_mu=1.0, tel_raw=None,
             neg_raw=None, hog_raw=None):
    a = int(RNG.choice(N_ASESOR, p=ASESOR_W)) if asesor is None else asesor
    mon = float(np.clip(RNG.lognormal(7.6, 0.6) * mscale, 150, 40000))
    return dict(
        dia=int(min(max(dia, 0), DIAS - 1)), persona_id=p["pid"],
        telefono_raw=tel_raw or fmt_phone(p["tel"]), dispositivo=p["dev"],
        direccion_hogar_raw=hog_raw or fmt_addr(p["hog"]),
        direccion_negocio_raw=neg_raw or fmt_addr(p["neg"]), negocio_id=p["nid"],
        ref1_id=p["r1"], ref2_id=p["r2"], asesor_id=f"S{a:03d}",
        agencia_id=f"G{ASESOR_AG[a]}", zona=p["hog"][0] % 10,
        tiempo_llenado_seg=round(float(np.clip(RNG.lognormal(6.3, 0.45), 40, 5000)), 1),
        hora=int(RNG.choice(np.arange(8, 20))) if R.random() < 0.93 else R.randrange(24),
        ratio_monto=round(float(np.clip(RNG.normal(ratio_mu, 0.12), 0.3, 2.0)), 3),
        monto=round(mon, 2), verif_domicilio_ok=int(R.random() < verif))


def lab(row, ring=-1, tipo="legit", grp=-1, gtipo="ninguno"):
    return {**row, "_anillo": ring, "_tipo": tipo, "_grupo": grp, "_gtipo": gtipo}


# ---------------------------------------------------------------- legitimos
def legit_groups():
    out, gid = [], 0
    # familias: telefono y/o hogar compartido; 30% con SIM numericamente cercanas
    for _ in range(70):
        n, d0, win = R.randint(3, 6), R.randrange(DIAS), R.choice([10, 40, 170])
        hog, tel = new_loc(), new_phone()
        near = R.random() < 0.3
        ps = []
        for k in range(n):
            p = new_person()
            p["hog"] = hog if R.random() < 0.9 else p["hog"]
            p["tel"] = tel if (not near and R.random() < 0.75) else (tel + R.randint(1, 12) if near else p["tel"])
            if R.random() < 0.2 and ps:  # un familiar atiende negocio en el hogar de otro
                p["neg"] = ps[0]["hog"]
            if R.random() < 0.15 and ps:
                p["r1"] = ps[0]["pid"]
            ps.append(p)
        for p in ps:
            out.append(lab(make_row(p, d0 + R.randrange(win)), grp=gid, gtipo="familia"))
        gid += 1
    # mercados: misma direccion de negocio (puestos)
    for _ in range(25):
        n, d0 = R.randint(6, 25), R.randrange(60)
        neg = new_loc()
        for _k in range(n):
            p = new_person()
            p["neg"] = neg
            out.append(lab(make_row(p, d0 + R.randrange(120)), grp=gid, gtipo="mercado"))
        gid += 1
    # cibercafes: pocos dispositivos compartidos por muchos clientes
    for _ in range(8):
        n, d0 = R.randint(12, 36), R.randrange(100)
        devs = [new_dev() for _ in range(R.randint(1, 3))]
        for _k in range(n):
            p = new_person()
            p["dev"] = R.choice(devs)
            out.append(lab(make_row(p, d0 + R.randrange(80)), grp=gid, gtipo="cibercafe"))
        gid += 1
    # talleres: negocio, direccion y asesor comunes
    for _ in range(15):
        n, d0 = R.randint(3, 8), R.randrange(150)
        neg, nid, ase = new_loc(), new_id("N"), int(RNG.choice(N_ASESOR, p=ASESOR_W))
        for _k in range(n):
            p = new_person()
            p["neg"], p["nid"] = neg, nid
            out.append(lab(make_row(p, d0 + R.randrange(30), asesor=ase), grp=gid, gtipo="taller"))
        gid += 1
    return out


def legit_independents(n):
    out, made = [], 0
    while made < n:
        p = new_person()
        k = 1 if R.random() > 0.07 else R.randint(2, 3)  # renovaciones
        d = R.randrange(DIAS)
        for j in range(k):
            same_ag = R.random() > 0.15
            ase = None
            row = make_row(p, d, ratio_mu=1.0 if j == 0 else 1.05)
            out.append(lab(row))
            made += 1
            d += R.randint(15, 80) if R.random() < 0.15 else R.randint(45, 120)
            if d >= DIAS:
                break
    return out


# ------------------------------------------------------------------ anillos
def ring_sim_secuencial(rid):
    n, win = R.randint(4, 8), R.randint(15, 60)
    d0 = R.randrange(DIAS - win)
    base, rows = new_phone(), []
    for _ in range(n):
        p = new_person()
        if R.random() < 0.85:
            p["tel"] = base + R.randint(0, 18)
        rows.append(make_row(p, d0 + R.randrange(win), verif=0.8))
    return rows


def ring_enlace_heterogeneo(rid):
    n, win = R.randint(4, 9), R.randint(40, 120)
    d0 = R.randrange(DIAS - win)
    ps = [new_person() for _ in range(n)]
    raws = [dict() for _ in range(n)]
    for i in range(1, n):
        par = R.randrange(i)
        kind = R.choice(["tel", "dev", "neg", "ref"])
        if kind == "tel":
            ps[i]["tel"] = ps[par]["tel"]
        elif kind == "dev":
            ps[i]["dev"] = ps[par]["dev"]
        elif kind == "neg":
            ps[i]["neg"] = ps[par]["neg"]
        else:
            ps[i]["r2"] = ps[par]["r1"]
    days = sorted(R.randrange(win) for _ in range(n))
    return [make_row(p, d0 + d, verif=0.8) for p, d in zip(ps, days)]


def ring_domicilio_como_negocio(rid):
    n, win = R.randint(3, 6), R.randint(10, 90)
    d0 = R.randrange(DIAS - win)
    ps = [new_person(home_biz=0.0) for _ in range(n)]
    for i in range(n):
        if R.random() < 0.9:
            ps[i]["neg"] = ps[(i + 1) % n]["hog"]
    return [make_row(p, d0 + R.randrange(win), verif=0.75) for p in ps]


def ring_fraccionamiento(rid):
    k = R.randint(1, 2)
    rows, d0 = [], R.randrange(DIAS - 30)
    ags = R.sample(range(N_ASESOR), 4)
    for _ in range(k):
        p = new_person()
        for j in range(R.randint(3, 5) if k == 1 else R.randint(2, 4)):
            q = dict(p)
            if R.random() < 0.6:
                q["dev"] = new_dev()
            if R.random() < 0.6:
                q["tel"] = new_phone()
            rows.append(make_row(q, d0 + R.randrange(25), mscale=0.55, asesor=R.choice(ags)))
    return rows


RING_FNS = [("sim_secuencial", ring_sim_secuencial, 9),
            ("enlace_heterogeneo", ring_enlace_heterogeneo, 9),
            ("domicilio_como_negocio", ring_domicilio_como_negocio, 8),
            ("fraccionamiento_multiagencia", ring_fraccionamiento, 8)]


def build():
    rings, rid = [], 0
    plan = [(n, f) for n, f, c in RING_FNS for _ in range(c)]
    R.shuffle(plan)
    for name, fn in plan:
        rows = fn(rid)
        if len(rows) < 3:
            continue
        rings += [lab(r, ring=rid, tipo=name) for r in rows]
        rid += 1
    groups = legit_groups()
    ind = legit_independents(N_TARGET - len(rings) - len(groups))
    allr = rings + groups + ind
    R.shuffle(allr)
    df = pd.DataFrame(allr)
    df.insert(0, "app_id", [f"A{i:06d}" for i in range(len(df))])
    return df, rid


if __name__ == "__main__":
    df, nr = build()
    cols = ["app_id", "dia", "persona_id", "telefono_raw", "dispositivo", "direccion_hogar_raw",
            "direccion_negocio_raw", "negocio_id", "ref1_id", "ref2_id", "asesor_id", "agencia_id",
            "zona", "tiempo_llenado_seg", "hora", "ratio_monto", "monto", "verif_domicilio_ok"]
    df[cols].to_csv(os.path.join(OUT, "apps.csv"), index=False)
    et = df[["app_id", "_anillo", "_tipo", "_grupo", "_gtipo"]]
    et.columns = ["app_id", "anillo_id", "tipologia", "grupo_id", "grupo_tipo"]
    et.to_csv(os.path.join(OUT, "etiquetas.csv"), index=False)
    print(len(df), nr)

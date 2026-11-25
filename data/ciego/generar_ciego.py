"""Generador sintetico ciego (semilla 4242). Solo stdlib + pandas."""
import os, random, string
import pandas as pd

R = random.Random(4242)
OUT = os.path.dirname(os.path.abspath(__file__))
DAYS, N_ASESOR, N_LEGIT = 180, 60, 10000

used_ids, used_phone, used_dev, used_addr = set(), set(), set(), set()
A = ["Los", "Las", "San", "Santa", "Nuevo", "Villa", "El", "La", "Alto", "Bello"]
B = ["Jardines", "Pinos", "Olivos", "Palmeras", "Andres", "Rosa", "Horizonte",
     "Sol", "Mirador", "Esperanza", "Alamos", "Cipreses"]
URBS = [f"{a} {b}" for a in A for b in B]
R.shuffle(URBS)
DENSE = URBS[:10]
W = [4 if u in DENSE else 1 for u in URBS]


def uid7(prefix):
    while True:
        n = R.randrange(1_000_000, 10_000_000)
        if n not in used_ids:
            used_ids.add(n)
            return f"{prefix}{n}"


def new_phone():
    while True:
        d = "9" + "".join(R.choice("0123456789") for _ in range(8))
        if d not in used_phone:
            used_phone.add(d)
            return d


def new_dev():
    while True:
        d = "D" + "".join(R.choice("0123456789abcdef") for _ in range(10))
        if d not in used_dev:
            used_dev.add(d)
            return d


def render_phone(d):
    if R.random() < 0.03:
        return ""
    return R.choice([
        f"+51 {d[:3]} {d[3:6]} {d[6:]}", d, f"{d[:3]}-{d[3:6]}-{d[6:]}",
        f"(51) {d}", f"+51{d}", f"{d[:3]} {d[3:6]} {d[6:]}"])


def new_addr(urb=None):
    while True:
        a = (R.choice(string.ascii_uppercase), R.randint(1, 60), urb or R.choices(URBS, W)[0])
        if a not in used_addr:
            used_addr.add(a)
            return a


def render_addr(a):
    if a is None:
        return ""
    m, l, u = a
    return R.choice([
        f"Mz. {m} Lt. {l} Urb. {u}", f"MZ {m} LT {l} URB {u.upper()}",
        f"Manzana {m} Lote {l} Urbanizacion {u}", f"MZ.{m} LT.{l} URB. {u.upper()}"])


COMMON = [uid7("P") for _ in range(400)]


def ext():
    return R.choice(COMMON) if R.random() < 0.15 else uid7("P")


def beh(fraud):
    if fraud:
        return dict(tiempo=R.lognormvariate(6.15, .38), hora=round(R.gauss(12.5, 3.8)),
                    ratio=R.gauss(1.12, .3), monto=R.lognormvariate(8.8, .7),
                    verif=int(R.random() < .68))
    return dict(tiempo=R.lognormvariate(6.4, .35), hora=round(R.gauss(11.5, 3.2)),
                ratio=R.gauss(1.0, .28), monto=R.lognormvariate(8.6, .8),
                verif=int(R.random() < .85))


def person(day=None, asesor=None, zona=None, fraud=False):
    home = new_addr()
    biz = None if R.random() < .15 else (home if R.random() < .2 else new_addr())
    p = dict(day=R.randrange(DAYS) if day is None else min(DAYS - 1, day),
             phone=new_phone(), dev=new_dev(), home=home, biz=biz, neg=uid7("N"),
             ases=R.randrange(N_ASESOR) if asesor is None else asesor,
             zona=R.randrange(12) if zona is None else zona, refs=[ext(), ext()])
    p.update(beh(fraud))
    return p


rows = []
_gid = [0]
_rid = [0]


def add(p, anillo=-1, tip="legit", grupo=-1, gtipo="ninguno"):
    rows.append(dict(p=p, anillo=anillo, tip=tip, grupo=grupo, gtipo=gtipo))
    return len(rows) - 1


def newgroup():
    _gid[0] += 1
    return _gid[0] - 1


# ---------------- legitimas ----------------
ciber_devs = []
for _ in range(700):  # hogares / familias
    g, n = newgroup(), R.choice([2, 2, 3, 3, 4])
    home, sph, sdev = new_addr(), new_phone(), new_dev()
    fam = (uid7("N"), new_addr()) if R.random() < .3 else None
    start, zona, ases = R.randrange(DAYS), R.randrange(12), R.randrange(N_ASESOR)
    uids = []
    for _ in range(n):
        p = person(day=start + R.randrange(60), asesor=ases if R.random() < .6 else None, zona=zona)
        p["home"] = home
        if R.random() < .5: p["phone"] = sph
        if R.random() < .35: p["dev"] = sdev
        if fam and R.random() < .6: p["neg"], p["biz"] = fam
        uids.append(add(p, grupo=g, gtipo="familia"))
    for u in uids:
        if R.random() < .3:
            rows[u]["p"]["refs"][0] = ("u", R.choice([x for x in uids if x != u]))

for _ in range(350):  # parientes que se avalan (pares mutuos / estrella)
    g, n = newgroup(), R.choice([2, 2, 3])
    start, ases = R.randrange(DAYS), R.randrange(N_ASESOR)
    uids = [add(person(day=start + R.randrange(40), asesor=ases if R.random() < .5 else None),
                grupo=g, gtipo="parientes_avales") for _ in range(n)]
    if n == 2:
        rows[uids[0]]["p"]["refs"][0] = ("u", uids[1]); rows[uids[1]]["p"]["refs"][0] = ("u", uids[0])
    else:
        rows[uids[0]]["p"]["refs"][0] = ("u", uids[1])
        for u in uids[1:]: rows[u]["p"]["refs"][0] = ("u", uids[0])

for _ in range(40):  # mercados / galerias
    g, zona = newgroup(), R.randrange(12)
    gal, aa = new_addr(), [R.randrange(N_ASESOR) for _ in range(2)]
    uids = []
    for _ in range(R.randint(15, 40)):
        p = person(asesor=R.choice(aa), zona=zona)
        p["biz"] = gal
        uids.append(add(p, grupo=g, gtipo="mercado"))
    for u in uids:
        if R.random() < .25: rows[u]["p"]["refs"][0] = ("u", R.choice(uids))

for _ in range(25):  # cibercafes / locutorios
    g, zona, cd, cph = newgroup(), R.randrange(12), new_dev(), new_phone()
    ciber_devs.append(cd)
    for _ in range(R.randint(4, 20)):
        p = person(zona=zona)
        p["dev"] = cd
        if R.random() < .25: p["phone"] = cph
        add(p, grupo=g, gtipo="ciber")

for _ in range(40):  # cooperativas
    g, zona, ases, start = newgroup(), R.randrange(12), R.randrange(N_ASESOR), R.randrange(DAYS)
    uids = [add(person(day=start + R.randrange(45), asesor=ases, zona=zona), grupo=g, gtipo="cooperativa")
            for _ in range(R.randint(6, 15))]
    for u in uids:
        if R.random() < .6: rows[u]["p"]["refs"][0] = ("u", R.choice([x for x in uids if x != u]))

for _ in range(60):  # un asesor atiende un mismo barrio
    g, zona, ases, urb = newgroup(), R.randrange(12), R.randrange(N_ASESOR), R.choice(URBS)
    for _ in range(R.randint(20, 40)):
        p = person(asesor=ases, zona=zona)
        p["home"] = new_addr(urb)
        add(p, grupo=g, gtipo="asesor_barrio")

while len(rows) < N_LEGIT:
    add(person())
LEGIT = list(range(len(rows)))


# ---------------- anillos (4 tipologias nuevas) ----------------
def mix(uids, slot, prob):
    for u in uids:
        if R.random() < prob:
            rows[u]["p"]["refs"][slot] = ("u", R.choice(LEGIT))


def ring(tip):
    rid = _rid[0]; _rid[0] += 1
    return lambda p: add(p, anillo=rid, tip=tip)


# 1) rotacion_dispositivos: 3-4 anillos comparten un pool de dispositivos "mula"
nr = R.randint(8, 12)
pools = [[new_dev() for _ in range(4)] for _ in range((nr + 2) // 3)]
for i in range(nr):
    mk = ring("rotacion_dispositivos")
    s, uids = R.randrange(DAYS - 30), []
    for _ in range(R.randint(3, 12)):
        p = person(day=s + R.randrange(30), fraud=True)
        p["dev"] = R.choice(ciber_devs) if R.random() < .1 else R.choice(pools[i // 3])
        uids.append(mk(p))
    mix(uids, 1, .2)

# 2) direccion_escalonada: reuso en zona densa, lotes contiguos, domicilio del anterior como negocio
for _ in range(R.randint(8, 12)):
    mk = ring("direccion_escalonada")
    while True:
        urb, mz, l0 = R.choice(DENSE), R.choice(string.ascii_uppercase), R.randint(1, 40)
        cand = [(mz, l0 + k, urb) for k in range(3)]
        if not any(c in used_addr for c in cand):
            used_addr.update(cand); break
    s, prev, uids = R.randrange(48), None, []
    for i in range(R.randint(3, 12)):
        p = person(day=s + i * R.randint(3, 12), fraud=True)
        p["home"] = R.choice(cand)
        if prev is not None: p["biz"] = prev
        prev = p["home"]
        uids.append(mk(p))
    mix(uids, 0, .2)

# 3) cadena_avales: A avala a B, B a C ... el ultimo avala a un legitimo
for _ in range(R.randint(8, 12)):
    mk = ring("cadena_avales")
    s, ases, zona, uids, d = R.randrange(60), R.randrange(N_ASESOR), R.randrange(12), [], 0
    for _ in range(R.randint(3, 12)):
        d += R.randint(1, 8)
        uids.append(mk(person(day=s + d, asesor=ases if R.random() < .8 else None, zona=zona, fraud=True)))
    for a, b in zip(uids, uids[1:]):
        rows[a]["p"]["refs"][0] = ("u", b)
    rows[uids[-1]]["p"]["refs"][0] = ("u", R.choice(LEGIT))
    mix(uids, 1, .15)

# 4) rafaga_casi_igual: ventana de 3 dias, telefonos consecutivos, comportamiento casi identico
for _ in range(R.randint(8, 12)):
    mk = ring("rafaga_casi_igual")
    n = R.randint(3, 12)
    while True:
        base = R.randrange(10 ** 8 - 20)
        ph = ["9" + f"{base + i:08d}" for i in range(n)]
        if not any(x in used_phone for x in ph): used_phone.update(ph); break
    urb, mz = R.choice(DENSE), R.choice(string.ascii_uppercase)
    while True:
        cand = [(mz, l, urb) for l in R.sample(range(1, 61), n)]
        if not any(c in used_addr for c in cand): used_addr.update(cand); break
    w0, ases, zona, shared = R.randrange(DAYS - 2), R.randrange(N_ASESOR), R.randrange(12), ext()
    b0 = beh(True)
    uids = []
    for i in range(n):
        p = person(day=w0 + R.randrange(3), asesor=ases, zona=zona, fraud=True)
        p.update(phone=ph[i], home=cand[i], tiempo=b0["tiempo"] * R.uniform(.93, 1.07),
                 monto=b0["monto"] * R.uniform(.95, 1.05), hora=min(23, max(0, b0["hora"] + R.randint(-1, 1))),
                 ratio=b0["ratio"] + R.uniform(-.05, .05))
        p["refs"][0] = shared
        uids.append(mk(p))
    mix(uids, 1, .15)

# ---------------- salida ----------------
order = list(range(len(rows)))
R.shuffle(order)
pid = {u: uid7("P") for u in order}
res = lambda r: pid[r[1]] if isinstance(r, tuple) else r
apps, labs = [], []
for k, u in enumerate(order):
    p, r = rows[u]["p"], rows[u]
    aid = f"A{k:06d}"
    apps.append(dict(
        app_id=aid, dia=int(p["day"]), persona_id=pid[u], telefono_raw=render_phone(p["phone"]),
        dispositivo=p["dev"], direccion_hogar_raw=render_addr(p["home"]),
        direccion_negocio_raw=render_addr(p["biz"]), negocio_id=p["neg"],
        ref1_id=res(p["refs"][0]), ref2_id=res(p["refs"][1]), asesor_id=f"S{p['ases']:03d}",
        agencia_id=f"G{p['ases'] // 5}", zona=p["zona"],
        tiempo_llenado_seg=round(min(2400, max(120, p["tiempo"])), 1),
        hora=min(23, max(0, p["hora"])), ratio_monto=round(min(2.5, max(.2, p["ratio"])), 3),
        monto=round(min(60000, max(300, p["monto"])), 2), verif_domicilio_ok=p["verif"]))
    labs.append(dict(app_id=aid, anillo_id=r["anillo"], tipologia=r["tip"],
                     grupo_id=r["grupo"], grupo_tipo=r["gtipo"]))
a, l = pd.DataFrame(apps), pd.DataFrame(labs)
a.to_csv(os.path.join(OUT, "apps.csv"), index=False, encoding="utf-8")
l.to_csv(os.path.join(OUT, "etiquetas.csv"), index=False, encoding="utf-8")
print(len(a), "filas;", int((l.anillo_id >= 0).sum()), "de anillo;", l.anillo_id.max() + 1, "anillos")

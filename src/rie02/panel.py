"""Panel de revisión humana (stdlib): lista la cola, el especialista aprueba, rechaza o corrige.

Seguridad: escucha solo en 127.0.0.1, exige Content-Type JSON y un token aleatorio por sesión
(evita que otra página web escriba revisiones), valida decisión/motivo y limita el tamaño del cuerpo.
"""
from __future__ import annotations

import json
import secrets
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DECISIONES = ("aprobar", "rechazar", "corregir")
MAX_CUERPO = 4096
MAX_MOTIVO = 500
FACTOR_RECHAZO = 0.5
PISO_FACTOR = 0.1


def validar_revision(cuerpo: object, casos_validos: set[str], patrones: dict[str, str]) -> dict:
    """Devuelve la revisión limpia o lanza ValueError con el motivo."""
    if not isinstance(cuerpo, dict):
        raise ValueError("cuerpo inválido")
    caso, decision, motivo = cuerpo.get("caso_id"), cuerpo.get("decision"), cuerpo.get("motivo", "")
    if not isinstance(caso, str) or caso not in casos_validos:
        raise ValueError("caso desconocido")
    if decision not in DECISIONES:
        raise ValueError("decisión inválida")
    if not isinstance(motivo, str) or len(motivo) > MAX_MOTIVO:
        raise ValueError("motivo inválido")
    if decision in ("rechazar", "corregir") and not motivo.strip():
        raise ValueError("rechazar o corregir exige motivo")
    return dict(caso_id=caso, decision=decision, motivo=motivo.strip(), patron=patrones[caso], ts=int(time.time()))


def _ultimas(revisiones: list[dict]) -> dict[str, dict]:
    """La ÚLTIMA revisión de cada caso es la que vale (un doble clic no cuenta dos veces)."""
    return {r["caso_id"]: r for r in revisiones}


def aplicar_revisiones(cola: list[dict], revisiones: list[dict]) -> list[dict]:
    """Reordena la cola: cada rechazo baja a la mitad la prioridad de los casos con el MISMO patrón
    de señales (piso 0.1). Los casos ya revisados salen de la cola pendiente. No borra nada."""
    ultimas = _ultimas(revisiones)
    rechazos = Counter(r["patron"] for r in ultimas.values() if r["decision"] == "rechazar")
    revisados = set(ultimas)
    salida = []
    for e in cola:
        if e["caso_id"] in revisados:
            continue
        f = max(PISO_FACTOR, FACTOR_RECHAZO ** rechazos.get(e["patron"], 0))
        salida.append({**e, "prioridad": e["score"] * f, "factor_revision": f})
    return sorted(salida, key=lambda e: -e["prioridad"])


def tasa_acuerdo(revisiones: list[dict]) -> float | None:
    """Fracción de revisiones que aprueban la alerta (None si no hay ninguna)."""
    ultimas = list(_ultimas(revisiones).values())
    return (sum(r["decision"] == "aprobar" for r in ultimas) / len(ultimas)) if ultimas else None


def leer_revisiones(ruta: Path) -> list[dict]:
    """Lee el JSONL ignorando líneas corruptas o incompletas (p. ej. una escritura cortada)."""
    if not ruta.exists():
        return []
    salida = []
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(linea) if linea.strip() else None
        except ValueError:
            continue
        if isinstance(r, dict) and {"caso_id", "decision", "patron"} <= r.keys():
            salida.append(r)
    return salida


PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8"><title>Cola de revisión RIE-02</title>
<style>body{font:15px system-ui;margin:2rem auto;max-width:60rem;padding:0 1rem}.caso{border:1px solid #ccc;border-radius:6px;padding:.8rem;margin:.8rem 0}
.meta{color:#555;font-size:13px}button{margin-right:.4rem}pre{white-space:pre-wrap;background:#f6f6f6;padding:.6rem}</style>
<h1>Casos que merecen revisión</h1><p class="meta" id="resumen"></p><div id="cola"></div>
<script>
const TOKEN="__TOKEN__";
async function cargar(){const r=await fetch('/api/cola');const j=await r.json();
 document.getElementById('resumen').textContent=j.pendientes+' pendientes · acuerdo con el sistema: '+(j.acuerdo===null?'sin revisiones':Math.round(j.acuerdo*100)+'%');
 const c=document.getElementById('cola');c.replaceChildren();
 for(const e of j.cola){const d=document.createElement('div');d.className='caso';
  const h=document.createElement('strong');h.textContent=e.caso_id+' · '+e.n_solicitudes+' solicitudes · prioridad '+e.prioridad.toFixed(2);d.append(h);
  const p=document.createElement('pre');p.textContent=e.resumen;d.append(p);
  const m=document.createElement('input');m.placeholder='motivo (obligatorio al rechazar o corregir)';m.size=50;d.append(m);
  for(const x of ['aprobar','rechazar','corregir']){const b=document.createElement('button');b.textContent=x;
   b.onclick=async()=>{const r=await fetch('/api/revision',{method:'POST',headers:{'Content-Type':'application/json','X-Panel-Token':TOKEN},
     body:JSON.stringify({caso_id:e.caso_id,decision:x,motivo:m.value})});if(!r.ok)alert((await r.json()).error);else cargar();};d.append(b);}
  c.append(d);}}
cargar();
</script></html>"""


def servidor(cola: list[dict], ruta_revisiones: Path, puerto: int = 8765) -> ThreadingHTTPServer:
    """cola: expedientes (dict) con clave 'resumen' ya generada. Devuelve el servidor sin arrancar."""
    token = secrets.token_hex(16)
    validos = {e["caso_id"] for e in cola}
    patrones = {e["caso_id"]: e["patron"] for e in cola}

    class Manejador(BaseHTTPRequestHandler):
        timeout = 10  # una conexión que no termina de enviar su cuerpo no bloquea un hilo para siempre

        def _host_ok(self) -> bool:
            """Solo acepta Host local: bloquea el DNS rebinding (una web externa leyendo el token)."""
            puerto = self.server.server_address[1]
            return self.headers.get("Host") in (f"127.0.0.1:{puerto}", f"localhost:{puerto}")

        def _json(self, codigo: int, obj: object) -> None:
            cuerpo = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return self._json(403, dict(error="host no permitido"))
            if self.path == "/":
                html = PAGINA.replace("__TOKEN__", token).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            elif self.path == "/api/cola":
                revs = leer_revisiones(ruta_revisiones)
                pendientes = aplicar_revisiones(cola, revs)
                self._json(200, dict(cola=pendientes, pendientes=len(pendientes), acuerdo=tasa_acuerdo(revs)))
            else:
                self._json(404, dict(error="no encontrado"))

        def do_POST(self):  # noqa: N802
            if not self._host_ok():
                return self._json(403, dict(error="host no permitido"))
            if self.path != "/api/revision":
                return self._json(404, dict(error="no encontrado"))
            if not secrets.compare_digest((self.headers.get("X-Panel-Token") or "").encode(), token.encode()):
                return self._json(403, dict(error="token inválido"))
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return self._json(415, dict(error="se espera application/json"))
            try:
                largo = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, dict(error="Content-Length inválido"))
            if largo <= 0 or largo > MAX_CUERPO:
                return self._json(413, dict(error="cuerpo demasiado grande o vacío"))
            try:
                rev = validar_revision(json.loads(self.rfile.read(largo)), validos, patrones)
            except (ValueError, TypeError, RecursionError) as e:  # JSONDecodeError es un ValueError
                return self._json(400, dict(error=str(e) or "cuerpo inválido"))
            ruta_revisiones.parent.mkdir(parents=True, exist_ok=True)
            with ruta_revisiones.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rev, ensure_ascii=False) + "\n")
            self._json(200, dict(ok=True))

        def log_message(self, *a):  # silencio
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    srv.token = token  # para pruebas
    return srv

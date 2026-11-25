"""Sella el pre-registro: guarda su sha256. Correr UNA vez, antes de cualquier resultado."""
import hashlib
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
YAML = RAIZ / "config" / "preregistro.yaml"
SELLO = RAIZ / "config" / "preregistro.sha256"


def hash_actual() -> str:
    return hashlib.sha256(YAML.read_bytes()).hexdigest()


if __name__ == "__main__":
    if SELLO.exists() and "--forzar" not in sys.argv:
        sys.exit(f"Ya sellado ({SELLO.read_text().strip()[:12]}...). Sellar de nuevo invalida resultados previos.")
    SELLO.write_text(hash_actual() + "\n")
    print("sellado", hash_actual())

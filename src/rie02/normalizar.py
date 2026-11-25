"""Normalización de teléfonos y direcciones (formatos peruanos simplificados).

Los datos son sintéticos: no hay DNI reales ni nombres. Los identificadores de
persona son códigos opacos (P0000123), no DNI, para no chocar con documentos reales.
"""
from __future__ import annotations

import re
import unicodedata


def normalizar_telefono(raw: object) -> str | None:
    """Móvil peruano: 9 dígitos que empiezan en 9, con o sin prefijo +51."""
    if raw is None:
        return None
    digitos = re.sub(r"\D", "", str(raw))
    if len(digitos) == 11 and digitos.startswith("51"):
        digitos = digitos[2:]
    if len(digitos) == 9 and digitos.startswith("9"):
        return digitos
    return None


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


_RE_MZ = re.compile(r"\b(?:mz|manzana)\s*([a-z])\b")
_RE_LT = re.compile(r"\b(?:lt|lote)\s*(\d+)\b")
_RE_URB = re.compile(r"\b(?:urb|urbanizacion)\s+([a-z ]+?)\s*$")


def normalizar_direccion(raw: object) -> str | None:
    """Clave canónica 'urbanizacion|manzana|lote'. None si falta alguna parte."""
    if raw is None:
        return None
    s = _sin_acentos(str(raw)).lower()
    s = re.sub(r"[.,\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    mz, lt, urb = _RE_MZ.search(s), _RE_LT.search(s), _RE_URB.search(s)
    if not (mz and lt and urb):
        return None
    return f"{urb.group(1).strip()}|{mz.group(1)}|{lt.group(1)}"

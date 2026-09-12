"""¿Sigue esta subasta o inmueble realmente en proceso?

Un listado de oportunidades sólo vale si lo que muestra se puede pujar o comprar
hoy. Se descarta todo lo que tenga alguna señal de estar cerrado: un estado que
lo diga, una fecha de conclusión ya pasada, o un texto del anuncio que indique
que se vendió, se adjudicó o quedó desierto.

Ante la falta de información se conserva: muchas fichas de servicers no publican
fechas y retirarlas por silencio vaciaría el listado.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from .parse import normaliza

# Palabras que, en el estado o en el texto, significan que ya no está disponible.
CERRADO = (
    "cancelada", "cancelado", "concluida", "concluido", "finalizada", "finalizado",
    "suspendida", "suspendido", "desierta", "desierto", "adjudicada", "adjudicado",
    "vendida", "vendido", "reservada", "reservado", "retirada", "retirado",
    "no disponible", "fuera de plazo", "plazo cerrado", "subasta cerrada",
)
# Estados que confirman que sigue viva.
ABIERTO = ("celebrandose", "proxima apertura", "en venta", "abierta", "activa")

_RE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_RE_ES = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


def fecha_de(texto: str | None) -> date | None:
    """Lee una fecha en formato ISO (2026-09-14…) o español (14-09-2026)."""
    if not texto:
        return None
    m = _RE_ISO.search(texto)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _RE_ES.search(texto)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _campo(inmueble, nombre: str):
    """Acepta tanto un Inmueble como el diccionario ya guardado en el JSON."""
    if isinstance(inmueble, dict):
        return inmueble.get(nombre)
    return getattr(inmueble, nombre, None)


def revisa(inmueble, hoy: date | None = None) -> tuple[bool, str]:
    """Devuelve (sigue_vigente, motivo_del_descarte)."""
    hoy = hoy or datetime.now().date()
    estado = normaliza(_campo(inmueble, "estado") or "")
    texto = normaliza(" ".join(filter(None, [
        _campo(inmueble, "titulo") or "", _campo(inmueble, "descripcion") or ""])))

    if any(p in estado for p in CERRADO):
        return False, f"estado «{estado}»"

    fin = fecha_de(_campo(inmueble, "fecha_fin"))
    if fin:
        if fin < hoy:
            return False, f"el plazo terminó el {fin.isoformat()}"
        if fin.year < hoy.year:
            return False, f"convocatoria de {fin.year}"

    # El texto del anuncio manda sobre el silencio del estado, pero sólo si la
    # señal es inequívoca: 'vendido' dentro de una descripción larga puede ser
    # parte de la historia registral de la finca.
    if not any(p in estado for p in ABIERTO):
        for palabra in ("subasta desierta", "adjudicada en firme", "ya vendida",
                        "inmueble vendido", "no disponible", "fuera de plazo"):
            if palabra in texto:
                return False, f"el anuncio dice «{palabra}»"

    return True, ""

"""Aplicación de los criterios de búsqueda a un inmueble.

Muchos anuncios de subasta no publican todos los datos (es habitual que falte el
número de dormitorios o la superficie de parcela). En lugar de descartar por
silencio, se clasifica en tres estados:

  total     -> todos los criterios verificables se cumplen con dato explícito
  parcial   -> ningún criterio incumple, pero falta algún dato por confirmar
  descartado-> al menos un criterio se incumple con dato explícito
"""
from __future__ import annotations

from .config import CRITERIOS, Criterios
from .models import Inmueble


def evalua(inm: Inmueble, c: Criterios = CRITERIOS) -> tuple[str, list[str]]:
    """Devuelve (estado, lista de datos que faltan por confirmar)."""
    faltan: list[str] = []

    # Tipología
    if inm.tipo == "no_casa":
        return "descartado", ["tipo"]
    if inm.tipo != "casa":
        faltan.append("tipo")

    # Dormitorios
    if inm.dormitorios is None:
        faltan.append("dormitorios")
    elif inm.dormitorios < c.dormitorios_min:
        return "descartado", ["dormitorios"]

    # Superficie construida
    if inm.superficie_m2 is None:
        faltan.append("superficie")
    elif inm.superficie_m2 < c.superficie_min_m2:
        return "descartado", ["superficie"]

    # Terreno / parcela
    if inm.terreno_m2 is None:
        faltan.append("terreno")
    elif inm.terreno_m2 < c.terreno_min_m2:
        return "descartado", ["terreno"]

    # Distancia
    if inm.distancia_km is not None and inm.distancia_km > c.radio_km:
        return "descartado", ["distancia"]
    if inm.distancia_km is None:
        faltan.append("ubicacion")

    return ("total" if not faltan else "parcial"), faltan


def aplica(inm: Inmueble, c: Criterios = CRITERIOS) -> bool:
    """Anota el resultado en el inmueble y dice si debe conservarse."""
    estado, faltan = evalua(inm, c)
    inm.cumple, inm.faltan = estado, faltan
    return estado != "descartado"

"""Orquestador: recorre las fuentes, filtra, geolocaliza y actualiza el listado.

    python -m monitor.run                # pasada completa
    python -m monitor.run --fuente BOE   # sólo una fuente
    python -m monitor.run --sin-red      # re-evalúa lo ya guardado (sin scraping)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import asdict

from . import parse, store, vigencia
from .config import BARCELONA, CRITERIOS
from .criteria import aplica
from .geo import Geocodificador, haversine_km
from .http import Cliente
from .models import Inmueble
from .sources import todas

log = logging.getLogger("monitor")


def configura_log(verboso: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def principal(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monitor de subastas de casas cerca de Barcelona")
    ap.add_argument("--fuente", action="append", help="limita a las fuentes indicadas (subcadena)")
    ap.add_argument("--paginas", type=int, default=20, help="tope de páginas por listado")
    ap.add_argument("--sin-geo", action="store_true", help="no consultar Nominatim (usa sólo caché)")
    ap.add_argument("--sin-red", action="store_true", help="no scrapear, sólo re-evaluar el JSON")
    ap.add_argument("--robots", action="store_true", help="obedecer robots.txt de cada portal")
    ap.add_argument("-v", "--verboso", action="store_true")
    args = ap.parse_args(argv)
    configura_log(args.verboso)

    previo = store.carga()
    geo = Geocodificador(offline=args.sin_geo)

    if args.sin_red:
        return _reevalua(previo, geo)

    cliente = Cliente(comprobar_robots=args.robots or os.getenv("RESPETAR_ROBOTS") == "1")
    fuentes = [f for f in todas() if not args.fuente or
               any(x.lower() in f.nombre.lower() for x in args.fuente)]
    for f in fuentes:
        f.cliente = cliente
        f.limite_paginas = args.paginas
        if hasattr(f, "geo"):
            f.geo = geo        # permite descartar municipios lejanos antes de descargar

    encontrados: list[Inmueble] = []
    origenes_ok: list[str] = []
    resumen_fuentes: dict[str, dict] = {}

    for fuente in fuentes:
        log.info("── Fuente %s ──", fuente.nombre)
        crudos = brutos = cerrados = 0
        try:
            for inm in fuente.recoge():
                brutos += 1
                inm.origen = fuente.nombre
                # Antes que nada: si el proceso ya está cerrado no interesa, y así
                # tampoco se gasta una consulta de geolocalización en él.
                sigue, motivo = vigencia.revisa(inm)
                if not sigue:
                    cerrados += 1
                    log.debug("Descartado %s: %s", inm.referencia, motivo)
                    continue
                if not aplica(inm):
                    continue
                _ubica(inm, geo)
                if not aplica(inm):      # segunda pasada, ya con distancia
                    continue
                encontrados.append(inm)
                crudos += 1
        except Exception:
            log.exception("Fallo recogiendo %s", fuente.nombre)
            continue
        if brutos:
            origenes_ok.append(fuente.nombre)
        resumen_fuentes[fuente.nombre] = {"revisados": brutos, "cerrados": cerrados,
                                          "aceptados": crudos}
        log.info("%s: %s anuncios revisados, %s ya cerrados, %s cumplen criterios",
                 fuente.nombre, brutos, cerrados, crudos)

    geo.guarda()
    estado, cambios = store.fusiona(previo, encontrados, origenes_ok)
    estado["criterios"] = asdict(CRITERIOS)
    estado["resumen_fuentes"] = resumen_fuentes
    store.guarda(estado)

    log.info("RESULTADO: %(total)s en el listado (%(activos)s vigentes) · %(altas)s altas · "
             "%(actualizados)s actualizados · %(bajas)s bajas · %(caducados)s caducados", cambios)
    if not estado["inmuebles"]:
        log.warning("El listado ha quedado vacío: revisa los parsers antes de publicar")
    return 0


def _ubica(inm: Inmueble, geo: Geocodificador) -> None:
    inm.municipio = parse.titulo_lugar(parse.normaliza_municipio(inm.municipio))
    coords = geo.coords(inm.municipio, inm.provincia)
    if coords:
        inm.lat, inm.lon = coords
        inm.distancia_km = haversine_km(BARCELONA, coords)
        # El nombre oficial de OSM unifica las variantes de cada portal.
        inm.municipio = geo.nombre_canonico(inm.municipio, inm.provincia) or inm.municipio


def _reevalua(previo: dict, geo: Geocodificador) -> int:
    """Vuelve a aplicar criterios y distancias sobre el JSON existente."""
    vivos = []
    for d in previo.get("inmuebles", []):
        inm = Inmueble(**{k: v for k, v in d.items()
                          if k in Inmueble.__dataclass_fields__})
        _ubica(inm, geo)
        if aplica(inm):
            nuevo = inm.to_dict()
            nuevo["first_seen"] = d.get("first_seen", nuevo["first_seen"])
            nuevo["activo"] = d.get("activo", True)
            vivos.append(nuevo)
    geo.guarda()
    previo["inmuebles"] = vivos
    previo["criterios"] = asdict(CRITERIOS)
    store.guarda(previo)
    log.info("Re-evaluados %s inmuebles", len(vivos))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())

"""Persistencia incremental del listado.

El fichero data/listings.json es el estado completo: cada ejecución fusiona los
hallazgos nuevos conservando first_seen, marcando last_seen y desactivando lo que
ya no aparece en origen (sin borrarlo, para no perder el histórico).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import vigencia
from .models import Inmueble, ahora

RUTA = Path(__file__).resolve().parent.parent / "data" / "listings.json"
# La página se abre a menudo con doble clic (file://), donde el navegador prohíbe
# fetch() por CORS. Un .js con los mismos datos se carga con <script> sin ese
# problema, así que se emiten los dos.
RUTA_JS = RUTA.with_suffix(".js")

# Campos que, si vienen vacíos en la nueva pasada, no deben pisar lo ya guardado.
_NO_PISAR = ("imagen", "lat", "lon", "distancia_km", "superficie_m2", "terreno_m2",
             "dormitorios", "banos", "precio", "municipio", "descripcion")


def carga(ruta: Path = RUTA) -> dict:
    if Path(ruta).exists():
        try:
            return json.loads(Path(ruta).read_text("utf-8"))
        except json.JSONDecodeError:
            pass
    return {"generado": None, "criterios": {}, "fuentes": [], "inmuebles": []}


def fusiona(previo: dict, nuevos: list[Inmueble], origenes_ok: list[str]) -> tuple[dict, dict]:
    """Devuelve (estado_nuevo, resumen_de_cambios).

    `origenes_ok` son las fuentes que respondieron en esta pasada. Se usa el
    módulo de origen y no la etiqueta visible: si el BOE devuelve subastas
    judiciales pero ninguna de la AEAT, las fichas de la AEAT que ya no están en
    el portal deben darse de baja igualmente.
    """
    ts = ahora()
    indice = {i["id"]: i for i in previo.get("inmuebles", [])}
    vistos: set[str] = set()
    altas, actualizados = [], 0

    for inm in nuevos:
        d = inm.to_dict()
        vistos.add(d["id"])
        anterior = indice.get(d["id"])
        if anterior is None:
            d["first_seen"] = ts
            d["last_seen"] = ts
            d["activo"] = True
            indice[d["id"]] = d
            altas.append(d)
        else:
            for campo in _NO_PISAR:
                if d.get(campo) in (None, "", []) and anterior.get(campo) not in (None, "", []):
                    d[campo] = anterior[campo]
            d["first_seen"] = anterior.get("first_seen", ts)
            d["last_seen"] = ts
            d["activo"] = True
            if {k: v for k, v in d.items() if k != "last_seen"} != {
                k: v for k, v in anterior.items() if k != "last_seen"
            }:
                actualizados += 1
            indice[d["id"]] = d

    # Desactivar sólo lo de fuentes que sí respondieron en esta pasada.
    bajas = 0
    for id_, d in indice.items():
        if id_ in vistos:
            continue
        if d.get("origen", d.get("fuente")) in origenes_ok and d.get("activo", True):
            d["activo"] = False
            d["baja_detectada"] = ts
            bajas += 1

    # Retirar lo que ya no está en proceso aunque el portal no lo haya dicho:
    # un plazo vencido ayer basta para que no deba figurar en el listado.
    caducados = 0
    for d in indice.values():
        if not d.get("activo", True):
            continue
        sigue, motivo = vigencia.revisa(d)
        if not sigue:
            d["activo"] = False
            d["baja_detectada"] = ts
            d["baja_motivo"] = motivo
            caducados += 1

    inmuebles = sorted(
        indice.values(),
        key=lambda d: (not d.get("activo", True), d.get("distancia_km") or 9e9),
    )
    estado = {
        "generado": ts,
        "criterios": previo.get("criterios", {}),
        "fuentes": sorted({d["fuente"] for d in inmuebles if d.get("activo", True)}),
        "origenes": origenes_ok,
        "inmuebles": inmuebles,
    }
    return estado, {"altas": len(altas), "actualizados": actualizados, "bajas": bajas,
                    "caducados": caducados, "total": len(inmuebles),
                    "activos": sum(1 for d in inmuebles if d.get("activo", True))}


def guarda(estado: dict, ruta: Path = RUTA) -> None:
    """Guarda el listado como JSON y como JS (este último para abrirlo en local)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, ensure_ascii=False, indent=1), "utf-8")

    publico = dict(estado, inmuebles=[d for d in estado["inmuebles"] if d.get("activo", True)])
    ruta.with_suffix(".js").write_text(
        "/* Generado por el monitor. La página lo carga con <script> para poder\n"
        "   abrirse también desde el disco, donde fetch() está prohibido. */\n"
        "window.SUBASTAS = " + json.dumps(publico, ensure_ascii=False) + ";\n"
        "window.dispatchEvent(new Event('subastas:listas'));\n", "utf-8")

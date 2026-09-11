"""Persistencia incremental del listado.

El fichero data/listings.json es el estado completo: cada ejecución fusiona los
hallazgos nuevos conservando first_seen, marcando last_seen y desactivando lo que
ya no aparece en origen (sin borrarlo, para no perder el histórico).
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import Inmueble, ahora

RUTA = Path(__file__).resolve().parent.parent / "data" / "listings.json"

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


def fusiona(previo: dict, nuevos: list[Inmueble], fuentes_ok: list[str]) -> tuple[dict, dict]:
    """Devuelve (estado_nuevo, resumen_de_cambios)."""
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
        if d.get("fuente") in fuentes_ok and d.get("activo", True):
            d["activo"] = False
            d["baja_detectada"] = ts
            bajas += 1

    inmuebles = sorted(
        indice.values(),
        key=lambda d: (not d.get("activo", True), d.get("distancia_km") or 9e9),
    )
    estado = {
        "generado": ts,
        "criterios": previo.get("criterios", {}),
        "fuentes": fuentes_ok,
        "inmuebles": inmuebles,
    }
    return estado, {"altas": len(altas), "actualizados": actualizados, "bajas": bajas,
                    "total": len(inmuebles),
                    "activos": sum(1 for d in inmuebles if d.get("activo", True))}


def guarda(estado: dict, ruta: Path = RUTA) -> None:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(estado, ensure_ascii=False, indent=1), "utf-8")

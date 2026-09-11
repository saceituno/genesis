"""Modelo de datos común a todas las plataformas."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Inmueble:
    # --- identidad
    fuente: str                      # plataforma visible (Servihabitat, BOE · Judicial, ...)
    url: str                         # enlace directo a la ficha
    origen: str = ""                 # módulo que lo recogió (BOE, Servihabitat): controla las bajas
    referencia: str = ""             # id/expediente en origen
    titulo: str = ""

    # --- ubicación
    municipio: str | None = None
    provincia: str | None = None
    direccion: str | None = None
    lat: float | None = None
    lon: float | None = None
    distancia_km: float | None = None

    # --- características
    tipo: str | None = None          # casa / no_casa / desconocido
    superficie_m2: float | None = None
    terreno_m2: float | None = None
    dormitorios: int | None = None
    banos: int | None = None

    # --- económico / subasta
    precio: float | None = None      # valor de subasta o precio de venta
    valor_tasacion: float | None = None
    deposito: float | None = None
    estado: str | None = None        # Celebrándose, Próxima apertura, En venta...
    fecha_fin: str | None = None
    organismo: str | None = None     # TGSS, AEAT, Juzgado n.º X

    # --- presentación
    imagen: str | None = None
    descripcion: str = ""

    # --- control
    cumple: str = "parcial"          # total | parcial
    faltan: list[str] = field(default_factory=list)
    first_seen: str = field(default_factory=ahora)
    last_seen: str = field(default_factory=ahora)
    activo: bool = True

    @property
    def id(self) -> str:
        base = f"{self.fuente}|{self.referencia or self.url}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d
